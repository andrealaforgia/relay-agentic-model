#!/usr/bin/env bash
# Launch one EDD swarm in its own tmux session, isolated so you can run several
# at once on different projects.
#
#   relay/launch.sh <swarm-name> [project-dir]
#
#   <swarm-name>   tmux session name AND the swarm's identity (must be unique
#                  across concurrently running swarms).
#   [project-dir]  where the agents work (the Builder writes code here).
#                  Defaults to the current directory. The swarm's private state
#                  lives in <project-dir>/.relay (its RELAY_HOME).
#
# Each swarm is fully isolated: its own RELAY_HOME (ledger + mailboxes + lock)
# and its own tmux session. Two swarms never share state.
#
# After launching, in a SEPARATE terminal start that swarm's dispatcher:
#   python3 relay/dispatch.py --session <swarm-name> --home <project-dir>/.relay
set -euo pipefail

SWARM="${1:?usage: launch.sh <swarm-name> [project-dir]}"
PROJECT_DIR="$(cd "${2:-$PWD}" && pwd)"
TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # the relay/ folder
RELAY_TOOL="$TOOL_DIR/relay.mjs"
RELAY_HOME="$PROJECT_DIR/.relay"
START_DELAY="${START_DELAY:-6}"   # seconds to let claude boot before sending the kickoff
ROLES=(interpreter analyst examiner builder)

if tmux has-session -t "$SWARM" 2>/dev/null; then
  echo "tmux session '$SWARM' already exists. Pick another name or: tmux kill-session -t $SWARM" >&2
  exit 1
fi

# The Builder commits its work and docwatch reads the history, so the project
# must be a git repo.
if [[ ! -d "$PROJECT_DIR/.git" ]]; then
  git -C "$PROJECT_DIR" init -q && echo "git-initialised $PROJECT_DIR"
fi
# Keep the relay's own state ($PROJECT_DIR/.relay) out of the project history,
# so the Builder's commits and the Documenter's diff only ever see real code.
if ! grep -qsx '.relay/' "$PROJECT_DIR/.gitignore" 2>/dev/null; then
  printf '%s\n' '.relay/' >> "$PROJECT_DIR/.gitignore"
fi

# Scaffold this swarm's private state (idempotent).
RELAY_HOME="$RELAY_HOME" node "$RELAY_TOOL" init

# One window per role. Export the swarm's env, cd into the project, start claude.
first=1
for r in "${ROLES[@]}"; do
  if [[ $first == 1 ]]; then
    tmux new-session -d -s "$SWARM" -n "$r" -c "$PROJECT_DIR"
    first=0
  else
    tmux new-window -t "$SWARM" -n "$r" -c "$PROJECT_DIR"
  fi
  # env vars exported here are inherited by claude and by its Bash tool subprocesses
  tmux send-keys -t "$SWARM:$r" \
    "export RELAY_HOME='$RELAY_HOME' RELAY_TOOL='$RELAY_TOOL' RELAY_AGENTS='$TOOL_DIR/agents' && claude" Enter
done

# The Sentinel (Communication Auditor) — external to the chain, in its own window.
tmux new-window -t "$SWARM" -n sentinel -c "$PROJECT_DIR"
tmux send-keys -t "$SWARM:sentinel" \
  "export RELAY_HOME='$RELAY_HOME' RELAY_TOOL='$RELAY_TOOL' RELAY_AGENTS='$TOOL_DIR/agents' && claude" Enter

# Give claude time to start, then tell each window its role.
sleep "$START_DELAY"
for r in "${ROLES[@]}"; do
  tmux send-keys -t "$SWARM:$r" \
    "Read \$RELAY_AGENTS/$r.md and act as the $r for this project. Use the relay CLI as: node \"\$RELAY_TOOL\" <cmd> (your data root is \$RELAY_HOME). When you receive a 'drain your inbox' message, process every pending message per the playbook, then stop." Enter
done
tmux send-keys -t "$SWARM:sentinel" \
  "Read \$RELAY_AGENTS/sentinel.md and act as the Sentinel (Communication Auditor) for this swarm. Your data root is \$RELAY_HOME. When you receive an 'audit time' message, audit new ledger messages per the playbook, then stop." Enter

# Optional: the Documenter (end-user docs site). Enable with WITH_DOCUMENTER=1.
if [[ "${WITH_DOCUMENTER:-0}" == "1" ]]; then
  tmux new-window -t "$SWARM" -n documenter -c "$PROJECT_DIR"
  tmux send-keys -t "$SWARM:documenter" \
    "export RELAY_HOME='$RELAY_HOME' RELAY_TOOL='$RELAY_TOOL' RELAY_AGENTS='$TOOL_DIR/agents' && claude" Enter
  sleep "$START_DELAY"
  tmux send-keys -t "$SWARM:documenter" \
    "Read \$RELAY_AGENTS/documenter.md and act as the Documenter for this project. Your data root is \$RELAY_HOME. On first run scaffold the Docusaurus docs site; when you receive a 'new commits' message, update the end-user docs from the diff, then stop." Enter
fi

cat <<EOF

Launched swarm '$SWARM'
  project   : $PROJECT_DIR
  RELAY_HOME: $RELAY_HOME
  windows   : ${ROLES[*]} sentinel

Attach:        tmux attach -t $SWARM        (switch windows: Ctrl-b then 1..5)
Dispatcher:    python3 $TOOL_DIR/dispatch.py --session $SWARM --home '$RELAY_HOME'
Sentinel:      python3 $TOOL_DIR/sentinel.py  --session $SWARM --home '$RELAY_HOME'
Documenter:    WITH_DOCUMENTER=1 to add its window, then: python3 $TOOL_DIR/docwatch.py --session $SWARM --home '$RELAY_HOME'
Begin:         talk to the 'interpreter' window as the Owner.
Audit (rules): RELAY_HOME='$RELAY_HOME' cat '$RELAY_HOME/audit/report.md'
Audit (msgs):  RELAY_HOME='$RELAY_HOME' node "$RELAY_TOOL" show
EOF
