# The Relay Method

### How a chain of specialized AI agents — each allowed to talk only to its neighbours — turns a vague human wish into working, audited software

---

## Summary

Most "AI coding" setups are a single model doing everything: it talks to you, designs the solution, writes the code, and tells you it's done. That works until it doesn't — and when it doesn't, you can't see *where* the reasoning went wrong, because it all happened inside one opaque conversation.

**The Relay Method** takes the opposite stance. It splits the work across a small chain of specialized agents, each with one job and one rule: **you may only talk to the agent on your left and the agent on your right.** A human problem flows down the chain, getting sharper at every step; working software and status flow back up. Every message between agents is a file on disk, appended to a single audit log you can replay line by line.

The result is a system where each handoff is a *translation* between levels of abstraction, where implementation detail physically cannot leak up to the human and the human's framing cannot leak down into the code, and where — months later — you can reconstruct exactly how "I want a 3D Tetris game" became a specific commit.

This article describes the method, each persona in the chain, how they communicate, and why the constraints are the point.

---

## The core idea: a bucket brigade for abstraction

Picture five stations in a line:

```
Owner (human)  ⇄  Interpreter  ⇄  Analyst  ⇄  Examiner  ⇄  Builder
└── live chat ──┘  └──────────── relay messages ────────────┘
```

Each arrow is an **edge**, and every edge is a translation to a different level of abstraction. Going down the chain, the same intent is progressively sharpened:

- The **Owner** has a problem, in plain human words.
- The **Interpreter** restates it as a *need to implement* — still in the Owner's language, never in solution terms.
- The **Analyst** reframes that need as an *observable behaviour* — what must be true, with no hint of *how*.
- The **Examiner** decomposes the behaviour into *expectations* — precise, checkable statements.
- The **Builder** writes code and produces *evidence* that each expectation holds.

The neighbours-only rule is not bureaucracy; it is the mechanism. Because the Builder can only speak to the Examiner, it can never leak file names and data structures up to the human. Because the Interpreter can only speak to the Analyst (downward) and the Owner (upward), it can never smuggle business framing into the code. Each role is forced to speak the vocabulary of its own edge — and that is exactly what keeps the abstraction levels clean.

There's a sixth participant who stands *outside* the line — the **Sentinel** — whose job is to make sure everyone honours their edge. More on them later.

---

## The personas

### 1. The Owner — the human with a problem

The Owner is you. You don't write code, you don't design the architecture, and you don't manage the agents. You **state a problem**, answer clarifying questions, approve a plan, and then gate each increment: continue, stop, or change course.

This is the quiet revolution of the method: your role shifts from *author* to *editor*. You are no longer producing the solution; you are evaluating proposals and steering. You speak to exactly one agent — the Interpreter — and only ever in the language of needs and outcomes.

### 2. The Interpreter — the Owner's voice inside the machine

The Interpreter is the bilingual diplomat. Upward, it speaks human: it asks you clarifying questions *before* planning (so ambiguity is resolved rather than assumed), proposes a **roadmap** of potentially-shippable iterations, presents finished **increments**, and asks whether to keep going. Downward, it hands the Analyst one **behaviour to implement** at a time — still expressed as a need ("the player should see the piece fall and lock at the bottom"), never as a design.

Crucially, the Interpreter is the only edge that is a *live conversation*: you type in its window and it talks back. Everything below it happens through files, asynchronously, while you watch.

### 3. The Analyst — from need to observable behaviour

The Analyst is the translator that strips solutions out of needs. It receives a behaviour-to-implement and reframes it as a pure **behaviour**: an actor, an observable outcome, and explicit boundaries — with every trace of *how* removed.

"Build a falling piece" becomes: *"Without any user interaction, the piece descends by exactly one cell at a steady, observable cadence; it stays aligned to the grid at each step; this covers descent through empty space only — what happens at the floor is a separate behaviour."*

Notice what's absent: no mention of timers, frames, data structures, or languages. The Analyst answers **what must be observably true**, and hands that to the Examiner. When status comes back up, the Analyst translates it the other way — reporting to the Interpreter only *which problem was solved*, never expectations or tests.

