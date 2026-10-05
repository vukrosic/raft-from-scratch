"""Checks for every step. Run: python3 tests.py"""
import contextlib
import io

from network import Sim, SafetyError
from step1_log import apply, replay, LOG
from step2_majority import majority, tolerated, smallest_overlap
import step3_election
import step5_replication
from step3_election import wait_for_leader, kill_leader
from step4_split_vote import downtime, first_split
from step5_replication import write
from step6_safety import Node, partition_story, stale_story
from step7_chaos import chaos, NoVoteRule

# step 1: the same log in the same order gives the same store
assert apply({}, "set x 3") == {"x": 3}
assert apply({"x": 3}, "add x 2") == {"x": 5}
assert replay(LOG) == {"x": 3, "y": 8}
assert replay(["set x 1", "add x 4"]) != replay(["add x 4", "set x 1"])

# step 2: majorities always overlap
assert [majority(n) for n in (1, 2, 3, 4, 5, 6, 7)] == [1, 2, 2, 3, 3, 4, 4]
assert [tolerated(n) for n in (3, 5, 7)] == [1, 2, 3]
assert all(smallest_overlap(n)[2] >= 1 for n in range(3, 8))

# step 3: one leader per term, and a new one after a kill
for seed in range(20):
    sim = Sim(step3_election.Node, seed=seed)
    first = wait_for_leader(sim)
    assert first is not None and len(first.votes) >= 3
    old, died, new = kill_leader(sim)
    assert new is not None and new.id != old and new.term > first.term
    assert len(set(sim.leader_of)) == len(sim.leader_of)

# two live servers out of five can never elect anyone
sim = Sim(step3_election.Node, seed=0)
for _ in range(3):
    wait_for_leader(sim)
    sim.kill(sim.leader().id if sim.leader() else min(
        s.id for s in sim.nodes if s.role != "dead"))
assert wait_for_leader(sim, 5000) is None

# step 4: the same seed replays the same run; a split vote costs a term
assert downtime(7, 150) == downtime(7, 150)
assert first_split()[1].leader().term > 1

# step 5: a committed entry sits on a majority, and everyone ends the same
sim = Sim(step5_replication.Node, seed=1)
leader = wait_for_leader(sim)
for k, command in enumerate(LOG):
    index, took = write(sim, command)
    assert index == k + 1 and 0 < took < 100
    assert sum(len(s.log) >= index for s in sim.nodes) >= 3
assert all(s.store == replay(LOG) for s in sim.nodes)
assert sim.nodes[(leader.id + 1) % 5].client("set x 9") is None

# step 6: the split heals, the stale server loses the election
with contextlib.redirect_stdout(io.StringIO()):     # the story prints
    sim, old, new, during = partition_story(Node)
assert all(s.log == sim.nodes[0].log for s in sim.nodes)
assert (1, "set x 100") not in sim.nodes[0].log
sim, sleeper, error = stale_story(Node)
assert error is None and sim.leader().id != sleeper
assert stale_story(step5_replication.Node)[2] is not None

# step 7: chaos never breaks full Raft, and breaks it without the vote rule
for seed in range(20):
    assert chaos(seed)["error"] is None
assert any(chaos(seed, NoVoteRule)["error"] for seed in range(5))
print("all tests passed")
