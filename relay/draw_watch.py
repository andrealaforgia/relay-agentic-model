#!/usr/bin/env python3
"""Continuously regenerate the relay comms board from the ledger.

A standalone watcher that runs OUTSIDE any Claude Code / agent loop: it polls
<RELAY_HOME>/ledger.jsonl and re-runs draw.py (the canonical renderer) whenever
the ledger changes, so <RELAY_HOME>/comms-site/index.html stays live while the
swarm talks. draw.py remains the single source of truth for the page layout;
this just drives it on a loop.

  python3 relay/draw_watch.py --home <project>/.relay
  python3 relay/draw_watch.py --home <project>/.relay --interval 2 --refresh 15
  python3 relay/draw_watch.py --home <project>/.relay --once    # one render, then exit

Stop it with Ctrl-C (or kill the process). Run it detached so it survives:
  nohup python3 relay/draw_watch.py --home <project>/.relay > /tmp/comms-watch.log 2>&1 &
"""
import argparse
import os
import pathlib
import subprocess
import sys
import time

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
DRAW = SCRIPT_DIR / "draw.py"


def mtime(p):
    try:
        return p.stat().st_mtime
    except OSError:
        return None


def regen(home, refresh):
    return subprocess.run(
        [sys.executable, str(DRAW), "--home", str(home), "--refresh", str(refresh)],
        capture_output=True, text=True,
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--home", default=os.environ.get("RELAY_HOME"),
                    help="RELAY_HOME of the swarm (default: $RELAY_HOME)")
    ap.add_argument("--interval", type=float, default=2.0,
                    help="seconds between ledger-change checks (default: 2)")
    ap.add_argument("--refresh", type=int, default=15,
                    help="browser meta-refresh seconds embedded in the page (default: 15)")
    ap.add_argument("--once", action="store_true", help="render once and exit")
    a = ap.parse_args()
    if not a.home:
        sys.exit("error: pass --home <project>/.relay or set RELAY_HOME")
    if not DRAW.exists():
        sys.exit(f"error: draw.py not found next to this script ({DRAW})")

    home = pathlib.Path(a.home).resolve()
    ledger = home / "ledger.jsonl"
    out = home / "comms-site" / "index.html"
    print(f"comms watcher: {ledger} -> {out} (regenerates on change, every {a.interval}s)", flush=True)

    last = object()  # sentinel so the first pass always renders
    while True:
        m = mtime(ledger)
        if m != last:
            r = regen(home, a.refresh)
            if r.returncode == 0:
                print(r.stdout.strip(), flush=True)
                last = m
            else:
                print(f"draw.py error: {r.stderr.strip() or r.stdout.strip()}", file=sys.stderr, flush=True)
                # leave `last` unchanged so we retry on the next tick
        if a.once:
            break
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
