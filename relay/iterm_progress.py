#!/usr/bin/env python3
"""Periodic progress heartbeat for the INTERPRETER — iTerm2, UUID-addressed.

Wakes the Interpreter's session on a fixed interval (default every 5 minutes) with
a "Progress check-in", asking it to compute % done from the checklist it maintains
at <RELAY_HOME>/interpreter/roadmap.md ([x] lines vs total) and report it to the
Owner concisely in chat. Unlike the Reaper/QA/Warden/Courier triggers, this one is
NOT gated on anything having changed — it's a heartbeat, so the Owner sees project
state at a steady cadence rather than only when a message happens to arrive.

It mirrors iterm_dispatch.py's UUID session addressing and busy-detection — the
Interpreter's window is shared with the live human Owner conversation, so this
never writes into it mid-turn (same "esc to interrupt" / "for agents" / etc. check
the dispatcher and every other trigger use).

Polls more often than the interval itself so a busy session doesn't push the next
check-in a full extra interval late — once `--interval` seconds have elapsed since
the last wake, every subsequent poll tries again until the session goes idle.

  python3 relay/iterm_progress.py --home /path/to/project/.relay [--interval 300]
  python3 relay/iterm_progress.py --home /path/to/project/.relay --dry-run --once
"""
import argparse
import json
import os
import pathlib
import subprocess
import time

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
NOTFOUND = "<<RELAY_SESSION_NOT_FOUND>>"

WAKE = ("Progress check-in — read your persisted roadmap at "
        "$RELAY_HOME/interpreter/roadmap.md, compute % done ([x] lines vs total), "
        "and report it to the Owner concisely in chat: % done, which iteration is "
        "in flight, anything currently blocking. Record it too: node \"$RELAY_TOOL\" "
        "send --as interpreter --to owner --type progress --body \"...\". Then stop "
        "and wait for the next check-in.")


def osa(script: str) -> str:
    # Never let a transient AppleScript hang kill the watcher: a timed-out or failed
    # osascript call returns "" so the caller skips this tick and retries next poll.
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=20)
        return r.stdout
    except Exception:
        return ""


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def resolve(home_arg):
    home = pathlib.Path(home_arg or os.environ.get("RELAY_HOME") or SCRIPT_DIR).resolve()
    win_map = json.loads((home / "iterm" / "windows.json").read_text())  # role -> session UUID
    return home, win_map


def session_contents(sid):
    out = osa(f'''
tell application "iTerm"
  repeat with w in windows
    repeat with t in tabs of w
      repeat with s in sessions of t
        if (id of s) is "{sid}" then return contents of s
      end repeat
    end repeat
  end repeat
end tell
return "{NOTFOUND}"
''')
    return None if out.strip() == NOTFOUND else out


def is_busy(contents):
    tail = contents[-600:]
    if "esc to interrupt" in tail:
        return True
    if "for agents" in tail or "? for shortcuts" in tail or "shift+tab to cycle" in tail:
        return False
    return True


def wake_session(sid, dry):
    if dry:
        print(f"    [dry-run] wake session {sid}", flush=True)
        return
    osa(f'''
tell application "iTerm"
  repeat with w in windows
    repeat with t in tabs of w
      repeat with s in sessions of t
        if (id of s) is "{sid}" then
          tell s
            write text "{esc(WAKE)}" newline NO
            delay 0.5
            write text ""
          end tell
          return "ok"
        end if
      end repeat
    end repeat
  end repeat
end tell
''')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--home", default=None, help="RELAY_HOME of the swarm")
    ap.add_argument("--interval", type=float, default=300.0, help="seconds between check-ins (default: 300 = 5 min)")
    ap.add_argument("--dry-run", action="store_true", help="print instead of waking")
    ap.add_argument("--once", action="store_true", help="check once and exit")
    a = ap.parse_args()

    home, win_map = resolve(a.home)
    sid = win_map.get("interpreter")
    if not sid:
        raise SystemExit("no 'interpreter' entry in iterm/windows.json — launch its window first")

    poll = min(15.0, a.interval)
    last_wake = 0.0
    warned = False
    print(f"iterm progress heartbeat (UUID-addressed, unconditional) for interpreter, "
          f"every {a.interval}s" + (" [dry-run]" if a.dry_run else ""), flush=True)
    while True:
        if (time.monotonic() - last_wake) >= a.interval:
            contents = session_contents(sid)
            if contents is None:
                if not warned:
                    print(f"!! interpreter session {sid} is GONE — relaunch + re-map windows.json", flush=True)
                    warned = True
            elif is_busy(contents):
                pass  # retry next poll tick, don't reset last_wake — catch up as soon as idle
            else:
                warned = False
                print("check-in due  ->  wake interpreter", flush=True)
                wake_session(sid, a.dry_run)
                last_wake = time.monotonic()
        if a.once:
            break
        time.sleep(poll)


if __name__ == "__main__":
    main()
