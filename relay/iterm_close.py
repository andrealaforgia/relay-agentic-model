#!/usr/bin/env python3
"""Close every iTerm window belonging to a swarm (by session UUID in windows.json).

Kills the process attached to each session's tty *before* closing its window,
so iTerm doesn't pop up a "still running, close anyway?" confirmation dialog
that would hang an unattended script. Tolerant of a missing windows.json and
of sessions/windows that are already gone.

  python3 relay/iterm_close.py --home /path/to/project/.relay
"""
import argparse
import json
import pathlib
import subprocess

NOTFOUND = "<<RELAY_SESSION_NOT_FOUND>>"


def osa(script: str) -> str:
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=20)
        return r.stdout.strip()
    except Exception:
        return ""


def session_tty(sid: str):
    out = osa(f'''
tell application "iTerm"
  repeat with w in windows
    repeat with t in tabs of w
      repeat with s in sessions of t
        if (id of s) is "{sid}" then return tty of s
      end repeat
    end repeat
  end repeat
end tell
return "{NOTFOUND}"
''')
    return None if out == NOTFOUND or out == "" else out


def close_session(sid: str) -> str:
    out = osa(f'''
tell application "iTerm"
  repeat with w in windows
    repeat with t in tabs of w
      repeat with s in sessions of t
        if (id of s) is "{sid}" then
          close w
          return "closed"
        end if
      end repeat
    end repeat
  end repeat
end tell
return "{NOTFOUND}"
''')
    return "already gone" if out in (NOTFOUND, "") else out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--home", required=True, help="RELAY_HOME of the swarm to close")
    a = ap.parse_args()
    home = pathlib.Path(a.home).resolve()
    wf = home / "iterm" / "windows.json"
    if not wf.exists():
        print("no windows.json — nothing to close")
        return
    win_map = json.loads(wf.read_text())
    for role, sid in win_map.items():
        tty = session_tty(sid)
        if tty:
            dev = tty.rsplit("/", 1)[-1]  # e.g. ttys009
            subprocess.run(["pkill", "-9", "-t", dev], capture_output=True)
        result = close_session(sid)
        print(f"{role}: {sid} -> {result}")


if __name__ == "__main__":
    main()
