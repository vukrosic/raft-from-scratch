"""Step 3 - the election.

Every server is a follower, a candidate or the leader. Time is cut into
numbered terms. A follower that hears nothing for a random 150-300 ms
starts a new term and asks for votes; whoever collects a majority leads.
"""
from network import Sim


class Node:
    def __init__(self, id, n, net):
        self.id, self.n, self.net = id, n, net
        self.term = 0           # newest term I have heard of  (kept on disk)
        self.voted_for = None   # who got my vote in that term (kept on disk)
        self.role = "follower"
        self.leader = None
        self.votes = set()

    def peers(self):
        return [p for p in range(self.n) if p != self.id]

    def start(self):
        """Boot, or reboot after a crash: come back as a follower."""
        self.role, self.leader, self.votes = "follower", None, set()
        self.reset_election_timer()

    def reset_election_timer(self):
        wait = self.net.rng.randint(*self.net.timeout)
        self.net.set_timer(self.id, "election", wait)

    def on_timer(self, kind):
        if kind == "election" and self.role != "leader":
            self.start_election()
        if kind == "heartbeat" and self.role == "leader":
            self.send_heartbeats()

    # ---- standing for election -------------------------------------------
    def start_election(self):
        self.term += 1
        self.role = "candidate"
        self.voted_for = self.id
        self.votes = {self.id}
        self.net.note(self.id, "candidate", term=self.term)
        self.reset_election_timer()
        for p in self.peers():
            self.net.send(self.id, p, self.vote_request())

    def vote_request(self):
        return {"type": "RequestVote", "term": self.term}

    def log_ok(self, m):
        return True             # step 6 adds a rule here

    def on_RequestVote(self, src, m):
        free = self.voted_for in (None, src)
        grant = m["term"] == self.term and free and self.log_ok(m)
        if grant:
            self.voted_for = src
            self.reset_election_timer()
            self.net.note(self.id, "vote", term=self.term, to=src)
        reply = {"type": "Vote", "term": self.term, "granted": grant}
        self.net.send(self.id, src, reply)

    def on_Vote(self, src, m):
        mine = self.role == "candidate" and m["term"] == self.term
        if mine and m["granted"]:
            self.votes.add(src)
            if len(self.votes) > self.n // 2:
                self.become_leader()

    # ---- leading ---------------------------------------------------------
    def become_leader(self):
        self.role, self.leader = "leader", self.id
        votes = len(self.votes)
        self.net.note(self.id, "leader", term=self.term, votes=votes)
        self.send_heartbeats()

    def send_heartbeats(self):
        for p in self.peers():
            self.net.send(self.id, p, self.append_request(p))
        self.net.set_timer(self.id, "heartbeat", self.net.heartbeat)

    def append_request(self, p):
        return {"type": "AppendEntries", "term": self.term}

    def on_AppendEntries(self, src, m):
        if m["term"] == self.term:      # the leader of my term is alive
            self.role, self.leader = "follower", src
            self.reset_election_timer()

    # ---- every message goes through here ---------------------------------
    def on_message(self, src, m):
        if m["term"] > self.term:       # a newer term exists: step down
            was_leader = self.role == "leader"
            self.term, self.voted_for = m["term"], None
            self.role = "follower"
            if was_leader:
                self.net.note(self.id, "stepdown", term=self.term)
                self.reset_election_timer()
        getattr(self, "on_" + m["type"])(src, m)


def wait_for_leader(sim, limit=10_000):
    """Run until some live server is leader. Returns it, or None."""
    if sim.leader() is None:
        sim.run(sim.now + limit, stop=lambda: sim.leader() is not None)
    return sim.leader()


def show_trace(sim):
    for e in sim.trace:
        line = f"{e['t']:>5} ms  server {e['node']}  {e['what']:<9}"
        if "term" in e:
            line += f" term {e['term']}"
        if "to" in e:
            line += f"  -> server {e['to']}"
        if "votes" in e:
            line += f"  with {e['votes']} of 5 votes"
        print(line)


def kill_leader(sim, limit=5000):
    """Kill the leader; return (who died, when, the new leader or None)."""
    old, died = sim.leader(), sim.now
    sim.kill(old.id)
    return old.id, died, wait_for_leader(sim, limit)


if __name__ == "__main__":
    sim = Sim(Node, seed=3)
    wait_for_leader(sim)
    show_trace(sim)

    # Kill leaders one after another and time each recovery.
    for round_ in range(3):
        sim.run(sim.now + 1000)
        old, died, new = kill_leader(sim)
        alive = 5 - len(sim.down)
        head = f"{died:>5} ms  kill server {old} ({alive} alive)  ->  "
        print(head, end="")
        if new:
            print(f"server {new.id} leads term {new.term} "
                  f"after {sim.now - died} ms")
        else:
            term = max(s.term for s in sim.nodes if s.role != "dead")
            print(f"no leader after 5000 ms, term climbed to {term}")

    back, came = min(sim.down), sim.now
    sim.restart(back)
    new = wait_for_leader(sim)
    print(f"{came:>5} ms  restart server {back} (3 alive)  ->  "
          f"server {new.id} leads term {new.term} after {sim.now - came} ms")
