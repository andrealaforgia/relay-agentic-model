#!/usr/bin/env python3
"""Periodic trigger for the SENTINEL (Communication Auditor) — iTerm2, UUID-addressed.

Wakes the Sentinel's iTerm session when the ledger has grown past its audit cursor,
but never while it is mid-audit, and retries a dropped wake on the next scan. The
Sentinel session is identified by its stable iTerm session UUID (from
iterm/windows.json), NOT a window id — window ids get recycled when a window
closes, which could send a wake into a stranger's session.

  python3 relay/iterm_sentinel.py --home /path/to/project/.relay [--interval 45]
"""
import argparse
import json
import os
import pathlib
import subprocess
import time

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
NOTFOUND = "<<RELAY_SESSION_NOT_FOUND>>"

WAKE = ("Audit time — read the ledger from your cursor, judge each new message "
        "against the per-edge contracts in your playbook, append findings, advance "
        "the cursor, refresh report.md (and advise any offending agent if warranted), "
        "then stop.")

COOLDOWN = 15.0


def osa(script: str) -> str:
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=20)
    return r.stdout


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def resolve(arg_home):
    home = pathlib.Path(arg_home or os.environ.get("RELAY_HOME") or SCRIPT_DIR).resolve()
    win_map = json.loads((home / "iterm" / "windows.json").read_text())  # role -> session UUID
    return home, home / "ledger.jsonl", home / "audit" / ".cursor", win_map


def ledger_len(ledger):
    return len(ledger.read_text().splitlines()) if ledger.exists() else 0


def cursor_val(cursor):
    try:
        return int(cursor.read_text().strip())
    except (FileNotFoundError, ValueError, OSError):
        return 0


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
    if "for agents" in tail or "? for shortcuts" in tail:
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
    ap.add_argument("--home", default=None)
    ap.add_argument("--interval", type=float, default=45.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()

    home, ledger, cursor, win_map = resolve(a.home)
    sid = win_map.get("sentinel")
    if not sid:
        raise SystemExit("no 'sentinel' entry in iterm/windows.json")
    last_wake = 0.0
    warned = False
    print(f"iterm sentinel trigger (UUID-addressed, retry-until-audited) watching {ledger}, "
          f"every {a.interval}s" + (" [dry-run]" if a.dry_run else ""), flush=True)
    while True:
        n, c = ledger_len(ledger), cursor_val(cursor)
        if n > c:
            contents = session_contents(sid)
            if contents is None:
                if not warned:
                    print(f"!! sentinel session {sid} is GONE — relaunch + re-map windows.json", flush=True)
                    warned = True
            elif (time.monotonic() - last_wake) >= COOLDOWN and not is_busy(contents):
                print(f"ledger at {n}, audited through {c}  ->  wake sentinel", flush=True)
                wake_session(sid, a.dry_run)
                last_wake = time.monotonic()
        if a.once:
            break
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
