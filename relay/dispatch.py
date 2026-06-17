#!/usr/bin/env python3
"""Event-driven dispatcher for the filesystem-mailbox relay.

Watches relay/ledger.jsonl and, for every new message addressed to a mailbox
role, wakes that role's tmux window so the agent drains its inbox. This replaces
per-session /loop polling: the agents stay idle (and cost nothing) until there is
actually something for them, while this cheap loop does the watching.

The ledger's gap-free `seq` means each message is announced exactly once, so there
is no dedup bookkeeping and restarting the dispatcher never re-fires history.

  python3 relay/dispatch.py --session myproj --home /path/to/myproj/.relay
  python3 relay/dispatch.py --dry-run --once --from-start   # test without tmux

For concurrent swarms, run one dispatcher per project: each with its own
--session (matching that swarm's tmux session) and --home (that swarm's
RELAY_HOME). They watch separate ledgers and wake separate tmux sessions, so
they never cross.
"""
import argparse
import json
import os
import pathlib
import subprocess
import time

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent

# Idempotent on purpose: "drain ... until empty" means coalesced or mid-turn
# pushes are harmless — the agent just processes whatever is pending.
WAKE = ("A message arrived — drain your inbox: process every pending message in "
        "your inbox per your playbook (read, act, send, ack), then stop and wait.")


def resolve_home(arg_home):
    home = pathlib.Path(arg_home or os.environ.get("RELAY_HOME") or SCRIPT_DIR).resolve()
    topo_path = home / "topology.json"
    if not topo_path.exists():
        topo_path = SCRIPT_DIR / "topology.json"  # bundled default rules
    roles = set(json.loads(topo_path.read_text())["mailboxRoles"])
    return home, home / "ledger.jsonl", roles


def ledger_lines(ledger):
    return ledger.read_text().splitlines() if ledger.exists() else []


def wake(session, role, dry):
    target = f"{session}:{role}"
    if dry:
        print(f"    [dry-run] tmux send-keys -t {target} <wake>")
        return
    subprocess.run(["tmux", "send-keys", "-t", target, WAKE, "Enter"], check=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--session", default="edd", help="tmux session name (default: edd)")
    ap.add_argument("--home", default=None, help="RELAY_HOME of the swarm to watch (default: $RELAY_HOME or tool dir)")
    ap.add_argument("--interval", type=float, default=1.0, help="seconds between scans")
    ap.add_argument("--from-start", action="store_true",
                    help="also announce messages already in the ledger at startup")
    ap.add_argument("--dry-run", action="store_true", help="print instead of send-keys")
    ap.add_argument("--once", action="store_true", help="scan once and exit (for testing)")
    a = ap.parse_args()

    home, ledger, roles = resolve_home(a.home)
    seen = 0 if a.from_start else len(ledger_lines(ledger))
    print(f"dispatcher watching {ledger} from seq {seen}, tmux session '{a.session}'"
          + (" [dry-run]" if a.dry_run else ""))
    while True:
        lines = ledger_lines(ledger)
        for line in lines[seen:]:
            try:
                m = json.loads(line)
            except json.JSONDecodeError:
                continue
            to = m.get("to")
            if to in roles:  # owner has no pane and is skipped automatically
                print(f"#{m.get('seq')} {m.get('from')} > {to} [{m.get('type')}]  ->  wake {to}")
                wake(a.session, to, a.dry_run)
        seen = len(lines)
        if a.once:
            break
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
