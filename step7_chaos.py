"""Step 7 - our own chaos monkey.

For 20 simulated seconds a monkey kills servers, restarts them, cuts the
network, heals it and drops messages, while clients keep writing.
The network (network.py) raises SafetyError the moment two servers
disagree about a committed entry or two leaders share a term.
Then the same monkey attacks Raft with one rule of step 6 removed.
"""
import random
import sys

from network import Sim, SafetyError
from step3_election import wait_for_leader
from step6_safety import Node

COUNTS = ("writes", "committed", "kills", "restarts", "splits", "elections")


class NoVoteRule(Node):
    def log_ok(self, m):
        return True


class NoCommitRule(Node):
    def can_commit(self, index):
        return True


def monkey_step(sim, monkey, r):
    """One roll of the dice: write, kill, restart, split or heal."""
    roll = monkey.random()
    leaders = [s for s in sim.nodes if s.role == "leader"]
    if roll < 0.80:                 # a client writes to a claimed leader
        if leaders:
            r["writes"] += 1
            key = monkey.randint(0, 3)
            monkey.choice(leaders).client(f"set k{key} {r['writes']}")
    elif roll < 0.86:               # kill; half the time, aim at a leader
        if len(sim.down) < 2:
            alive = [s.id for s in sim.nodes if s.role != "dead"]
            if leaders and monkey.random() < 0.5:
                alive = [s.id for s in leaders]
            sim.kill(monkey.choice(alive))
            r["kills"] += 1
    elif roll < 0.92:
        if sim.down:
            sim.restart(monkey.choice(sorted(sim.down)))
            r["restarts"] += 1
    elif roll < 0.96:               # cut the network in two random pieces
        side = set(monkey.sample(range(5), monkey.randint(1, 2)))
        sim.split(side, set(range(5)) - side)
        r["splits"] += 1
    else:
        sim.split()                 # heal


def settle(sim, r):
    """The monkey leaves: heal, restart everyone, check they all agree."""
    sim.split()
    sim.loss = 0
    for i in sorted(sim.down):
        sim.restart(i)
    sim.run(sim.now + 1000)
    wait_for_leader(sim).client("set done 1")   # one write in the last term
    r["writes"] += 1
    sim.run(sim.now + 2000)
    first = sim.nodes[0]
    for s in sim.nodes:
        if s.log != first.log or s.store != first.store:
            raise SafetyError("the five servers did not end the same")
    for index, command in sim.committed.items():
        if first.log[index - 1][1] != command:
            raise SafetyError("a committed write is missing at the end")


def chaos(seed, node=Node, ms=20_000):
    sim = Sim(node, seed=seed, loss=0.05)       # 5% of messages vanish
    monkey = random.Random(1000 + seed)         # the monkey's own dice
    r = dict.fromkeys(COUNTS, 0)
    r["seed"], r["error"] = seed, None
    try:
        while sim.now < ms:
            sim.run(sim.now + monkey.randint(5, 40))
            monkey_step(sim, monkey, r)
        settle(sim, r)
    except SafetyError as error:
        r["error"] = f"{sim.now} ms: {error}"
    r["committed"] = len(sim.committed)
    r["elections"] = len(sim.leader_of)
    r["sim"] = sim
    return r


def campaign(node, seeds):
    runs = [chaos(seed, node) for seed in seeds]
    total = {k: sum(r[k] for r in runs) for k in COUNTS}
    total["runs"] = len(runs)
    total["broken"] = [(r["seed"], r["error"]) for r in runs if r["error"]]
    return total


def report(name, t):
    print(f"{name}: {t['runs']} runs of 20 s")
    print(f"  {t['kills']} kills, {t['restarts']} restarts, "
          f"{t['splits']} network splits, {t['elections']} elections")
    print(f"  {t['writes']} writes sent, {t['committed']} committed")
    print(f"  runs with a broken promise: {len(t['broken'])}")
    for seed, error in t["broken"][:2]:
        print(f"    seed {seed}: {error}")


if __name__ == "__main__":
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    report("full Raft", campaign(Node, range(runs)))
    report("without the vote rule", campaign(NoVoteRule, range(200)))
    report("without the commit rule", campaign(NoCommitRule, range(runs)))
