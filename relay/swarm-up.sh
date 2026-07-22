#!/bin/bash
# Launch (or relaunch) an agentic relay swarm: opens the 7 role windows and
# starts the 5 communication daemons, fully detached from this shell (they
# survive the terminal/session that launched them).
#
#   relay/swarm-up.sh <swarm-name> <project-dir>
#
# Idempotent: tears down any existing windows/daemons for that project dir
# first (via swarm-down.sh), then launches fresh. The ledger and mailboxes
# under <project-dir>/.relay are preserved across relaunches.
#
# Env:
#   START_DELAY   seconds to let claude boot before priming each window (default 15)
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "usage: $0 <swarm-name> <project-dir>" >&2
  exit 1
fi

TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SWARM_NAME="$1"
PROJECT_DIR="$(python3 -c "import os,sys; print(os.path.abspath(os.path.expanduser(sys.argv[1])))" "$2")"
RELAY_HOME="$PROJECT_DIR/.relay"

echo "== stopping any existing swarm for $PROJECT_DIR =="
"$TOOL_DIR/swarm-down.sh" "$SWARM_NAME" "$PROJECT_DIR"

echo
echo "== opening swarm windows =="
START_DELAY="${START_DELAY:-15}" python3 "$TOOL_DIR/iterm_launch.py" "$SWARM_NAME" "$PROJECT_DIR"

echo
echo "== starting communication daemons (detached) =="
nohup python3 "$TOOL_DIR/iterm_dispatch.py"    --home "$RELAY_HOME" >> "$RELAY_HOME/dispatch.log"          2>&1 & disown
nohup python3 "$TOOL_DIR/dispatch_watchdog.py" --home "$RELAY_HOME" >> "$RELAY_HOME/dispatch-watchdog.log" 2>&1 & disown
nohup python3 "$TOOL_DIR/iterm_sentinel.py"    --home "$RELAY_HOME" >> "$RELAY_HOME/sentinel.log"          2>&1 & disown
nohup python3 "$TOOL_DIR/iterm_qa.py"          --home "$RELAY_HOME" >> "$RELAY_HOME/qa-trigger.log"        2>&1 & disown
nohup python3 "$TOOL_DIR/iterm_warden.py"      --home "$RELAY_HOME" >> "$RELAY_HOME/warden-trigger.log"    2>&1 & disown

sleep 1
n=$(pgrep -f "relay/(iterm_dispatch|dispatch_watchdog|iterm_sentinel|iterm_qa|iterm_warden)\.py --home $RELAY_HOME" | wc -l | tr -d ' ')
echo
echo "swarm '$SWARM_NAME' is up: $PROJECT_DIR  ($n/5 daemons running)"
echo "shut down with: $TOOL_DIR/swarm-down.sh $SWARM_NAME $PROJECT_DIR"
