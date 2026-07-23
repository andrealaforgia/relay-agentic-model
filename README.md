# Agentic Working Model — EDD Relay Chain

A five-role relay where a human's problem is sliced into a validated roadmap and
delivered one potentially shippable increment at a time, through
[Expectation-Driven Development](https://a4al6a.substack.com/p/expectation-driven-development-a)
— with three out-of-chain observers (a **Sentinel**, a **QA** reviewer, and a
**Warden** security expert) watching alongside. Each chain agent talks only to its
immediate neighbours, and every message — including the human's gate decisions — is
recorded in an append-only ledger you can audit.

## The chain

```mermaid
flowchart LR
    O["Problem Owner<br/>(human)"] <--> I[Interpreter] <--> A[Analyst] <--> E[Examiner] <--> B[Builder]
    S(["Sentinel<br/>comms auditor"]) -. "advisory / warning / directive" .-> I
    S -.-> A
    S -.-> E
    S -.-> B
    Q(["QA<br/>Farley test-design"]) -. "test-review / warning" .-> B
    W(["Warden<br/>security expert"]) -. "security-review / warning" .-> B
```

| Role | Was called | Talks to | Transforms… |
|------|------------|----------|-------------|
| **Problem Owner** | Problem Stater | Interpreter | a problem; validates the roadmap; gives feedback + continue/stop each iteration (the human) |
| **Interpreter** | Problem Stater Proxy | Owner, Analyst | problem → **roadmap of shippable iterations**; packages each **increment** back to the Owner |
| **Analyst** | Solver | Interpreter, Examiner | behaviour-to-implement → a crisp **behaviour** |
| **Examiner** | Verifier | Analyst, Builder | behaviour → **expectations**; judges **evidence**; persists each satisfied behaviour as a committed **BDD feature** |
| **Builder** | Implementer | Examiner | expectations → code via **TDD** (test-first); proves each with **evidence** = a demonstrated run of the real system (not "tests pass") |

Names state the *transformation* each node performs. "Solver"/"Verifier" were
renamed because they don't solve or verify code — the Builder solves; the Examiner
sets expectations and judges evidence.

### Observers (outside the chain)

Three agents run alongside the relay but are not links in it — they only ever speak
*one-way*, and no agent replies:

- **Sentinel** — the communication auditor. Reads the whole ledger and may send
  `advisory` / `warning` / `directive` to any agent when a message drifts off-contract
  (e.g. the Builder leaking implementation detail up toward the Examiner).
- **QA** — the test-design reviewer. On new commits it scores the Builder's changed
  tests with the **Farley Index** (Dave Farley's 8 Properties of Good Tests) and sends
  the Builder a `test-review`, or a `warning` when quality drops below a calibrated floor.
- **Warden** — the security expert. On new commits it scans the Builder's changed code
  for vulnerabilities and violations of common security patterns, and sends the Builder
  a `security-review`, or a `warning` on any Critical/High or newly introduced vulnerability.

## Two ways to run it

The same chain, topology, and ledger back two execution surfaces:

- **Workflow orchestrator** (`orchestrator.workflow.js` + `ledger.mjs`) — headless,
  run-by-run; the Owner's gates happen conversationally between runs. This is what the
  sections below describe.
- **iTerm relay swarm** (`relay/`) — each agent is a long-lived Claude session in its
  own iTerm window, and messages travel as filesystem-mailbox files a dispatcher
  delivers; the Sentinel, QA, and Warden observers run as their own windows. Best when
  you want to watch the agents work live. See "Running as a live iTerm swarm" below.

## How an engagement runs

The Owner has two gates: **validate the roadmap**, and **per-iteration feedback +
continue?**. A headless workflow run can't pause for a human, so the engagement is
a sequence of workflow runs stitched together by those gates, which happen
conversationally between runs:

```mermaid
flowchart TD
    P([Owner states problem]) --> R["RUN mode: roadmap<br/>Interpreter slices the problem into<br/>ordered, shippable vertical slices"]
    R --> G1{"GATE 1<br/>Owner validates the roadmap"}
    G1 -->|"revise — re-run roadmap mode with ownerFeedback"| R
    G1 -->|approve| IT["RUN mode: iteration k<br/>relay: Interpreter → Analyst → Examiner ⇄ Builder<br/>(EDD loop) → one shippable increment + continue?"]
    IT --> G2{"GATE 2<br/>Owner feedback + continue?"}
    G2 -->|"continue — next iteration k+1"| IT
    G2 -->|"feedback reshapes the remaining roadmap → re-plan"| R
    G2 -->|stop| DONE([Engagement ends])
```

One **ledger spans the whole engagement** — every run appends to the same
`ledger/ledger.jsonl`, so the audit trail is continuous across all iterations and
gates.

## The rules of the topology

1. **Send only to neighbours.** An agent may message only its left/right neighbour.
2. **See only your edges.** Each agent is prompted with its two neighbours and only
   its own slice of the conversation. The full ledger belongs to *you, the auditor*.
3. **Fixed vocabulary per edge.** e.g. the Builder may only ever emit `evidence`;
   the Owner→Interpreter edge carries `problem` / `roadmap-verdict` / `feedback` /
   `decision`.
4. **Extraordinary broadcasts.** The Owner can send a `broadcast` — a line-wide
   instruction (a global constraint, a priority shift, "stop after this behaviour").
   It still travels neighbour-to-neighbour: each agent applies it and relays it to
   its downstream neighbour, so it reaches the whole chain
   (owner → interpreter → analyst → examiner → builder).
5. **Out-of-chain observers.** The Sentinel, QA, and Warden sit outside the chain and
   speak one-way only: the Sentinel may message any agent (`sentinel>*`), while QA and
   the Warden message the Builder (`qa>builder`, `warden>builder`). These edges are
   listed in `topology.json` beside the chain edges, so their messages validate too.

These rules live in **`topology.json`** — the single source of truth — and are
enforced in two places that both read it: the orchestrator's in-run `append()`
(rules passed in via `args.topology`) and `ledger.mjs` on persistence.

## Files

| File | Role |
|------|------|
| `topology.json` | **Single source of truth** for adjacency + per-edge message vocabulary. |
| `orchestrator.workflow.js` | The Claude Code Workflow script. `mode:"roadmap"` and `mode:"iteration"`, the agent prompts, and the relay flow. |
| `ledger.mjs` | Persistence chokepoint + auditor CLI (`count` / `append` / `append-batch` / `verify` / `show`). Runnable with `node`. |
| `schema/message.schema.json` | The ledger wire format (one message per line). |
| `ledger/ledger.jsonl` | The audit trail for one engagement. |
| `relay/` | The live **iTerm relay swarm** — one Claude session per role in its own window, filesystem-mailbox delivery, plus the Sentinel + QA + Warden observers. See "Running as a live iTerm swarm" below. |

`orchestrator.workflow.js` runs inside Claude's workflow engine (which provides
`agent()`, `log()`, …) — run it by asking Claude, not with `node`. `ledger.mjs` is
a plain Node script for the human/auditor side.

## Driving it (between-run loop)

The driver (Claude, relaying to you) repeats:

```
# 0. starting seq for the next run
SEQ=$(node ledger.mjs count)

# 1. plan — produces a roadmap for you to validate
Workflow({ scriptPath:"orchestrator.workflow.js",
           args:{ mode:"roadmap", problem:"<your problem>",
                  topology:<topology.json>, seqStart:SEQ }})
#    persist the run's messages, then record YOUR verdict:
node ledger.mjs append-batch <run-output.json>
node ledger.mjs append '{"from":"owner","to":"interpreter","type":"roadmap-verdict","body":"approved"}'

# 2. deliver iteration k — produces a shippable increment + "continue?"
Workflow({ scriptPath:"orchestrator.workflow.js",
           args:{ mode:"iteration", roadmap:<approved roadmap>, iterationIndex:k,
                  topology:<topology.json>, seqStart:$(node ledger.mjs count) }})
node ledger.mjs append-batch <run-output.json>
#    record YOUR feedback + decision:
node ledger.mjs append '{"from":"owner","to":"interpreter","type":"feedback","body":"..."}'
node ledger.mjs append '{"from":"owner","to":"interpreter","type":"decision","body":"continue"}'
# → repeat step 2 for k+1, or re-run step 1 to re-plan, or stop.
```

`seqStart` keeps sequence numbers continuous across runs; the workflow returns its
`messages`, which you persist with `append-batch`. Owner gate messages are appended
directly. Both paths validate against `topology.json`.

## Auditing an orchestrator run

```bash
node ledger.mjs show       # human-readable replay of the whole engagement
node ledger.mjs verify     # re-checks topology, vocabulary, and gap-free sequence

# Everything the Builder ever said (must be only 'evidence')
jq 'select(.from=="builder")' ledger/ledger.jsonl

# Trace one iteration's lineage
jq 'select(.refs[]? == "I1")' ledger/ledger.jsonl

# Every human gate decision
jq 'select(.from=="owner")' ledger/ledger.jsonl
```

Because the ledger is append-only with a gap-free `seq`, a missing or out-of-order
number is itself an audit signal — `ledger.mjs verify` flags it. Commit
`ledger.jsonl` to git per run for tamper-evident history.

(This is the orchestrator's own `ledger.mjs`, over `ledger/ledger.jsonl` at the repo
root. Each iTerm swarm keeps a separate ledger and its own CLI — see below.)

## Running as a live iTerm swarm

The same chain, topology, and message vocabulary as above — but instead of headless
workflow runs stitched together by conversational gates, each role is a **long-lived
Claude session in its own iTerm window**, and messages travel as plain files that a
dispatcher delivers between mailboxes. No server, no broker — every message is a file
you can `ls`, `cat`, and replay; a stuck chain is just a message sitting in an inbox.
Best when you want to watch the agents work live.

Only the `owner ↔ interpreter` edge is a live conversation — you type in the
Interpreter's window. The other three chain edges, plus the Sentinel/QA/Warden's
one-way messages, travel through `<project-dir>/.relay/mailbox/<role>/inbox|done/`.

### Quick start

```
relay/swarm-up.sh   <swarm-name> <project-dir>   # open all 7 windows + start all 5 daemons, detached
relay/swarm-down.sh <swarm-name> <project-dir>   # stop the daemons and close the windows
relay/swarm-down.sh <swarm-name> <project-dir> --keep-windows   # stop daemons only, leave windows open
```

`swarm-up.sh` is idempotent — it tears down any existing windows/daemons for that
project dir first, then relaunches. The ledger and mailboxes are preserved across
relaunches, and the daemons run via `nohup ... & disown`, so they outlive the
shell/session that launched them. Then talk to the **interpreter** window as the
Owner. `node`/`npm` must be on the agents' PATH (e.g. symlinked into
`/opt/homebrew/bin` if you use nvm).

