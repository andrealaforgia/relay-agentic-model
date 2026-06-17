# Interpreter playbook (the live-session role)

**Core correction:** the Owner↔Interpreter edge runs in the **live Claude session**,
not in a workflow. Claude plays the Interpreter when facing the Owner. Only the
human-free relay (Analyst→Examiner→Builder) is dispatched to a background workflow.
This is what gives the Owner visible, interactive participation — and an audit
ledger that matches what was said on screen.

## Steps

### 0. Clarify — MANDATORY, before any planning
The Interpreter must not invent assumptions silently. Before proposing a roadmap it
asks the Owner about every material ambiguity in the problem (semantics, scope,
inputs/outputs, success criteria, what's explicitly out of scope). Ask in the chat
(use crisp multiple-choice where it helps). Proceed only once the ambiguities that
would change the plan are resolved. Record each as `interpreter>owner:question` and
the reply as `owner>interpreter:clarification` in the ledger.

### 1. Roadmap — co-authored, then approved
Draft the slices (optionally using the workflow's `mode:"roadmap"` as a drafting
aid), but present them **in the chat** and revise *with* the Owner until they
explicitly approve. Record the approval as `owner>interpreter:roadmap-verdict`.

### 2. Per iteration — dispatch, then deliver
Dispatch the iteration to the relay (`mode:"iteration"`, background workflow). When
it returns, append its messages to the ledger and **show the Owner** the delivered
increment in the chat (`interpreter>owner:increment`), then ask plainly whether to
continue (`continue-query`). The Owner replies with `feedback` + `decision`.

### 3. Loop
Feedback may reshape the remaining roadmap (re-draft in chat, Step 1). Continue,
re-plan, or stop on the Owner's word.

## Visibility contract
- Every Owner-facing message is shown in the chat **and** appended to
  `ledger/ledger.jsonl` via `ledger.mjs` — the chat and the audit trail are the
  same conversation.
- The relay's internal messages are appended after each dispatch; replay any time
  with `node ledger.mjs show`.

## Folded-in fix (from the first demo)
The Examiner must author an **iteration-level integration expectation** ("the
increment runs end-to-end and satisfies the iteration goal"), not only per-behaviour
expectations — otherwise every behaviour can pass while the increment doesn't run.
