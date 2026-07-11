# Domain Model

Everything in Commander Spellbook is built from a small vocabulary. Learn these six
concepts and the rest of the codebase reads easily. The models live in
[`backend/spellbook/models/`](https://github.com/SpaceCowMedia/commander-spellbook-backend/tree/master/backend/spellbook/models).

## The core concepts

### Card

A real Magic card, mirrored from [Scryfall](https://scryfall.com/) (keyed by
`oracle_id` and synced by the `update_cards` task). Beyond its name it carries the
Magic characteristics used for filtering and validation — color identity, mana
value, type line, oracle text, keywords — inherited from the abstract **`Playable`**
base. A card can *produce features* directly (e.g. a card that by itself is
"an extra turn").

### Feature

A **named effect or result** — the abstraction that lets the engine chain things
together. Examples: `Infinite mana`, `Untap target permanent`, `Win the game`.
Cards and combos *produce* features; combos *need* features. A feature's **status**
decides how it is treated and shown:

| Status | Meaning |
|--------|---------|
| Hidden / Public utility | Intermediate building block used only by the engine (public ones are visible to combo submitters) |
| Helper | A reusable effect meant to be exploited by other combos |
| Contextual | Situational effect |
| Standalone | A meaningful, usually game-impacting result |

Features can be marked **uncountable** (only ever one copy — this also speeds up
generation).

### Template

A **placeholder for "any card matching a query"**, e.g. *"a creature with power 4 or
greater"*. A template holds a [Scryfall-style search query](api.md#the-search-query-language)
and a set of concrete **replacements** (cards known to satisfy it). Templates let a
combo be written generically; the engine expands them into real cards.

### Combo

The **editor-authored interaction** — the input to the engine. A combo is a *recipe*
that declares:

- **uses** — cards it needs (`CardInCombo`)
- **requires** — templates it needs (`TemplateInCombo`)
- **needs** — features it consumes as prerequisites (`FeatureNeededInCombo`)
- **produces** — features it results in (`FeatureProducedInCombo`)
- **removes** — features it invalidates (`FeatureRemovedInCombo`)

plus editorial text (mana needed, prerequisites, step-by-step description, notes). A
combo's **status** controls its role in generation — most importantly `GENERATOR`
(a combo that variants are generated *from*) versus `UTILITY` (a building block that
only exists to be chained into others).

### Variant

A **concrete, fully-resolved card combination** produced by the engine — the primary
object the API serves. Where a combo may say "a mana dork + Isochron Scepter", a
variant names the exact cards. Each variant records the generator combos it is
`of`, the combos it `includes`, the cards it `uses`, the templates it `requires`,
and the features it `produces`, and adds derived data: color identity, mana cost,
popularity, a power **bracket** estimate, and a review **status** (only `OK` and
`EXAMPLE` variants are public). Variant output is **pre-serialized/denormalized** on
save so reads are fast.

### Suggestions

Community-submitted content that waits for editor review before it becomes canonical:

- **VariantSuggestion** — a combo submitted by a user. Editors review it and, if
  accepted, turn it into a real Combo.
- **VariantUpdateSuggestion** — proposed edits to existing variants.
- **VariantAlias** — a redirect from an old or alternative id to a canonical variant,
  so links never break.

## How they relate

```
   Card ──produces──▶ Feature ◀──needs──── Combo ──produces──▶ Feature
    │                    ▲                   │
    │                    │ replacements      │ uses / requires
    │                 Template ◀─────────────┘
    │                                        │  variant generation engine
    └────────────────────────────────────────┼──────────────▶ Variant
                                              │   (of / includes)
                             VariantSuggestion (user-submitted ⇒ becomes a Combo)
```

The **feature** is the pivot: a card or combo *produces* a feature, and another combo
*needs* it. Chaining "produces → needs" across the graph is exactly what the
[variant generation engine](variant-generation.md) walks.

## Shared building blocks

A few abstract models and join tables recur throughout:

- **`Recipe`** — the abstract `uses` / `requires` / `produces` structure and
  automatic name generation, shared by `Combo`, `Variant`, and `VariantSuggestion`.
- **`Playable`** — Magic characteristics (color identity, mana value, type line, …)
  shared by `Card` and `Variant`.
- **`Ingredient` / `IngredientInCombination`** — the through-model base that carries
  per-item data such as `quantity` and starting **zone locations** (hand,
  battlefield, graveyard, …).

## The `[[name]]` reference syntax

Text fields (descriptions, prerequisites) can reference a feature by name with
`[[name]]`. Two modifiers exist: `[[name|alias]]` gives it a reusable alias, and
`[[name$number]]` selects one of several copies. This lets editorial prose refer to
generated pieces without hardcoding card names.

## Where to go next

The [Variant Generation](variant-generation.md) page explains how the engine turns
these combos into variants.
