#!/usr/bin/env python3
"""Periodic trigger for the SENTINEL (Communication Auditor).

The Sentinel is external to the chain: it audits the conversation for breaches of
the per-edge communication contracts (see relay/agents/sentinel.md). This script
wakes the Sentinel's tmux window on an interval — but only when there are unaudited
messages — so it costs nothing while the swarm is quiet.

Coordination: the Sentinel writes the next-seq-to-audit into
<RELAY_HOME>/audit/.cursor; this script compares it to the ledger length and wakes
the window only if the ledger has grown past the cursor.

  python3 relay/sentinel.py --session <swarm> --home <project>/.relay --interval 60
  python3 relay/sentinel.py --home <project>/.relay --dry-run --once
"""
import argparse
import os
import pathlib
import subprocess
import time

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
WAKE = ("Audit time — read the ledger from your cursor, judge each new message "
        "against the per-edge contracts in your playbook, append findings, advance "
        "the cursor, refresh report.md, then stop.")


def resolve_home(arg_home):
    home = pathlib.Path(arg_home or os.environ.get("RELAY_HOME") or SCRIPT_DIR).resolve()
    return home, home / "ledger.jsonl", home / "audit" / ".cursor"


def ledger_len(ledger):
    return len(ledger.read_text().splitlines()) if ledger.exists() else 0


def cursor_val(cursor):
    try:
        return int(cursor.read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0


def wake(session, dry):
    target = f"{session}:sentinel"
    if dry:
        print(f"    [dry-run] tmux send-keys -t {target} <audit>")
        return
    subprocess.run(["tmux", "send-keys", "-t", target, WAKE, "Enter"], check=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--session", default="edd", help="tmux session name (default: edd)")
    ap.add_argument("--home", default=None, help="RELAY_HOME of the swarm to audit")
    ap.add_argument("--interval", type=float, default=60.0, help="seconds between audit checks")
    ap.add_argument("--dry-run", action="store_true", help="print instead of send-keys")
    ap.add_argument("--once", action="store_true", help="check once and exit")
    a = ap.parse_args()

    home, ledger, cursor = resolve_home(a.home)
    print(f"sentinel trigger on {ledger}, session '{a.session}', every {a.interval}s"
          + (" [dry-run]" if a.dry_run else ""))
    while True:
        n, c = ledger_len(ledger), cursor_val(cursor)
        if n > c:
            print(f"ledger at {n}, audited through {c}  ->  wake sentinel")
            wake(a.session, a.dry_run)
        if a.once:
            break
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
