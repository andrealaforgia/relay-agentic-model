#!/usr/bin/env python3
"""Git-diff trigger for the DOCUMENTER.

Watches the project's git history and, when the Builder has integrated new commits,
wakes the Documenter's tmux window with the diff since it last looked — so the
end-user docs site stays in step with what's actually been built.

Coordination mirrors the Sentinel: the Documenter writes the last-documented commit
sha to <RELAY_HOME>/docwatch/.last; this script compares it to HEAD and only wakes
the window (after writing the diff to <RELAY_HOME>/docwatch/diff.patch) when they
differ.

  python3 relay/docwatch.py --session <swarm> --home <project>/.relay
  python3 relay/docwatch.py --home <project>/.relay --dry-run --once
"""
import argparse
import os
import pathlib
import subprocess

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"  # git's well-known empty tree
WAKE = ("The project has new commits — read $RELAY_HOME/docwatch/diff.patch and "
        "update the end-user docs site per your playbook, commit, then advance "
        "$RELAY_HOME/docwatch/.last.")


def resolve(home_arg, project_arg):
    home = pathlib.Path(home_arg or os.environ.get("RELAY_HOME") or SCRIPT_DIR).resolve()
    # RELAY_HOME is conventionally <project>/.relay; default the project to its parent.
    project = pathlib.Path(project_arg).resolve() if project_arg else home.parent
    return home, project


def git(project, *args):
    return subprocess.run(["git", "-C", str(project), *args],
                          capture_output=True, text=True)


def head(project):
    r = git(project, "rev-parse", "HEAD")
    return r.stdout.strip() if r.returncode == 0 else None


def last_seen(home):
    f = home / "docwatch" / ".last"
    try:
        return f.read_text().strip() or None
    except FileNotFoundError:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--session", default="edd", help="tmux session name")
    ap.add_argument("--home", default=None, help="RELAY_HOME of the swarm")
    ap.add_argument("--project", default=None, help="git repo to watch (default: RELAY_HOME's parent)")
    ap.add_argument("--interval", type=float, default=30.0, help="seconds between checks")
    ap.add_argument("--dry-run", action="store_true", help="print instead of send-keys")
    ap.add_argument("--once", action="store_true", help="check once and exit")
    a = ap.parse_args()

    home, project = resolve(a.home, a.project)
    print(f"docwatch on {project} (.git), session '{a.session}', every {a.interval}s"
          + (" [dry-run]" if a.dry_run else ""))

    import time
    while True:
        h = head(project)
        if h is None:
            pass  # no repo / no commits yet
        else:
            base = last_seen(home)
            if base != h:
                (home / "docwatch").mkdir(parents=True, exist_ok=True)
                rng = f"{base or EMPTY_TREE}..{h}"
                diff = git(project, "diff", rng)
                (home / "docwatch" / "diff.patch").write_text(diff.stdout)
                changed = git(project, "diff", "--name-status", rng).stdout.strip()
                print(f"HEAD {h[:8]} (last {str(base)[:8]}) — {len(changed.splitlines())} files changed  ->  wake documenter")
                target = f"{a.session}:documenter"
                if a.dry_run:
                    print(f"    [dry-run] tmux send-keys -t {target} <doc-update>")
                else:
                    subprocess.run(["tmux", "send-keys", "-t", target, WAKE, "Enter"], check=False)
        if a.once:
            break
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