Each swarm is fully isolated by project dir — its own `RELAY_HOME`
(`<project-dir>/.relay`, holding the ledger, mailboxes, and `iterm/windows.json`) and
its own set of iTerm windows — so several swarms can run at once without crossing.

### Files

```
relay/
  topology.json          the rules: permitted edges + per-edge message vocabulary
  relay.mjs               this swarm's CLI: send / inbox / next / ack / show / verify
  agents/<role>.md         the playbook each session adopts

  swarm-up.sh / swarm-down.sh   one-shot launch/teardown (see Quick start)
  iterm_launch.py          open the swarm as separate, tiled iTerm windows
  iterm_close.py           close a swarm's windows cleanly (used by swarm-down.sh)
  iterm_dispatch.py        push dispatcher — wakes a window when it has mail
  dispatch_watchdog.py     restarts the dispatcher if it dies
  iterm_sentinel.py / iterm_qa.py / iterm_warden.py   wake triggers for the three observers
  iterm_decorate.py        role badge + background colour per window (edit PALETTE to change)
  draw.py                  render the ledger as a swimlane comms board
  iterm_docwatch.py        optional: wakes a Documenter from git history
```

### Manual control

`swarm-up.sh` is just these steps, glued together — useful if you want to run one
daemon in the foreground for debugging, or only restart one of them:

