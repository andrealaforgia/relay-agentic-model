#!/usr/bin/env python3
"""Git-diff trigger for the DOCUMENTER — iTerm2, UUID-addressed.

The iTerm counterpart to docwatch.py (which targets tmux). Watches the PROJECT's
git history and, when the Builder has integrated new commits past the Documenter's
cursor, writes the diff to <RELAY_HOME>/docwatch/diff.patch and wakes the
Documenter's iTerm session — but never while it is mid-pass, and it retries a
dropped wake on the next scan. The session is addressed by its stable iTerm session
UUID (from iterm/windows.json), NOT a window id, since window ids get recycled when
a window closes and would misdeliver a wake.

Coordination (same as docwatch.py): the Documenter records the last-documented
commit sha in <RELAY_HOME>/docwatch/.last; this script compares it to the project's
HEAD and only acts when they differ.

  python3 relay/iterm_docwatch.py --home /path/to/project/.relay [--interval 30]
  python3 relay/iterm_docwatch.py --home /path/to/project/.relay --dry-run --once
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

WAKE = ("The project has new commits — read $RELAY_HOME/docwatch/diff.patch for the "
        "changes since you last looked, update the end-user docs site per your "
        "playbook and project overrides (existing Astro site, end-user language only), "
        "commit AND push, then advance $RELAY_HOME/docwatch/.last to the project HEAD, "
        "and stop.")


def osa(script: str) -> str:
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=20)
    return r.stdout


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
        return (home / "docwatch" / ".last").read_text().strip() or None
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
    ap.add_argument("--home", default=None, help="RELAY_HOME of the swarm")
    ap.add_argument("--project", default=None, help="git repo to watch (default: RELAY_HOME's parent)")
    ap.add_argument("--interval", type=float, default=30.0, help="seconds between checks")
    ap.add_argument("--dry-run", action="store_true", help="print instead of waking")
    ap.add_argument("--once", action="store_true", help="check once and exit")
    a = ap.parse_args()

    home, project, win_map = resolve(a.home, a.project)
    sid = win_map.get("documenter")
    if not sid:
        raise SystemExit("no 'documenter' entry in iterm/windows.json — launch its window first")

    last_wake = 0.0
    warned = False
    print(f"iterm docwatch (UUID-addressed, retry-until-documented) watching {project} (.git), "
          f"every {a.interval}s" + (" [dry-run]" if a.dry_run else ""), flush=True)
    while True:
        h = head(project)
        if h is not None:
            base = last_seen(home)
            if base != h:
                # Stage the diff so it's ready the instant the Documenter is woken.
                (home / "docwatch").mkdir(parents=True, exist_ok=True)
                rng = f"{base or EMPTY_TREE}..{h}"
                (home / "docwatch" / "diff.patch").write_text(git(project, "diff", rng).stdout)
                n_changed = len(git(project, "diff", "--name-status", rng).stdout.strip().splitlines())

                contents = session_contents(sid)
                if contents is None:
                    if not warned:
                        print(f"!! documenter session {sid} is GONE — relaunch + re-map windows.json", flush=True)
                        warned = True
                elif (time.monotonic() - last_wake) >= COOLDOWN and not is_busy(contents):
                    warned = False
                    print(f"HEAD {h[:8]} (last {str(base)[:8]}) — {n_changed} files changed  ->  wake documenter",
                          flush=True)
                    wake_session(sid, a.dry_run)
                    last_wake = time.monotonic()
        if a.once:
            break
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
