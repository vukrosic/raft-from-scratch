"""Step 2 - the majority.

A decision counts once more than half of the servers hold it.
Any two majorities share at least one server, so two groups can never
decide two different things.
"""
from itertools import combinations


def majority(n):
    return n // 2 + 1


def tolerated(n):
    """How many servers can be dead while a majority is still alive."""
    return n - majority(n)


def smallest_overlap(n):
    """Check every pair of majority-sized groups for shared servers."""
    groups = list(combinations(range(n), majority(n)))
    pairs = list(combinations(groups, 2))
    overlap = min(len(set(a) & set(b)) for a, b in pairs)
    return len(groups), len(pairs), overlap


if __name__ == "__main__":
    print("size  majority  can lose")
    for n in range(1, 8):
        print(f"{n:>4}  {majority(n):>8}  {tolerated(n):>8}")

    groups, pairs, overlap = smallest_overlap(5)
    print(f"5 servers: {groups} groups of 3, {pairs} pairs of groups, "
          f"smallest overlap {overlap}")

    # Two groups of 2 out of 5 can miss each other completely.
    pairs = list(combinations(combinations(range(5), 2), 2))
    apart = sum(1 for a, b in pairs if not set(a) & set(b))
    print(f"groups of 2: {apart} of {len(pairs)} pairs share nobody")