```
START_DELAY=15 python3 relay/iterm_launch.py <swarm-name> <project-dir>
python3 relay/iterm_dispatch.py    --home <project-dir>/.relay &
python3 relay/dispatch_watchdog.py --home <project-dir>/.relay &
python3 relay/iterm_sentinel.py    --home <project-dir>/.relay &
python3 relay/iterm_qa.py          --home <project-dir>/.relay &
python3 relay/iterm_warden.py      --home <project-dir>/.relay &
python3 relay/iterm_decorate.py    --home <project-dir>/.relay   # optional: badge + colour
```

A daemon started with a bare trailing `&` from an interactive shell stays tied to
that shell/session and can die with it — use `nohup ... & disown` (what
`swarm-up.sh` does) if that matters to you.

### Sending and auditing a swarm

```
node relay/relay.mjs send  --as analyst --to examiner --type behaviour --body "..." --refs B1
node relay/relay.mjs inbox --as examiner            # what's waiting
node relay/relay.mjs show                           # human-readable replay of this swarm's conversation
node relay/relay.mjs verify                         # re-checks topology, vocabulary, gap-free sequence
```

Run these with `RELAY_HOME=<project-dir>/.relay` set (or from inside the project).
`topology.json` is the single source of truth for which message types are legal on
each edge. Because each swarm's ledger is append-only with a gap-free `seq`, a
missing or out-of-order number is itself an audit signal that `verify` flags.

