#!/usr/bin/env python3
"""Communication Drawer — render the relay ledger as a swimlane message board.

Reads <RELAY_HOME>/ledger.jsonl and writes a self-contained static HTML page
(no external assets, no JS framework — expand/collapse uses native <details>):
one lane per agent, message cards in the sender's lane flowing top-to-bottom,
each showing direction, type, refs and an expandable body. Inspired by the
Kaleidoscope communication board.

Deterministic and cheap — re-run it anytime to refresh the board:

  python3 relay/draw.py --home <project>/.relay
  python3 relay/draw.py --home <project>/.relay --out /tmp/board.html
"""
import argparse
import html
import json
import os
import pathlib

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
ACCENTS = {
    "owner": "#6b7280", "interpreter": "#2563eb", "analyst": "#7c3aed",
    "examiner": "#0d9488", "builder": "#d97706",
}


def load(home_arg):
    home = pathlib.Path(home_arg or os.environ.get("RELAY_HOME") or SCRIPT_DIR).resolve()
    topo_path = home / "topology.json"
    if not topo_path.exists():
        topo_path = SCRIPT_DIR / "topology.json"
    chain = json.loads(topo_path.read_text())["chain"]
    ledger = home / "ledger.jsonl"
    msgs = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()] if ledger.exists() else []
    return home, chain, msgs


def card(m, lanes):
    sender, to, typ = m["from"], m["to"], m["type"]
    arrow = "→" if lanes.index(to) > lanes.index(sender) else "←"
    body = html.escape(m.get("body", ""))
    first = body.splitlines()[0] if body else ""
    summary = (first[:70] + "…") if len(first) > 70 else (first or "(empty)")
    refs = m.get("refs") or []
    refs_html = f'<span class="refs">{html.escape(",".join(refs))}</span>' if refs else ""
    return (
        f'<div class="card" style="border-left-color:{ACCENTS.get(sender, "#888")}">'
        f'<div class="hd"><span class="seq">#{m["seq"]}</span>'
        f'<span class="badge">{html.escape(typ)}</span>'
        f'<span class="to">{arrow} {html.escape(to)}</span>{refs_html}</div>'
        f'<details><summary>{summary}</summary><pre>{body}</pre></details>'
        f'</div>'
    )


def render(chain, msgs):
    lanes = chain
    channels = sorted({f'{m["from"]}>{m["to"]}' for m in msgs})
    participants = sorted({p for m in msgs for p in (m["from"], m["to"])}, key=lanes.index)
    headers = "".join(
        f'<div class="lane-hd" style="color:{ACCENTS.get(r, "#888")}">{html.escape(r)}</div>'
        for r in lanes
    )
    rows = []
    for m in msgs:
        cells = []
        for r in lanes:
            cells.append(f'<div class="cell">{card(m, lanes) if r == m["from"] else ""}</div>')
        rows.append("".join(cells))
    grid = f'repeat({len(lanes)}, minmax(0, 1fr))'
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Communication board</title>
<style>
  :root {{ font-family: system-ui, sans-serif; }}
  body {{ margin: 0; background: #f7f7f8; color: #1f2937; }}
  header {{ padding: 18px 24px; border-bottom: 1px solid #e5e7eb; background: #fff; position: sticky; top: 0; z-index: 3; }}
  header h1 {{ margin: 0 0 4px; font-size: 18px; }}
  header .stats {{ color: #6b7280; font-size: 13px; }}
  .board {{ display: grid; grid-template-columns: {grid}; gap: 0; }}
  .lane-hd {{ position: sticky; top: 61px; background: #fff; border-bottom: 2px solid #e5e7eb;
             padding: 8px 10px; font-weight: 600; font-size: 13px; text-align: center; z-index: 2; }}
  .cell {{ border-right: 1px dashed #e5e7eb; padding: 6px; min-height: 8px; }}
  .card {{ background: #fff; border: 1px solid #e5e7eb; border-left: 4px solid #888; border-radius: 8px;
           padding: 8px 10px; box-shadow: 0 1px 2px rgba(0,0,0,.05); }}
  .hd {{ display: flex; gap: 8px; align-items: center; font-size: 12px; flex-wrap: wrap; }}
  .seq {{ color: #9ca3af; }}
  .badge {{ background: #eef2ff; color: #3730a3; border-radius: 999px; padding: 1px 8px; font-weight: 600; }}
  .to {{ color: #6b7280; }}
  .refs {{ color: #9ca3af; font-family: ui-monospace, monospace; }}
  details {{ margin-top: 4px; }}
  summary {{ cursor: pointer; font-size: 13px; color: #374151; }}
  pre {{ white-space: pre-wrap; word-break: break-word; font-family: ui-monospace, monospace;
         font-size: 12px; background: #f9fafb; border-radius: 6px; padding: 8px; margin: 6px 0 0; }}
</style></head>
<body>
<header>
  <h1>Communication board</h1>
  <div class="stats">{len(msgs)} messages &middot; {len(participants)} agents &middot; {len(channels)} channels &middot; {", ".join(channels)}</div>
</header>
<div class="board">{headers}{"".join(rows)}</div>
</body></html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--home", default=None, help="RELAY_HOME of the swarm (default: $RELAY_HOME)")
    ap.add_argument("--out", default=None, help="output HTML path (default: <home>/comms-site/index.html)")
    a = ap.parse_args()
    home, chain, msgs = load(a.home)
    out = pathlib.Path(a.out) if a.out else home / "comms-site" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(chain, msgs))
    print(f"wrote {out} ({len(msgs)} messages)")


if __name__ == "__main__":
    main()
