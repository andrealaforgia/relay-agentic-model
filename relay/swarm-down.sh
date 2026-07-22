#!/bin/bash
# Tear down an agentic relay swarm: stops the 5 communication daemons and
# closes the 7 role windows for the given project.
#
#   relay/swarm-down.sh <swarm-name> <project-dir> [--keep-windows]
#
# Safe to run on a swarm that's already partially or fully down (or that was
# never started) — nothing to stop/close is not an error.
set -uo pipefail

if [ $# -lt 2 ]; then
  echo "usage: $0 <swarm-name> <project-dir> [--keep-windows]" >&2
  exit 1
fi

TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SWARM_NAME="$1"
PROJECT_DIR="$(python3 -c "import os,sys; print(os.path.abspath(os.path.expanduser(sys.argv[1])))" "$2")"
RELAY_HOME="$PROJECT_DIR/.relay"
KEEP_WINDOWS=false
[ "${3:-}" = "--keep-windows" ] && KEEP_WINDOWS=true

echo "== stopping daemons for $SWARM_NAME ($RELAY_HOME) =="
if pkill -f "relay/(iterm_dispatch|dispatch_watchdog|iterm_sentinel|iterm_qa|iterm_warden)\.py --home $RELAY_HOME"; then
  echo "daemons stopped"
else
  echo "no daemons were running"
fi

if [ "$KEEP_WINDOWS" = true ]; then
  echo "== leaving windows open (--keep-windows) =="
elif [ -d "$RELAY_HOME" ]; then
  echo "== closing role windows =="
  python3 "$TOOL_DIR/iterm_close.py" --home "$RELAY_HOME"
fi

echo
echo "swarm '$SWARM_NAME' is down: $PROJECT_DIR"
