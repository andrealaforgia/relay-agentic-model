# Running a swarm on a new problem

End-to-end instructions for driving one problem through a four-agent swarm
(Interpreter → Analyst → Examiner → Builder) using the filesystem-mailbox relay
and the tmux push dispatcher.

## Prerequisites (once)

- `tmux`, `node`, and `python3` on your PATH (`tmux -V`, `node -v`, `python3 -V`).
- `claude` installed and logged in.
- This repo cloned. For convenience, point a shortcut at the relay tooling:

  ```bash
  export EDD=/Users/andrealaforgia/dev/agentic-working-model/relay
  ```

## 1. Pick the project

The swarm builds into a **project directory** (the Builder writes real code there).
It can be a new empty folder or an existing codebase:

```bash
mkdir -p ~/code/url-shortener        # or cd into an existing project
```

Choose a **swarm name** — it becomes the tmux session and must be unique among
swarms you're running at the same time (e.g. `urlshort`).

## 2. Launch the swarm

```bash
bash "$EDD/launch.sh" urlshort ~/code/url-shortener
```

This:
- scaffolds the swarm's private state in `~/code/url-shortener/.relay`
  (`RELAY_HOME`: its own ledger, mailboxes, lock);
- opens a tmux session `urlshort` with four windows — `interpreter`, `analyst`,
  `examiner`, `builder` — each running `claude` in the project dir;
- primes each window with its role playbook after a short boot delay.

If a window's kickoff looks mistyped (slow boot), relaunch with a longer delay:
`START_DELAY=12 bash "$EDD/launch.sh" urlshort ~/code/url-shortener`.

## 3. Start the dispatcher (separate terminal)

```bash
python3 "$EDD/dispatch.py" --session urlshort --home ~/code/url-shortener/.relay
```

It watches this swarm's ledger and wakes the right window whenever a message
arrives — so the Analyst/Examiner/Builder sit idle (free) until they have work.
Leave it running. It prints each `#seq from > to [type] -> wake <role>` as it fires.

## 4. Attach and verify

```bash
tmux attach -t urlshort
```

Switch windows with `Ctrl-b` then `1`–`4` (or `Ctrl-b w` to pick from a list).
Check each of windows 2–4 shows Claude having read its playbook and waiting. The
first time each agent runs a relay command Claude will ask permission to run
`node` — choose **always allow** so the dispatcher's wakes aren't blocked.

## 5. State the problem (you are the Owner)

Go to the **interpreter** window (`Ctrl-b 1`) and describe what you want, in plain
language:

> I want a command-line URL shortener: given a long URL it returns a short code,
> and given the short code it returns the original URL.

## 6. Answer the Interpreter's questions

The Interpreter will **ask clarifying questions before planning** (storage?
persistence across runs? collision handling? custom aliases?). Answer them in the
same window. Don't expect work to start yet — this is the point where ambiguity
gets resolved instead of assumed.

## 7. Approve the roadmap

The Interpreter proposes a roadmap — an ordered set of *potentially shippable
iterations*. Read it. Reply with either:
- **approval** — e.g. "approved, go" — and it starts iteration 1; or
- **changes** — e.g. "merge 2 and 3, drop aliases for now" — and it re-proposes.

You just talk; the Interpreter records your verdict to the ledger itself.

## 8. Watch the cascade, then gate each iteration

Once approved, the Interpreter sends the first `behaviour-to-implement`. From here
it's automatic — watch the windows light up as the dispatcher wakes each agent:

```
interpreter → analyst : behaviour-to-implement
analyst     → examiner : behaviour
examiner    → builder  : expectation        (incl. an "it runs end-to-end" expectation)
builder     → examiner : evidence           (Builder writes code in the project, runs it)
examiner    → builder  : verdict            (loops until satisfied)
examiner    → analyst  : behaviour-status
analyst     → interpreter : behaviour-status
```

When the iteration is covered, the dispatcher wakes the **interpreter**, which
presents the **increment** to you and asks whether to continue. Reply in the
interpreter window with feedback and your decision (**continue** / **stop** /
re-plan). Repeat until you stop.

## 9. Audit anytime (any terminal)

```bash
export RELAY_HOME=~/code/url-shortener/.relay
node "$EDD/relay.mjs" show        # replay the whole conversation
node "$EDD/relay.mjs" verify      # topology + vocabulary + gap-free sequence
node "$EDD/relay.mjs" inbox --as examiner   # what any agent is waiting on
ls ~/code/url-shortener/.relay/mailbox/*/inbox/   # the chain at a glance
```

The Builder's actual output is in the project directory itself.

## 10. Finish / tear down

```bash
tmux kill-session -t urlshort     # close the agent windows
# stop the dispatcher with Ctrl-C in its terminal
```

The `.relay/ledger.jsonl` remains as the audit trail — commit it with the project
for a tamper-evident record of how the code was produced.

## Running another swarm at the same time

Just use a different swarm name and project dir; the two never share state:

```bash
bash "$EDD/launch.sh" notes ~/code/notes-app
python3 "$EDD/dispatch.py" --session notes --home ~/code/notes-app/.relay
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| An agent isn't reacting | `node "$EDD/relay.mjs" inbox --as <role>` (RELAY_HOME set). A message sitting there = it stalled; go to that window and type `process your inbox`. |
| A window's claude died | Restart `claude` in that window, re-send its kickoff (`Read $RELAY_AGENTS/<role>.md …`). Unacked inbox files are preserved, so it resumes. |
| Dispatcher fires but nothing wakes | Confirm `--session` matches the tmux session name and `--home` matches the project's `.relay`. |
| Kickoff text got mistyped on launch | `tmux kill-session -t <swarm>` and relaunch with a higher `START_DELAY`. |
| Constant permission prompts | In each window, "always allow" `node`; or add `node` to the project's allowed Bash commands. |
| Two swarms interfering | They must have distinct swarm names; each `launch.sh` uses its own `<project>/.relay`. |