### Resuming after a restart or crash

All state is on disk, so a reboot only loses the *processes*, not the work.
`swarm-up.sh` (or `iterm_launch.py` directly) is idempotent — it keeps the existing
ledger and mailboxes, the agents re-read their playbooks, and the dispatcher wakes
whoever still has pending mail. The swarm continues from exactly where it stopped.

### Troubleshooting: mail not being delivered

The dispatcher and the three observer triggers each decide "is this window idle or
busy" by matching known substrings in the tail of the session's visible text
(`"esc to interrupt"` = busy; `"for agents"` / `"? for shortcuts"` /
`"shift+tab to cycle"` = idle; anything unrecognized defaults to busy, since waking a
genuinely busy session mid-generation is worse than a missed wake). If a Claude Code
UI update changes that footer text, a window can look permanently "busy" to every
watcher and its mail silently never gets delivered — the daemon keeps running and
logs nothing wrong, so this fails silently.

If mail sits undelivered with no wake attempts logged for a role that's actually
idle, this is the first thing to check: capture that session's `contents` (see
`session_contents()` in `iterm_dispatch.py`, `iterm_sentinel.py`, `iterm_qa.py`, or
`iterm_warden.py`) and add whatever its current idle footer contains to the
`is_busy()` match list — in **all four** files.

### The observers, mechanically

- **Sentinel** (`iterm_sentinel.py`, every 45s) wakes when the ledger has grown past
  its audit cursor; findings go to `<RELAY_HOME>/audit/`.
- **QA** (`iterm_qa.py`, every 600s) wakes on new commits and scores the changed
  tests' Farley Index via the `alf-test-design-reviewer` agent.
- **Warden** (`iterm_warden.py`, every 600s) wakes on new commits and scans changed
  code for vulnerabilities via the `alf-security-assessor` agent.

Two more tools watch but never speak: **Communication Drawer**
(`python3 relay/draw.py --home <project-dir>/.relay`) renders the ledger as a
swimlane board at `<RELAY_HOME>/comms-site/index.html`; **Documenter**
(`agents/documenter.md` + `iterm_docwatch.py`, optional, not wired into the
launcher) watches git history and keeps an end-user docs site in sync.

### Why this resists getting stuck

All state is inspectable files — there is no hidden broker/connection state to
wedge. If an agent stalls, its unprocessed message is visibly sitting in its inbox;
re-run that one session and it picks up exactly where it left off (`done/` + the
`in_reply_to` field make reprocessing idempotent).

## Why this shape

- **Rules in one data file.** Topology + vocabulary live only in `topology.json`,
  read by both writers. No second place to drift.
- **The model never enforces the audit.** Adjacency, edges, vocabulary, and
  sequence are plain code/data, not something an agent is asked to remember.
- **Human gates are real.** Roadmap validation and per-iteration continue/stop are
  the Owner's decisions, recorded in the same ledger as the machine's messages.
- **EDD, faithfully.** The Examiner authors plain-language **expectations**; the
  Builder returns **evidence** — a demonstrated run of the real system, not "tests
  pass" — preferring *executed* over *generative*; the Examiner judges it
  adversarially and consolidates each satisfied behaviour into a committed **BDD
  feature** (Feature = behaviour, Scenario = expectation + the evidence that proved
  it), so the proof lives with the code. The Builder builds **test-first (TDD)**, and
  those tests double as the regression net EDD calls *stabilising* — but they are the
  Builder's discipline, distinct from the demonstrated evidence that governs
  correctness across the chain.
