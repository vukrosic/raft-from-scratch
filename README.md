# How Netflix survives a dead server — Raft consensus from scratch

Code for the video course. Netflix runs Chaos Monkey, a tool that kills its own production servers on purpose. For that to be safe, the servers that are left must still agree on one record of what happened. Raft is the standard algorithm for that agreement; it runs inside etcd, the store under Kubernetes. Here you build Raft step by step: five servers, a leader election, a copied log, two safety rules, and your own chaos monkey to attack it. Nine files, 634 lines of Python (blank lines and comments not counted), standard library only. Each file is one part of the video.

```bash
./run_all.sh              # every step, one to two minutes; output as in demo-output.txt
python3 step3_election.py # or one step at a time
python3 live.py           # bonus: the same servers on five real UDP ports (9101-9105)
python3 tests.py          # quick checks
```

Nothing to install. Steps 1 to 7 run on a simulated clock with seeded dice, so the output is the same on every machine. `live.py` uses real sockets and the real clock, so its timings change on every run; one run is saved in `live-output.txt`.

| Part | File | Lines | What it does |
| --- | --- | --- | --- |
| 1 | `step1_log.py` | 28 | Five servers apply the same six commands. Same order gives the same store; shuffled order gives 3 different answers |
| 2 | `step2_majority.py` | 20 | Majority size for 1 to 7 servers, and a check that any two majorities of five share at least one server |
| 3 | `network.py` | 84 | A pretend network: delayed messages, timers, a clock we control. Also the referee that raises `SafetyError` on a broken promise |
| 3 | `step3_election.py` | 113 | Follower, candidate, leader. Terms, votes, heartbeats. Kill the leader and a new one takes over |
| 4 | `step4_split_vote.py` | 33 | A split vote, then 1,000 elections for each timer range from 150-150 ms to 150-300 ms |
| 5 | `step5_replication.py` | 112 | The leader copies its log; an entry commits once a majority holds it; a dead server catches up |
| 6 | `step6_safety.py` | 67 | The vote rule and the commit rule, each with a switch to turn it off |
| 7 | `step7_chaos.py` | 88 | A monkey kills, restarts, splits the network and drops messages for 20 simulated seconds per run |
| bonus | `live.py` | 89 | The `Node` class from step 6, untouched, on real UDP sockets and threads |

## Results (`demo-output.txt`)

- First election: server 2 leads term 1 at 201 ms with 3 of 5 votes. Kill it and a new leader appears after 181 ms. With 2 of 5 alive there is no leader after 5,000 ms and the term climbs to 28.
- Timer ranges, 1,000 elections each: all timers at 150 ms → 922 stuck over 10 s. 150-155 ms → 21 stuck, median 1,847 ms. 150-300 ms → 0 stuck, median 184 ms, worst 652 ms.
- Copying: a write commits 19 to 23 ms after the leader gets it. A server that was dead for two writes catches up in 13 ms.
- Network split [2, 3] | [0, 1, 4]: the side with two servers accepts writes and commits none of them; 61 ms after healing all five logs match.
- Chaos monkey against full Raft, 1,000 runs of 20 s: 35,856 kills, 34,866 restarts, 36,235 network splits, 23,046 elections, 441,994 writes sent, 413,365 committed, 0 runs with a broken promise.
- Same monkey without the vote rule, 200 runs: 200 broken.
- Same monkey without the commit rule, 1,000 runs: 0 broken. The case that rule guards against (Figure 8 of the paper) needs a precise order of crashes that random chaos did not produce.
- Live run on real sockets: first leader at 154 ms, new leader 244 ms after the kill.

## What this does not show

This is a teaching version. It leaves out three things real systems add, all described in the Raft paper: writing the log to disk before answering (here a restart only pretends to keep it), snapshots that cut old entries off the log, and adding or removing servers while running. Zero broken promises in 1,000 random runs is a test, not a proof. Do not put this in production; use etcd, Consul or another tested implementation.

The video opens with Netflix because of Chaos Monkey. It does not claim that Netflix's own services run Raft.

## Sources

- Diego Ongaro and John Ousterhout. "In Search of an Understandable Consensus Algorithm." USENIX ATC 2014. Extended version: https://raft.github.io/raft.pdf. The 150-300 ms election timer, the vote rule (section 5.4.1) and the commit rule (section 5.4.2) follow this paper.
- Netflix Tech Blog, "The Netflix Simian Army", July 2011. Chaos Monkey code: https://github.com/Netflix/chaosmonkey
- etcd FAQ: https://etcd.io/docs/v3.5/faq/

## Your turn

Build clusters of three, five and seven servers. Kill the leader, wait for a new one, and kill that one too. How many leaders can each cluster lose before it stops? You know the answer from part 2; make the code show it. One answer is in `solutions/sizes.py`.

License: MIT.
