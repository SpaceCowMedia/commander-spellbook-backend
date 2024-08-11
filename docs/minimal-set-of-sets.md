# The Minimal Set of Multisets Abstract Data Type

## Introduction

The Minimal Set of Multisets (MSM) is a data structure that represents a set of multisets.
No multiset in a MSM is a subset of another multiset in the MSM.
When you add a new multiset to a MSM, one of two things happens:

1. If the new multiset is a superset of an existing multiset, nothing happens and the MSM remains unchanged.
2. Otherwise, if the new multiset is not a superset of any existing multiset, it is added to the MSM.
   Then, any multiset that is a superset of the added multiset is removed from the MSM.


## Example

Suppose we have a MSM with the following multisets:

```
{1: 1, 2: 1, 3: 2}
{1: 1, 2: 2, 4: 1}
{1: 1, 3: 1, 5: 1}
```

If we add the multiset `{1: 3, 2: 3, 3: 1, 4: 1}`, nothing happens and the MSM remains unchanged, because the new multiset is a superset of the second multiset.

If we add the multiset `{1: 1, 2: 1, 6: 1}`, it is added to the MSM:

```
{1: 1, 2: 1, 3: 2}
{1: 1, 2: 2, 4: 1}
{1: 1, 3: 1, 5: 1}
{1: 1, 2: 1, 6: 1}
```

If we add the multiset `{1: 1, 2: 2}`, it is added to the MSM, and all its supersets are removed:

```
{1: 1, 2: 1, 3: 2}
{1: 1, 3: 1, 5: 1}
{1: 1, 2: 1, 6: 1}
{1: 1, 2: 2}
```

If we add the multiset `{1: 1, 2: 1}`, it is added to the MSM, and all its supersets are removed:

```
{1: 1, 3: 1, 5: 1}
{1: 1, 2: 1}
```

## Implementation

You can find the implementation of the MSM in the [minimal_set_of_multisets.py](https://github.com/SpaceCowMedia/commander-spellbook-backend/blob/master/backend/spellbook/variants/minimal_set_of_multisets.py) file.

Nevertheless, the implementation is not optimized for performance.
It is intended to be a reference implementation, because the performance of the MSM is not critical for the Commander Spellbook project.
If you need a more performant implementation, you can use the reference implementation as a starting point and optimize it for your use case.

These are the papers/links to refer for the implementation of an optimized MSS (Minimal Set of Sets) data structure:

- [Stack Overflow Question #1](https://stackoverflow.com/questions/1737076/collection-of-sets-containing-no-sets-which-are-a-subset-of-another-in-the-colle)
- [Article: _"Data structure set-trie for storing and querying sets: Theoretical and empirical analysis"_](https://journals.plos.org/plosone/article/authors?id=10.1371/journal.pone.0245122)
- [Article: _"Index Data Structure for Fast Subset and Superset Queries"_](https://osebje.famnit.upr.si/~savnik/papers/cdares13.pdf)
- [Stack Overflow Question #2](https://stackoverflow.com/questions/9353100/quickly-checking-if-set-is-superset-of-stored-sets)
- [Stack Overflow Question #3](https://stackoverflow.com/questions/1263524/superset-search)

These are the papers/links to refer for the implementation of an optimized MSM (Minimal Set of Multisets) data structure:

- [Article: _"Multiset-Trie Data Structure"_ on MDPI](https://www.mdpi.com/1999-4893/16/3/170) and [on ResearchGate](https://www.researchgate.net/publication/369437643_Multiset-Trie_Data_Structure)
