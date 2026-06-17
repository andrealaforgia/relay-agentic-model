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
node relay/relay.mjs init      # creates the mailboxes and an empty ledger
```

Then open **four terminals**, run `claude` in each from the repo root, and give each
its role, e.g.:

> "Read `relay/agents/examiner.md` and act as the Examiner. Run your loop."

| Session | Playbook | Driven by |
|---------|----------|-----------|
| Interpreter | `agents/interpreter.md` | the human Owner (this is where you talk) |
| Analyst | `agents/analyst.md` | reacts to its inbox |
| Examiner | `agents/examiner.md` | reacts to its inbox |
| Builder | `agents/builder.md` | reacts to its inbox |

The reactive sessions can poll with `/loop` (e.g. `/loop 15s` running their check),
or you can process on demand. Nothing happens until the Owner and Interpreter send
the first `behaviour-to-implement` — the chain is driven top-down.

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
