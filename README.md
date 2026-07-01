# Agentic Working Model — EDD Relay Chain

A five-role relay where a human's problem is sliced into a validated roadmap and
delivered one potentially shippable increment at a time, through
[Expectation-Driven Development](https://a4al6a.substack.com/p/expectation-driven-development-a).
Each agent talks only to its immediate neighbours, and every message — including
the human's gate decisions — is recorded in an append-only ledger you can audit.

## The chain

```mermaid
flowchart LR
    O["Problem Owner<br/>(human)"] <--> I[Interpreter] <--> A[Analyst] <--> E[Examiner] <--> B[Builder]
```

| Role | Was called | Talks to | Transforms… |
|------|------------|----------|-------------|
| **Problem Owner** | Problem Stater | Interpreter | a problem; validates the roadmap; gives feedback + continue/stop each iteration (the human) |
| **Interpreter** | Problem Stater Proxy | Owner, Analyst | problem → **roadmap of shippable iterations**; packages each **increment** back to the Owner |
| **Analyst** | Solver | Interpreter, Examiner | behaviour-to-implement → a crisp **behaviour** |
| **Examiner** | Verifier | Analyst, Builder | behaviour → **expectations**; judges **evidence** |
| **Builder** | Implementer | Examiner | expectations → code via **TDD** (test-first); proves each with **evidence** = a demonstrated run of the real system (not "tests pass") |

Names state the *transformation* each node performs. "Solver"/"Verifier" were
renamed because they don't solve or verify code — the Builder solves; the Examiner
sets expectations and judges evidence.

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

All three rules live in **`topology.json`** — the single source of truth — and are
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

## Auditing a run

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
  adversarially. The Builder builds **test-first (TDD)**, and those tests double as
  the regression net EDD calls *stabilising* — but they are the Builder's discipline,
  distinct from the demonstrated evidence that governs correctness across the chain.
