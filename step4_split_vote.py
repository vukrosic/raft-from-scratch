"""Step 4 - the split vote.

If two followers time out together, each votes for itself and nobody
reaches three votes. The fix is the random wait. This measures how much
randomness is needed: kill the leader 1000 times per setting and time
how long the cluster has no leader.
"""
import random
import statistics

from network import Sim
from step3_election import Node, wait_for_leader, show_trace

LIMIT = 10_000   # ms; give up on a trial after this long


def downtime(seed, spread, base=150):
    """Kill the leader once. Return ms until the other four elect one."""
    sim = Sim(Node, seed=seed)
    wait_for_leader(sim)
    sim.timeout = (base, base + spread)     # new waits come from this range
    sim.run(sim.now + 400 + random.Random(seed).randint(0, 49))
    died = sim.now
    sim.kill(sim.leader().id)
    return sim.now - died if wait_for_leader(sim, LIMIT) else LIMIT


def measure(spread, trials=1000):
    times = sorted(downtime(seed, spread) for seed in range(trials))
    return {"spread": spread, "trials": trials,
            "median": int(statistics.median(times)),
            "worst": times[-1],
            "stuck": sum(1 for t in times if t >= LIMIT)}


def first_split(seeds=range(1000)):
    """Find a boot where the first election ends with no winner."""
    for seed in seeds:
        sim = Sim(Node, seed=seed)
        if wait_for_leader(sim).term > 1:
            return seed, sim


if __name__ == "__main__":
    seed, sim = first_split()
    print(f"seed {seed}: a split vote at boot")
    show_trace(sim)

    print("wait range      median    worst   stuck over 10 s")
    for spread in (0, 5, 25, 50, 150):
        r = measure(spread)
        print(f"150-{150 + spread:<3} ms   {r['median']:>6} ms "
              f"{r['worst']:>6} ms   {r['stuck']:>4} of {r['trials']}")