### 4. The Examiner — expectations, not assertions

The Examiner is where the method gets its rigor, and it runs on **Expectation-Driven Development** (EDD) — a practice for human–AI collaboration in which correctness is established by stating expectations in plain language and then demanding *evidence* that they hold, rather than by anyone declaring "done." (See the original write-up: [*Expectation-Driven Development*](https://a4al6a.substack.com/p/expectation-driven-development-a).)

The Examiner takes a behaviour and decomposes it into a **set of expectations** — `E1..En` — each a precise, checkable statement of what must be true, plus an end-to-end *integration* expectation that ties them together. For the falling piece: *"E1: the piece's vertical position decreases by exactly one cell per tick. E2: between ticks it is stationary. E3: it never leaves the grid…"* Still no "how" — expectations describe outcomes, not mechanisms.

It sends these to the Builder and waits for **evidence**. Then it judges. In EDD terms, the Examiner insists on *executed* evidence — real runs, real output, real measured values — over *generative* evidence, where the AI merely narrates what it believes would happen. If an expectation is unmet or the evidence is unconvincing, the Examiner returns a **verdict** saying what still fails, and the Builder iterates. This `expectation → evidence → verdict` loop repeats until every expectation is satisfied.

The striking consequence, straight from EDD: **the code may carry no unit tests at all.** The expectations and their evidence — recorded permanently in the audit log — *are* the proof of correctness. The Examiner is the test oracle, and the ledger is the test report.

### 5. The Builder — the only one who touches code

The Builder is the implementer, and the only agent that writes and runs real code. It receives expectations from the Examiner and produces **evidence** that they now hold: it builds, it runs the program, it captures screenshots and measured outputs, and it reports back **which expectations are fulfilled** — and *only* that. It is forbidden from leaking implementation detail upward; "I used a hash map keyed by cell coordinates" is a contract violation. The correct report is "E2 now holds; here is the run that shows it."

The Builder talks to no one but the Examiner. It doesn't know who the Owner is or what the roadmap looks like. It knows expectations, and it knows how to produce evidence. That narrowness is its strength.

### 6. The Sentinel — the auditor outside the chain

The five-station line is a closed pipeline, but pipelines drift. Over a long run, the Builder starts slipping code internals into its evidence; the Interpreter starts smuggling implementation hints into a behaviour. Who watches the contracts?

The **Sentinel** does. It stands outside the chain — not a link in it — and is the one party allowed to read the *entire* conversation. It periodically audits every message against its edge's contract (does this builder→examiner message leak implementation detail? does this analyst→examiner message prescribe a solution?), writes findings to an audit log, and — by design — may message any agent directly with an `advisory`, a `warning`, or a `directive` to pull it back on-contract. In practice it earns its keep: it will catch the Builder naming functions in its evidence and the Interpreter drifting into solutioning — corrections a single mega-prompt would never surface.

The Sentinel never blocks or rewrites messages. It observes, reports, and nudges. It is the method's conscience.

---

## How they communicate: files you can replay

There is no server and no message broker. Every message is a small JSON file written to a mailbox directory, and simultaneously appended as one line to a single, gap-free, append-only **ledger**. That ledger is the system of record. You can replay the entire conversation message by message, filter by agent, and trace any decision's full lineage — from the Owner's first sentence to a specific commit — because every message carries the id of the message it replies to.

The rules live in one place: a topology file that fixes **which edges exist** and **which message types are legal on each edge**. A wrong neighbour or a wrong message type is rejected before anything is written. This is "who-talks-to-whom" enforced as data, not as etiquette.

The message vocabulary mirrors the abstraction ladder:

- **Owner ↔ Interpreter:** `problem`, `clarification`, `roadmap`, `roadmap-verdict`, `increment`, `continue-query`, `feedback`, `result`, `question`.
- **Interpreter → Analyst:** `behaviour-to-implement`.
- **Analyst → Examiner:** `behaviour`.
- **Examiner → Builder:** `expectation`, `verdict`.
- **Builder → Examiner:** `evidence`.
- **Examiner → Analyst → Interpreter:** `behaviour-status` (climbing back up, re-translated at each step).
- **Sentinel → any agent:** `advisory`, `warning`, `directive`.

### The rhythm of one behaviour

```
Interpreter --behaviour-to-implement--> Analyst
Analyst     --behaviour-------------->   Examiner
Examiner    --expectation------------>   Builder    (E1..En + an integration expectation)
Builder     --evidence--------------->   Examiner
Examiner    --verdict (if unmet)----->   Builder    ⟲ loop until every expectation holds
Examiner    --behaviour-status------->   Analyst
Analyst     --behaviour-status------->   Interpreter
Interpreter --increment + continue?-->   Owner
```

Each agent runs in its own session and stays idle — costing nothing — until a tiny dispatcher notices a message waiting in its inbox and wakes it. Work flows by itself; the human only re-enters at the gates.

---

## Why the constraints are the point

It's tempting to see the neighbours-only rule and the per-edge vocabularies as friction. They are the opposite — they are what make the system legible:

- **Clean abstraction boundaries by construction.** Detail cannot leak up; framing cannot leak down. The structure of the conversation enforces separation of concerns better than any code review.
- **A complete, tamper-evident audit trail.** The ledger is append-only with a gap-free sequence, so a missing or out-of-order message is itself a signal. Commit it alongside the code and you have a permanent record of *how* the software was produced, not just *what* was produced.
- **Resilience.** Because all state is inspectable files, a stuck chain is just a message sitting in an inbox. A crash or restart loses only the running processes; relaunch the agents and they pick up exactly where they left off.
- **Specialization over a bigger brain.** The win isn't a smarter agent — it's a *team* of narrow agents communicating under strict, auditable contracts.

We put it to the test by building **ThreeDeeBlocks**, a 3D Tetris clone compiled to WebAssembly, end to end. The swarm worked through dozens of behaviours largely autonomously, leaving a complete trail of every expectation, every piece of executed evidence, and every course-correction — including the Sentinel flagging contract drift in real time, and the Interpreter surfacing an honest engineering substitution (a different toolchain) to the Owner for sign-off rather than burying it.

---

## Conclusions

The Relay Method is a bet that the path to trustworthy AI-built software is not a single, ever-more-capable agent, but a **structured conversation** between modest ones — constrained so tightly that the structure itself does much of the quality work.

Three ideas do the heavy lifting:

1. **A linear chain of single-purpose agents**, each speaking only to its neighbours, so every handoff is a clean translation across abstraction levels.
2. **Expectation-Driven Development at the core**, so correctness is proven by plain-language expectations and executed evidence rather than asserted — sometimes with no unit tests in the code at all.
3. **A file-based, append-only audit trail plus an external Sentinel**, so the whole thing is inspectable, replayable, and self-policing.

The human comes out changed too: not an author hunched over a keyboard, but an editor who states problems, reviews increments, and decides. If you've ever wished you could *see* how an AI arrived at a piece of code — and trust that it actually does what it claims — the Relay Method is one concrete way to get there.

---

## References & further reading

- **Expectation-Driven Development** — the practice the Examiner is built on (expectations, executed vs. generative evidence, stabilizing into tests): https://a4al6a.substack.com/p/expectation-driven-development-a
- **Conway's Law** (Melvin Conway, 1968) — that systems mirror the communication structure of the organizations that build them; the Relay Method designs that communication structure deliberately.
- **Behaviour-Driven Development** (Dan North) — a precursor in spirit: describing behaviour in structured natural language. EDD relaxes its framework constraints for human–AI collaboration.
- **The test oracle** — the classic testing notion of an authority that decides whether an output is correct; in this method, the Examiner plays that role and the ledger records its verdicts.
- **Continuous Delivery / Modern Software Engineering** (Dave Farley) — on working in small, verifiable increments behind explicit gates, echoed here in the roadmap-and-increment rhythm.
