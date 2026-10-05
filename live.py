"""Bonus - the same servers on real sockets.

Five threads, five UDP ports on this machine, the real clock. The Raft
code is the class from step 6, untouched; only the network is swapped.
Timings change on every run. One run is saved in live-output.txt.
"""
import json
import random
import socket
import threading
import time

from step6_safety import Node

PORTS = [9101 + i for i in range(5)]
START = time.monotonic()


def ms():
    return int((time.monotonic() - START) * 1000)


class RealNet:
    """The three tools a server needs, for real: send, set_timer, note."""
    timeout, heartbeat = (150, 300), 50

    def __init__(self, id):
        self.rng = random.Random()
        self.timers = {}
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", PORTS[id]))

    def send(self, src, dst, message):
        packet = json.dumps({**message, "from": src}).encode()
        self.sock.sendto(packet, ("127.0.0.1", PORTS[dst]))

    def set_timer(self, node, kind, wait):
        self.timers[kind] = time.monotonic() + wait / 1000

    def note(self, node, what, **more):
        if what in ("leader", "stepdown"):
            print(f"{ms():>5} ms  server {node} {what}, term {more['term']}")

    def applied(self, node, index, command):
        pass


def serve(node, alive):
    """One server's whole life: wait for a packet or a timer, react."""
    net = node.net = RealNet(node.id)
    node.start()
    while alive[node.id]:
        wait = min(net.timers.values()) - time.monotonic()
        net.sock.settimeout(max(wait, 0.001))
        try:
            m = json.loads(net.sock.recvfrom(65536)[0])
            if m["type"] == "Client":
                node.client(m["command"])
            else:
                node.on_message(m["from"], m)
        except socket.timeout:
            pass
        for kind, when in list(net.timers.items()):
            if when <= time.monotonic():
                del net.timers[kind]
                node.on_timer(kind)
    net.sock.close()
    node.role = "dead"


def boot(node, alive, threads):
    alive[node.id] = True
    thread = threading.Thread(target=serve, args=(node, alive), daemon=True)
    threads[node.id] = thread
    thread.start()


def kill(node, alive, threads):
    alive[node.id] = False
    threads[node.id].join()


def leader_of(nodes):
    while True:
        leaders = [s for s in nodes if s.role == "leader"]
        if leaders:
            return max(leaders, key=lambda s: s.term)
        time.sleep(0.005)


def write(nodes, command):
    """Send one command to whoever leads right now and give it 100 ms."""
    packet = json.dumps({"type": "Client", "command": command}).encode()
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.sendto(packet, ("127.0.0.1", PORTS[leader_of(nodes).id]))
    client.close()
    time.sleep(0.1)


if __name__ == "__main__":
    nodes = [Node(i, 5, None) for i in range(5)]
    alive, threads = {}, {}
    for node in nodes:
        boot(node, alive, threads)
    first = leader_of(nodes)
    for command in ("set x 1", "add x 4", "set y 7"):
        write(nodes, command)
    print(f"{ms():>5} ms  3 writes; log lengths", [len(s.log) for s in nodes])

    died = ms()
    print(f"{died:>5} ms  kill server {first.id}")
    kill(first, alive, threads)
    leader_of(nodes)
    print(f"{ms():>5} ms  no leader for {ms() - died} ms")
    for command in ("add x 2", "set x 3"):
        write(nodes, command)

    boot(first, alive, threads)     # the old leader is back, with its disk
    time.sleep(0.5)
    print(f"{ms():>5} ms  server {first.id} is back; log lengths",
          [len(s.log) for s in nodes])
    print("stores:", [s.store for s in nodes])
    print("all five agree:", all(s.store == nodes[0].store for s in nodes))
