# Filesystem-mailbox relay

Four agents, each in its own Claude session on this machine, talking only to their
neighbours through plain files. No server, no broker — every message is a file you
can `ls`, `cat`, and replay. A stuck chain is just a message sitting in an inbox.

```
Owner (human)  ⇄  Interpreter  ⇄  Analyst  ⇄  Examiner  ⇄  Builder
                  └── live session ──┘   └─── mailbox files ───┘
```

The `owner↔interpreter` edge is a live conversation in the Interpreter's session.
The three agent-to-agent edges go through mailboxes.

## Files

```
relay/
  topology.json          the rules: adjacency + per-edge message vocabulary
  relay.mjs              the CLI: send / inbox / next / ack / show / verify
  ledger.jsonl           append-only audit trail — the single source of truth
  mailbox/<role>/inbox/  messages waiting for <role>
  mailbox/<role>/done/   messages <role> has processed
  agents/<role>.md       the playbook each session adopts
```

## Launch (one time)

```
relay/launch.sh <swarm-name> [project-dir]
```

This creates a tmux session named `<swarm-name>` with four windows
(interpreter, analyst, examiner, builder), each running `claude` in `project-dir`
and primed with its role. The swarm's private state lives in
`<project-dir>/.relay` — its `RELAY_HOME`. Then, in a separate terminal, start the
push dispatcher for that swarm:

```
python3 relay/dispatch.py --session <swarm-name> --home <project-dir>/.relay
```

| Window | Playbook | Driven by |
|--------|----------|-----------|
| interpreter | `agents/interpreter.md` | the human Owner (this is where you talk) |
| analyst | `agents/analyst.md` | woken by the dispatcher when a message arrives |
| examiner | `agents/examiner.md` | woken by the dispatcher when a message arrives |
| builder | `agents/builder.md` | woken by the dispatcher when a message arrives |

Attach with `tmux attach -t <swarm-name>` (switch windows: `Ctrl-b` then `1`–`4`).
Nothing happens until you talk to the **interpreter** window as the Owner and it
sends the first `behaviour-to-implement` — the chain is driven top-down.

### Push instead of poll — the dispatcher

`dispatch.py` watches the swarm's `ledger.jsonl` and, for each new message
addressed to a mailbox role, runs `tmux send-keys` to **wake that role's window**.
The agents stay idle (and cost nothing) until there's actually something for them —
no `/loop` polling burning tokens on empty inboxes. The ledger's gap-free `seq`
means each message is announced exactly once. (You can still drive manually instead:
just type `process your inbox` in a window, or `/loop` it.)

### Running several swarms at once

Each swarm is fully isolated — its own `RELAY_HOME` (ledger + mailboxes + lock) and
its own tmux session — so concurrent swarms on different projects never cross:

```
relay/launch.sh alpha ~/code/project-alpha
python3 relay/dispatch.py --session alpha --home ~/code/project-alpha/.relay   &

relay/launch.sh beta  ~/code/project-beta
python3 relay/dispatch.py --session beta  --home ~/code/project-beta/.relay    &
```

Pick a unique `<swarm-name>` per running swarm. Audit any swarm with
`RELAY_HOME=<project>/.relay node relay/relay.mjs show`.

### Manual launch (no script)

`RELAY_HOME=<dir> node relay/relay.mjs init`, then open four `claude` sessions
yourself and tell each: *"Read `relay/agents/<role>.md` and act as the `<role>`."*

## The message rhythm (one behaviour)

```
Interpreter --behaviour-to-implement--> Analyst
Analyst     --behaviour-------------->   Examiner
Examiner    --expectation------------>   Builder        (a set E1..En, incl. an integration expectation)
Builder     --evidence--------------->   Examiner
Examiner    --verdict (if unmet)----->   Builder        (loop until satisfied)
Examiner    --behaviour-status------->   Analyst
Analyst     --behaviour-status------->   Interpreter
Interpreter --increment + continue?-->   Owner
```

## Sending and receiving

Every send is validated against `topology.json` — wrong neighbour or wrong message
type for the edge is rejected before anything is written:

```
node relay/relay.mjs send  --as analyst --to examiner --type behaviour --body "..." --refs B1
node relay/relay.mjs inbox --as examiner            # what's waiting
node relay/relay.mjs next  --as examiner            # read the oldest (JSON)
node relay/relay.mjs ack   --as examiner --seq 7    # move it to done/
```

Long bodies: use `--body-file path`, or pipe on stdin with `-`.

## Auditing

```
node relay/relay.mjs show       # human-readable replay of the whole conversation
node relay/relay.mjs verify     # re-checks topology, vocabulary, gap-free sequence
```

`ledger.jsonl` is append-only with a gap-free `seq`, so a missing or out-of-order
number is itself a signal. Each session's own Claude transcript is a second,
independent record. Commit `ledger.jsonl` per engagement for tamper-evident history.

## Why this resists getting stuck

All state is inspectable files — there is no hidden broker/connection state to
wedge. If an agent stalls, its unprocessed message is visibly sitting in its inbox;
re-run that one session and it picks up exactly where it left off (`done/` + the
`in_reply_to` field make reprocessing idempotent).
