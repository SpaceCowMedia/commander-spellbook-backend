# Variant generation: remaining macro-optimizations

This document collects the macro-level optimization ideas for variant generation that have
**not** been implemented yet. They complement the ones already in place:

- delta writes: the save phase only writes variants and relationship rows that actually changed;
- incremental generation: entity fingerprints (`VariantGenerationFingerprints`) detect what changed
  since the last run, and only the affected generator combos are regenerated;
- lightweight data loading: the variant relation tables are loaded as slim rows instead of Django
  model instances, and full `Variant` instances are only hydrated for the variants being written;
- parallel generation: the graph and restore phases fan out across forked worker processes on
  platforms that support the `fork` start method (production containers do);
- element-indexed variant set entries and packed-integer entry encoding (see below);
- element-indexed BFS unblocking in the results ("up") phase (see below).

One idea was implemented and then deliberately removed: a persistent per-combo variant set cache
(`ComboVariantSetCache`). It only skipped the "down" phase (`Graph.variants()`), while the results
discovery ("up") phase — which dominates the runtime — still ran in full for every combo, so the
cache did not pay for its own complexity (an extra table, input hashing over structural
fingerprints, and serialization of every variant set).

## Already implemented: variant set entry representation and up-phase indexing

Profiling showed the "up" phase (`Graph.results` → `_card_nodes_up`) running roughly 15–20x slower
than the "down" phase: it runs once per variant instead of once per combo, and each call installs a
per-variant filter that lazily re-filters every node's cached variant set. Almost all of that time
sat in `MinimalSetOfMultisets.subtree()` (invoked by `VariantSet.filter`), doing a linear scan of
every entry with a Python-level multiset `issubset` on each — tens of millions of comparisons per
run. The following changes address it directly.

### Element index over `MinimalSetOfMultisets`

`MinimalSetOfMultisets` keeps an `element → entries containing it` index alongside its set of
entries. Every subset of a probed entry, and every superset, shares at least one element with it
(the empty entry is the sole exception, handled explicitly), so `subtree()`, `add()`'s dominance
check, and its superset removal all scan only the union of the relevant buckets instead of the whole
collection. This turns the previously O(n) scans output-sensitive: `add()` building an *n*-entry set
drops from O(n²) toward roughly linear, and the per-variant `filter()`/`subtree()` cost collapses.
The change is confined to `minimal_set_of_multisets.py` (plus its `.pxd`/`.pyi`) and is transparent
to the rest of the pipeline.

### Packed-integer entries (`PackedEntry`)

Variant set entries are no longer `FrozenMultiset` (a dict plus a wrapper hashed via a `frozenset`
of its items). `PackedEntry` stores an entry as a sorted tuple of `element * COUNT_LIMIT + count`
integers. Subset tests and merges become linear merge-walks over sorted integers, and hashing and
equality are plain tuple operations — all of which Cython compiles to tight C. Negative elements
(templates, encoded as negated ids by `VariantSet.ingredients_to_entry`) decode correctly through
Python floor-division/modulo. The encoding is confined behind
`VariantSet.ingredients_to_entry`/`entry_to_ingredients`, so the blast radius is small; the visible
behavioral change is that `entry_to_ingredients` now yields ingredients in ascending-id order.
The save path (`_restore_variant`) was adjusted to compute order-dependent fields such as the
variant `name` from the ingredients in their final persisted display order rather than from entry
iteration order, so the stored name stays consistent with what `Variant.get_recipe()` reads back.

### Element-indexed BFS unblocking in the up phase

`_card_nodes_up`'s BFS previously parked combos whose feature requirements were not yet satisfiable
in two flat lists, and re-enqueued **every** parked combo whenever **any** new countable/uncountable
feature became available — latently quadratic on deep feature chains. Combos are now indexed by the
specific feature nodes that block them (`_uncountable_feature_blockers` /
`_countable_feature_blockers` report which nodes could unblock a stalled combo), and only the combos
actually waiting on a produced feature are woken. The enqueue guards were also reordered to test the
cheap `issuperset` multiset check before the expensive lazy variant-set filter.

Measured on a synthetic graph (90 cards, 58 combos, 6405 variants), these changes together took the
up phase from ~11.0s to ~5.7s and the down phase from ~0.72s to ~0.41s, with byte-identical recipe
output.

The remaining ideas below are ordered by expected impact.

## 1. Faster bulk writes on the PostgreSQL side

These matter for runs that still produce large create/update volumes (first generation, full
regenerations after wide-reaching changes). Background for each part:

- **`COPY` instead of multi-row `INSERT` for bulk creates.** Django's `bulk_create` sends batched
  `INSERT INTO ... VALUES (...), (...), ...` statements. Each batch has to be parsed, planned, and
  executed as a regular statement, and every value travels through the SQL text/bind protocol.
  PostgreSQL's `COPY FROM` is a dedicated bulk-load path: rows are streamed in a compact format
  with almost no per-row protocol or parsing overhead. At hundreds of thousands of rows it is
  typically several times faster than batched INSERTs. psycopg 3 exposes it as
  `cursor.copy('COPY table (cols) FROM STDIN')` + `copy.write_row(...)`, so the create half of
  `perform_bulk_saves` could stream `CardInVariant`/`TemplateInVariant`/... rows directly.
  Caveat: `COPY` cannot do upserts and reports conflicts as hard errors, so it only replaces the
  plain-insert paths.
- **Merge the create and update passes with an upsert.** `bulk_create(..., update_conflicts=True,
  unique_fields=..., update_fields=...)` compiles to `INSERT ... ON CONFLICT (...) DO UPDATE`,
  letting one statement per table handle both new and changed rows instead of separate
  `bulk_create` + `bulk_update` passes. `bulk_update` is the slower of the two because it builds
  large `CASE WHEN pk=... THEN ...` expressions per batch; `ON CONFLICT DO UPDATE` avoids that
  entirely. (This is how the variant set cache upserts its rows already.)
- **`SET LOCAL synchronous_commit = off` inside the save transaction.** By default PostgreSQL
  waits for the WAL to be flushed to disk before acknowledging each commit. With
  `synchronous_commit = off`, the commit returns as soon as the WAL record is written to memory;
  the flush happens up to ~1s later in the background. The transaction is still atomic and
  consistent — the only risk is losing *acknowledged* work if the server crashes within that
  window, which is acceptable here because a crashed generation is simply re-run. `SET LOCAL`
  scopes the setting to the current transaction, so nothing else is affected. This mainly helps
  when the save phase issues many statements/batches in sequence.
- **`ANALYZE` the variant tables after large writes**, so the query planner sees fresh statistics
  before the site starts querying the new data (autovacuum gets there eventually, but only after a
  delay proportional to the write volume).

With delta writes and incremental generation in place, routine runs write little, so this item
pays off mainly for the worst-case runs.
