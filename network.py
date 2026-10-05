"""A pretend network: five servers inside one program, on a clock we control.

Nothing here is Raft. It does three jobs for the servers:
  send(src, dst, message)    deliver a message a few milliseconds later
  set_timer(node, kind, ms)  wake a server up later
  note(...) / applied(...)   write down what happened, catch broken promises
The clock and the dice are ours, so the same seed replays the same run.
"""
import heapq
import random

TIMEOUT = (150, 300)   # ms a server waits for the leader before an election
DELAY = (5, 15)        # ms for one message to cross the network
HEARTBEAT = 50         # ms between a leader's "I am alive" messages


class SafetyError(Exception):
    """A promise Raft must never break was broken."""


class Sim:
    def __init__(self, node, n=5, seed=0, timeout=TIMEOUT, loss=0.0):
        self.rng = random.Random(seed)
        self.timeout, self.delay, self.loss = timeout, DELAY, loss
        self.heartbeat = HEARTBEAT
        self.now = 0            # the clock, in ms
        self.events = []        # heap of (time, order, kind, data)
        self.order = 0
        self.timers = {}        # (node, kind) -> the one timer that counts
        self.down = set()       # dead servers
        self.groups = None      # a network split: sets that cannot talk
        self.trace = []         # everything the servers noted
        self.wire = []          # messages: (sent, arrives, src, dst, type)
        self.leader_of = {}     # term -> the one server that won it
        self.committed = {}     # log index -> the command applied there
        self.commit_time = {}   # log index -> when it was first applied
        self.nodes = [node(i, n, self) for i in range(n)]
        for server in self.nodes:
            server.start()

    # ---- what the servers call -------------------------------------------
    def push(self, delay, kind, data):
        self.order += 1
        when = self.now + delay
        heapq.heappush(self.events, (when, self.order, kind, data))
        return self.order

    def linked(self, a, b):
        groups = self.groups
        return groups is None or any(a in g and b in g for g in groups)

    def send(self, src, dst, message):
        delay = self.rng.randint(*self.delay)
        lost = not self.linked(src, dst) or self.rng.random() < self.loss
        arrives = None if lost else self.now + delay
        self.wire.append((self.now, arrives, src, dst, message["type"]))
        if not lost:
            self.push(delay, "message", (src, dst, message))

    def set_timer(self, node, kind, ms):
        self.timers[(node, kind)] = self.push(ms, "timer", (node, kind))

    def note(self, node, what, **more):
        if what == "leader":    # Election Safety: one leader per term
            if self.leader_of.setdefault(more["term"], node) != node:
                raise SafetyError(f"two leaders in term {more['term']}")
        self.trace.append({"t": self.now, "node": node, "what": what, **more})

    def applied(self, node, index, command):
        """State Machine Safety: one index, one command, on every server."""
        first = self.committed.setdefault(index, command)
        self.commit_time.setdefault(index, self.now)
        if first != command:
            raise SafetyError(
                f"index {index}: server {node} applied '{command}' "
                f"but '{first}' was already applied there")

    # ---- what the experiment calls ---------------------------------------
    def run(self, until, stop=None):
        """Play events in time order up to `until` ms, or until stop()."""
        while self.events and self.events[0][0] <= until:
            self.now, order, kind, data = heapq.heappop(self.events)
            if kind == "timer":
                node, name = data
                live = self.timers.get((node, name)) == order
                if live and node not in self.down:
                    self.nodes[node].on_timer(name)
            else:
                src, dst, message = data
                if dst not in self.down and self.linked(src, dst):
                    self.nodes[dst].on_message(src, message)
            if stop and stop():
                return self.now
        self.now = until
        return None

    def leader(self):
        """The live leader with the newest term, or None."""
        leaders = [s for s in self.nodes if s.role == "leader"]
        return max(leaders, key=lambda s: s.term) if leaders else None

    def kill(self, node):
        self.down.add(node)
        self.nodes[node].role = "dead"
        self.note(node, "kill")

    def restart(self, node):
        self.down.discard(node)
        self.nodes[node].start()
        self.note(node, "restart")

    def split(self, *groups):
        self.groups = [set(g) for g in groups] if groups else None
        self.note(None, "split" if groups else "heal")
