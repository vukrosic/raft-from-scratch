"""Step 5 - copying the log.

Clients talk to the leader. The leader writes the command in its log and
sends it to everyone inside the heartbeat. Once a majority holds an entry
it is committed: safe forever, and every server may apply it.
"""
from network import Sim
from step1_log import apply
import step3_election
from step3_election import wait_for_leader


class Node(step3_election.Node):
    def __init__(self, id, n, net):
        self.log = []       # (term, command) pairs; index 1 is self.log[0]
        super().__init__(id, n, net)

    def start(self):
        """A reboot loses memory, not disk: term, vote and log survive."""
        self.commit = 0     # highest index known to be on a majority
        self.applied = 0    # highest index run against the store
        self.store = {}
        self.next, self.match = {}, {}
        super().start()

    # ---- the leader's side -----------------------------------------------
    def become_leader(self):
        last = len(self.log)
        self.next = {p: last + 1 for p in self.peers()}  # send this next
        self.match = {p: 0 for p in self.peers()}        # surely holds this
        super().become_leader()

    def client(self, command):
        """A client asks for a change. Only the leader accepts."""
        if self.role != "leader":
            return None
        self.log.append((self.term, command))
        self.send_heartbeats()      # do not wait for the next heartbeat
        return len(self.log)

    def append_request(self, p):
        prev = self.next[p] - 1     # the entry just before the ones we send
        prev_term = self.log[prev - 1][0] if prev else 0
        return {"type": "AppendEntries", "term": self.term,
                "prev_index": prev, "prev_term": prev_term,
                "entries": self.log[prev:], "commit": self.commit}

    def on_AppendReply(self, src, m):
        if self.role != "leader" or m["term"] != self.term:
            return
        if m["ok"]:
            self.match[src] = max(self.match[src], m["match"])
            self.next[src] = self.match[src] + 1
            self.advance_commit()
        else:                       # that log differs: step back and retry
            back = min(self.next[src] - 1, m["match"] + 1)
            self.next[src] = max(1, back)
            self.net.send(self.id, src, self.append_request(src))

    def can_commit(self, index):
        return True                 # step 6 adds a rule here

    def advance_commit(self):
        for index in range(len(self.log), self.commit, -1):
            copies = 1 + sum(self.match[p] >= index for p in self.peers())
            if copies > self.n // 2 and self.can_commit(index):
                self.commit = index
                self.net.note(self.id, "commit", term=self.term,
                              index=index, copies=copies)
                self.apply_committed()
                return

    # ---- the follower's side ---------------------------------------------
    def on_AppendEntries(self, src, m):
        if m["term"] < self.term:           # an old leader: tell it the news
            self.reply(src, False)
            return
        super().on_AppendEntries(src, m)    # stay a follower, reset the timer
        prev, mine = m["prev_index"], len(self.log)
        if prev > mine or (prev and self.log[prev - 1][0] != m["prev_term"]):
            self.reply(src, False, min(prev - 1, mine))   # no match there
            return
        for k, entry in enumerate(m["entries"]):
            at = prev + k                   # position in the Python list
            if at < len(self.log) and self.log[at][0] != entry[0]:
                gone = len(self.log) - at   # mine disagrees: drop the rest
                self.net.note(self.id, "drop", term=self.term, count=gone)
                del self.log[at:]
            if at >= len(self.log):
                self.log.append(tuple(entry))
        match = prev + len(m["entries"])
        if m["commit"] > self.commit:
            self.commit = max(self.commit, min(m["commit"], match))
            self.apply_committed()
        self.reply(src, True, match)

    def reply(self, src, ok, match=0):
        m = {"type": "AppendReply", "term": self.term}
        self.net.send(self.id, src, {**m, "ok": ok, "match": match})

    # ---- everyone ----------------------------------------------------------
    def apply_committed(self):
        while self.applied < self.commit:
            self.applied += 1
            command = self.log[self.applied - 1][1]
            apply(self.store, command)
            self.net.applied(self.id, self.applied, command)


def show(sim, title):
    print(title)
    for s in sim.nodes:
        entries = " ".join(f"[{t}:{c}]" for t, c in s.log)
        print(f"  server {s.id} {s.role:<9} commit {s.commit}  {entries}")


def write(sim, command, wait=100):
    """Send one command to the leader; let the cluster work `wait` ms."""
    index = sim.leader().client(command)
    sent = sim.now
    sim.run(sim.now + wait)
    return index, sim.commit_time.get(index, sent) - sent


if __name__ == "__main__":
    sim = Sim(Node, seed=3)
    leader = wait_for_leader(sim)
    print(f"server {leader.id} leads term {leader.term} at {sim.now} ms")

    for command in ("set x 1", "add x 4", "set y 7"):
        index, took = write(sim, command)
        print(f"  '{command}' -> index {index}, committed after {took} ms")
    show(sim, f"{sim.now} ms: three writes")

    # A follower dies, misses two writes, comes back and catches up.
    lost = (leader.id + 1) % 5
    sim.kill(lost)
    for command in ("add x 2", "set x 3"):
        write(sim, command)
    show(sim, f"{sim.now} ms: server {lost} was dead for two writes")
    sim.restart(lost)
    back = sim.now
    sim.run(sim.now + 5000, stop=lambda: sim.nodes[lost].applied == 5)
    show(sim, f"{sim.now} ms: server {lost} caught up in {sim.now - back} ms")
    print("stores:", [s.store for s in sim.nodes])
