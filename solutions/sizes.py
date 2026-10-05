"""Your turn, solved: how many dead leaders can a cluster survive?

Build clusters of 3, 5 and 7 servers. Kill the leader, wait for a new
one, kill that one too, until nobody can win an election.
"""
import sys
sys.path.insert(0, ".")
from network import Sim
from step3_election import wait_for_leader, kill_leader
from step6_safety import Node

print("servers  majority  leaders killed before it stopped")
for n in (3, 5, 7):
    sim = Sim(Node, n=n, seed=1)
    wait_for_leader(sim)
    survived = 0
    while True:
        sim.run(sim.now + 1000)
        old, died, new = kill_leader(sim)
        if new is None:
            break
        survived += 1
    print(f"{n:>7}  {n // 2 + 1:>8}  {survived:>4} survived, "
          f"kill {survived + 1} left {n - len(sim.down)} alive: no leader")
