#!/usr/bin/env python3
"""Watchdog for the iTerm relay dispatcher — keep chain delivery alive.

The dispatcher (iterm_dispatch.py) is the single point that wakes chain windows when
they have mail. It can die on a transient failure — e.g. an `osascript` call to read a
session hangs past its 20s timeout and raises, killing the process (this has happened).
When it's down, chain mail stops being delivered and the swarm silently stalls with
messages piling up in inboxes.

This watchdog polls for a live dispatcher bound to a given RELAY_HOME and restarts it
when it's missing. It uses only `ps` + process spawning (no AppleScript), so it is far
less likely to die than what it guards. Every check-result and restart is logged to
<RELAY_HOME>/dispatch-watchdog.log.

  python3 relay/dispatch_watchdog.py --home /path/to/project/.relay [--interval 60]
  python3 relay/dispatch_watchdog.py --home ... --check-only   # report, never restart
  python3 relay/dispatch_watchdog.py --home ... --once         # one check, then exit

Run it alongside the dispatcher (leave running):
  python3 relay/dispatch_watchdog.py --home <project>/.relay &
"""
import argparse
import os
import pathlib
import subprocess
import time
from datetime import datetime

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
DISPATCHER = SCRIPT_DIR / "iterm_dispatch.py"


def stamp():
    # Local wall-clock, for a human reading the log.
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def dispatcher_pids(home):
    """PIDs of running iterm_dispatch.py processes bound to this RELAY_HOME.

    Matches on both the script name and the home path so it never confuses a
    dispatcher for another swarm (each swarm has its own RELAY_HOME)."""
    home = str(home)
    out = subprocess.run(["ps", "-Ao", "pid=,args="], capture_output=True, text=True).stdout
    pids = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        pid, _, args = line.partition(" ")
        if "iterm_dispatch.py" in args and home in args:
            try:
                pids.append(int(pid))
            except ValueError:
                pass
    return pids


def start_dispatcher(home, dispatch_log):
    """Relaunch the dispatcher, detached so it outlives this watchdog, appending its
    output to the same dispatch.log the operator already tails."""
    log = open(dispatch_log, "a")
    p = subprocess.Popen(
        ["python3", str(DISPATCHER), "--home", str(home)],
        stdout=log, stderr=log, start_new_session=True,
        env={**os.environ, "PATH": "/opt/homebrew/bin:" + os.environ.get("PATH", "")},
    )
    return p.pid


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--home", default=None, help="RELAY_HOME of the swarm to guard")
    ap.add_argument("--interval", type=float, default=60.0, help="seconds between checks (default: 60)")
    ap.add_argument("--check-only", action="store_true", help="report health, never restart")
    ap.add_argument("--once", action="store_true", help="check once and exit")
    a = ap.parse_args()

    home = pathlib.Path(a.home or os.environ.get("RELAY_HOME") or SCRIPT_DIR).resolve()
    dispatch_log = home / "dispatch.log"
    guard_log = home / "dispatch-watchdog.log"

    def log(msg):
        line = f"{stamp()} {msg}"
        print(line, flush=True)
        try:
            with open(guard_log, "a") as f:
                f.write(line + "\n")
        except OSError:
            pass

    log(f"watchdog started (home={home}, every {a.interval}s"
        + (", check-only" if a.check_only else "") + ")")

    restarts = 0
    while True:
        pids = dispatcher_pids(home)
        if pids:
            if len(pids) > 1:
                log(f"WARN: {len(pids)} dispatchers running for this home: {pids} (expected 1)")
            # else: healthy, stay quiet to keep the log signal-rich.
        elif a.check_only:
            log("dispatcher DOWN (check-only: not restarting)")
        else:
            pid = start_dispatcher(home, dispatch_log)
            restarts += 1
            log(f"dispatcher DOWN -> restarted (new pid {pid}, restart #{restarts})")
        if a.once:
            break
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
