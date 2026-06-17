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

# Give claude time to start, then tell each window its role.
sleep "$START_DELAY"
for r in "${ROLES[@]}"; do
  tmux send-keys -t "$SWARM:$r" \
    "Read \$RELAY_AGENTS/$r.md and act as the $r for this project. Use the relay CLI as: node \"\$RELAY_TOOL\" <cmd> (your data root is \$RELAY_HOME). When you receive a 'drain your inbox' message, process every pending message per the playbook, then stop." Enter
done

cat <<EOF

Launched swarm '$SWARM'
  project   : $PROJECT_DIR
  RELAY_HOME: $RELAY_HOME
  windows   : ${ROLES[*]}

Attach:        tmux attach -t $SWARM        (switch windows: Ctrl-b then 1..4)
Dispatcher:    python3 $TOOL_DIR/dispatch.py --session $SWARM --home '$RELAY_HOME'
Begin:         talk to the 'interpreter' window as the Owner.
Audit:         RELAY_HOME='$RELAY_HOME' node "$RELAY_TOOL" show
EOF
