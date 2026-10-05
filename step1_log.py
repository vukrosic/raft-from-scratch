"""Step 1 - the log.

A tiny key-value store. Every change is a command. If every server applies
the same commands in the same order, every server ends in the same state.
"""
import random


def apply(state, command):
    """Run one command against a store: 'set x 3' or 'add x 2'."""
    op, key, value = command.split()
    if op == "set":
        state[key] = int(value)
    elif op == "add":
        state[key] = state.get(key, 0) + int(value)
    return state


def replay(log):
    """Build a store from nothing by applying a whole log."""
    state = {}
    for command in log:
        apply(state, command)
    return state


LOG = ["set x 1", "add x 4", "set y 7", "add x 2", "set x 3", "add y 1"]

if __name__ == "__main__":
    print("log:", LOG)

    # Five servers, same log, same order.
    stores = [replay(LOG) for _ in range(5)]
    same = all(s == stores[0] for s in stores)
    print("same order  ->", stores[0], "on all 5:", same)

    # Same commands, but every server receives them in its own order.
    rng = random.Random(1)
    different = []
    for server in range(5):
        shuffled = LOG[:]
        rng.shuffle(shuffled)
        different.append(replay(shuffled))
        print(f"  server {server} shuffled ->", different[-1])
    distinct = len({tuple(sorted(s.items())) for s in different})
    print("own order   ->", distinct, "different answers on 5 servers")
