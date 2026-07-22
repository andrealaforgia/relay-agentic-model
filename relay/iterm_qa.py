#!/usr/bin/env python3
"""Periodic trigger for the QA test-design reviewer — iTerm2, UUID-addressed.

Wakes the QA session about every 10 minutes when the project has new commits since
QA's last review, asking it to read the staged diff, review the changed tests with
the alf-test-design-reviewer agent, compute the Farley Index, and send the review to
the Builder over the qa>builder edge.

It mirrors iterm_docwatch.py (git-diff staging + cursor) and iterm_sentinel.py (UUID
session addressing, busy-detection, retry-until-done). The diff since QA last looked
is staged to <RELAY_HOME>/qa/diff.patch; QA advances <RELAY_HOME>/qa/.last after each
review. Change-gated: if HEAD == .last there is nothing new, so QA is left idle
(no token waste) — the ~10 min interval is the *cap* on cadence, not a blind timer.

  python3 relay/iterm_qa.py --home /path/to/project/.relay [--interval 600]
  python3 relay/iterm_qa.py --home /path/to/project/.relay --dry-run --once
"""
import argparse
import json
import os
import pathlib
import subprocess
import time

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"  # git's well-known empty tree
NOTFOUND = "<<RELAY_SESSION_NOT_FOUND>>"
COOLDOWN = 15.0

WAKE = ("QA time — read the staged diff at $RELAY_HOME/qa/diff.patch, identify the "
        "TEST files it changes, review their design with the alf-test-design-reviewer "
        "agent, compute the Farley Index, and judge it against the floor in your "
        "playbook. Send the result to the builder over qa>builder (type test-review, "
        "or type warning if it falls below the floor). Then append to "
        "$RELAY_HOME/qa/farley-history.jsonl, advance $RELAY_HOME/qa/.last to the "
        "project HEAD, and stop.")


def osa(script: str) -> str:
    # Never let a transient AppleScript hang kill the watcher: a timed-out or failed
    # osascript call returns "" so the caller skips this tick and retries next loop.
    # "" reads as an unknown/busy session (not a gone one), so no false "session GONE".
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=20)
        return r.stdout
    except Exception:
        return ""


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def resolve(home_arg, project_arg):
    home = pathlib.Path(home_arg or os.environ.get("RELAY_HOME") or SCRIPT_DIR).resolve()
    # RELAY_HOME is conventionally <project>/.relay; default the project to its parent.
    project = pathlib.Path(project_arg).resolve() if project_arg else home.parent
    win_map = json.loads((home / "iterm" / "windows.json").read_text())  # role -> session UUID
    return home, project, win_map


def git(project, *args):
    return subprocess.run(["git", "-C", str(project), *args], capture_output=True, text=True)


def head(project):
    r = git(project, "rev-parse", "HEAD")
    return r.stdout.strip() if r.returncode == 0 else None


def last_seen(home):
    try:
        return (home / "qa" / ".last").read_text().strip() or None
    except FileNotFoundError:
        return None


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
    ap.add_argument("--project", default=None, help="git repo to watch (default: RELAY_HOME's parent)")
    ap.add_argument("--interval", type=float, default=600.0, help="seconds between checks (default: 600 = 10 min)")
    ap.add_argument("--dry-run", action="store_true", help="print instead of waking")
    ap.add_argument("--once", action="store_true", help="check once and exit")
    a = ap.parse_args()

    home, project, win_map = resolve(a.home, a.project)
    sid = win_map.get("qa")
    if not sid:
        raise SystemExit("no 'qa' entry in iterm/windows.json — launch its window first")

    last_wake = 0.0
    warned = False
    print(f"iterm qa trigger (UUID-addressed, retry-until-reviewed) watching {project} (.git), "
          f"every {a.interval}s" + (" [dry-run]" if a.dry_run else ""), flush=True)
    while True:
        h = head(project)
        if h is not None:
            base = last_seen(home)
            if base != h:
                # Stage the diff since QA last looked, so it's ready the instant QA wakes.
                (home / "qa").mkdir(parents=True, exist_ok=True)
                rng = f"{base or EMPTY_TREE}..{h}"
                (home / "qa" / "diff.patch").write_text(git(project, "diff", rng).stdout)
                n_changed = len(git(project, "diff", "--name-status", rng).stdout.strip().splitlines())

                contents = session_contents(sid)
                if contents is None:
                    if not warned:
                        print(f"!! qa session {sid} is GONE — relaunch + re-map windows.json", flush=True)
                        warned = True
                elif (time.monotonic() - last_wake) >= COOLDOWN and not is_busy(contents):
                    warned = False
                    print(f"HEAD {h[:8]} (last {str(base)[:8]}) — {n_changed} files changed  ->  wake qa", flush=True)
                    wake_session(sid, a.dry_run)
                    last_wake = time.monotonic()
        if a.once:
            break
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
