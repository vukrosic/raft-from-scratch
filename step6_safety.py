"""Step 6 - never lose a committed entry.

Two rules finish Raft:
  1. The vote rule: never vote for a candidate whose log is behind yours.
  2. The commit rule: a leader commits by counting copies only for entries
     of its own term (older entries become committed along with them).
Then two attacks: split the network, and let a server with an empty log
ask to lead.
"""
from network import Sim, SafetyError
import step5_replication
from step5_replication import show, write
from step3_election import wait_for_leader


class Node(step5_replication.Node):
    def last(self):
        """(term of my last entry, length of my log): how current I am."""
        return (self.log[-1][0] if self.log else 0, len(self.log))

    def vote_request(self):
        return {"type": "RequestVote", "term": self.term, "last": self.last()}

    def log_ok(self, m):
        return tuple(m["last"]) >= self.last()      # rule 1: not behind me

    def can_commit(self, index):
        return self.log[index - 1][0] == self.term  # rule 2: my term only


def partition_story(node=Node, seed=3):
    """Cut the leader off with one follower. Both sides take writes."""
    sim = Sim(node, seed=seed)
    old = wait_for_leader(sim)
    for command in ("set x 1", "set y 2"):
        write(sim, command)
    small = {old.id, (old.id + 1) % 5}
    big = set(range(5)) - small
    sim.split(small, big)
    for command in ("set x 100", "set y 200"):  # the old leader still accepts
        old.client(command)
    leads = lambda: [i for i in big if sim.nodes[i].role == "leader"]
    sim.run(sim.now + 5000, stop=leads)
    new = sim.nodes[leads()[0]]
    for command in ("set x 5", "set z 6", "add x 1"):
        new.client(command)
        sim.run(sim.now + 100)
    show(sim, f"{sim.now} ms: split {sorted(small)} | {sorted(big)}")
    during = [(s.role, s.commit, list(s.log)) for s in sim.nodes]
    sim.split()                                 # heal
    healed = sim.now
    agree = lambda: all(s.applied == 5 for s in sim.nodes)
    sim.run(sim.now + 5000, stop=agree)
    show(sim, f"{sim.now} ms: healed {sim.now - healed} ms ago")
    return sim, old.id, new.id, during


def stale_story(node=Node, seed=3):
    """A server sleeps through three writes, wakes up and asks to lead."""
    sim = Sim(node, seed=seed)
    leader = wait_for_leader(sim)
    sleeper = (leader.id + 1) % 5
    sim.kill(sleeper)
    for command in ("set x 1", "set y 2", "set z 3"):
        write(sim, command)                     # committed on the other four
    sim.kill(leader.id)
    sim.restart(sleeper)
    sim.set_timer(sleeper, "election", 1)       # it times out first
    try:
        new = wait_for_leader(sim)
        new.client("set w 9")
        sim.run(sim.now + 5000, stop=lambda: sim.nodes[sleeper].applied == 4)
        sim.run(sim.now + 100)
        return sim, sleeper, None
    except SafetyError as error:
        return sim, sleeper, str(error)


if __name__ == "__main__":
    partition_story()

    for name, node in (("without the vote rule", step5_replication.Node),
                       ("with the vote rule", Node)):
        sim, sleeper, error = stale_story(node)
        leader = sim.leader()
        print(f"{name}: empty server {sleeper} asks to lead -> "
              f"server {leader.id} leads term {leader.term}")
        if error:
            print("  BROKEN:", error)
        else:
            show(sim, "  every committed entry kept:")
