# The Minimal Set of Sets Abstract Data Type

## Introduction

The Minimal Set of Sets (MSS) is a data structure that represents a set of sets.
No set in a MSS is a subset of another set in the MSS.
When you add a new set to a MSS, one of two things happens:

1. If the new set is a superset of an existing set, nothing happens and the MSS remains unchanged.
2. Else if the new set is not a superset of any existing set, it is added to the MSS.
   Then, any sets that are supersets of the new set are removed from the MSS.


## Example

Suppose we have a MSS with the following sets:

```
{1, 2, 3}
{1, 2, 4}
{1, 3, 5}
```

If we add the set `{1, 2, 3, 4}`, nothing happens and the MSS remains unchanged.

If we add the set `{1, 2, 6}`, it is added to the MSS:

```
{1, 2, 3}
{1, 2, 4}
{1, 3, 5}
{1, 2, 6}
```

If we add the set `{1, 2}`, it is added to the MSS, and every superset of `{1, 2}` is removed:

```
{1, 2}
{1, 3, 5}
```

## Implementation

You can find the implementation of the MSS in the [minimal_set_of_sets.py](https://github.com/SpaceCowMedia/commander-spellbook-backend/blob/master/backend/spellbook/variants/minimal_set_of_sets.py) file.

Nevertheless, the implementation is not optimized for performance.
It is intended to be a reference implementation, because the performance of the MSS is not critical for the Commander Spellbook project.
If you need a more performant implementation, you can use the reference implementation as a starting point and optimize it for your use case.

These are the papers/links to refer for the implementation of an optimized MSS:

- [Stack Overflow Question #1](https://stackoverflow.com/questions/1737076/collection-of-sets-containing-no-sets-which-are-a-subset-of-another-in-the-colle)
- [Article: _"Data structure set-trie for storing and querying sets: Theoretical and empirical analysis"_](https://journals.plos.org/plosone/article/authors?id=10.1371/journal.pone.0245122)
- [Article: _"Multiset-Trie Data Structure"_](https://www.mdpi.com/1999-4893/16/3/170)
- [Article: _"Index Data Structure for Fast Subset and Superset Queries"_](https://osebje.famnit.upr.si/~savnik/papers/cdares13.pdf)
- [Stack Overflow Question #2](https://stackoverflow.com/questions/9353100/quickly-checking-if-set-is-superset-of-stored-sets)
- [Stack Overflow Question #3](https://stackoverflow.com/questions/1263524/superset-search)

This is an optimized implementation of a SetTrie in C++ with a Python API: [C++/Python implementation of a set-trie](https://github.com/BBVA/mercury-settrie).
The issue with this implementation is that it must be compiled during installation and it's incomplete (doesn't allow iteration and removal of sets at the time of writing).
