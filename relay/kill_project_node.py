#!/usr/bin/env python3
"""Kill leftover 'node' processes still rooted in a project directory.

Swarm teardown closes each role's iTerm window and kills whatever's attached to
its tty (iterm_close.py) — but an agent may have started a test process detached
from that tty (a BDD runner, a server-under-test kept alive for acceptance tests,
a `nohup npm test &`), which survives the window closing as an orphan. This sweeps
every 'node' process on the machine and kills the ones whose current working
directory is inside the given project dir, regardless of which window (if any)
started them.

Scoped by cwd, not by matching "test" in the command line, so it also catches a
test-support server left running — deliberately broad, since anything at all
still running node under the project dir once its swarm is down is unexpected.
Never touches node processes rooted elsewhere in the filesystem. The `claude` CLI
itself is a native binary (verify with `file "$(which claude)"` if that ever
changes) so this never targets the agent sessions.

  python3 relay/kill_project_node.py --project-dir /path/to/project
  python3 relay/kill_project_node.py --project-dir /path/to/project --dry-run
"""
import argparse
import os
import pathlib
import signal
import subprocess


def node_pids():
    r = subprocess.run(["pgrep", "-x", "node"], capture_output=True, text=True)
    return [int(p) for p in r.stdout.split()]


def process_cwd(pid):
    r = subprocess.run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
                        capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if line.startswith("n"):
            return line[1:]
    return None


def process_args(pid):
    r = subprocess.run(["ps", "-o", "args=", "-p", str(pid)], capture_output=True, text=True)
    return r.stdout.strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-dir", required=True)
    ap.add_argument("--dry-run", action="store_true", help="report what would be killed, don't kill")
    a = ap.parse_args()
    project_dir = str(pathlib.Path(a.project_dir).resolve())

    killed = []
    for pid in node_pids():
        cwd = process_cwd(pid)
        if cwd and (cwd == project_dir or cwd.startswith(project_dir + os.sep)):
            args = process_args(pid)
            if a.dry_run:
                print(f"[dry-run] would kill pid {pid} (cwd {cwd}): {args}")
                continue
            try:
                os.kill(pid, signal.SIGKILL)
                killed.append((pid, args))
            except ProcessLookupError:
                pass

    if a.dry_run:
        return
    if killed:
        print(f"killed {len(killed)} leftover node process(es) under {project_dir}:")
        for pid, args in killed:
            print(f"  {pid}: {args}")
    else:
        print(f"no leftover node processes under {project_dir}")


if __name__ == "__main__":
    main()
