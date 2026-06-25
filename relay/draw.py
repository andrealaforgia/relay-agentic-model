#!/usr/bin/env python3
"""Communication Drawer — render the relay ledger as a swimlane message board.

Reads <RELAY_HOME>/ledger.jsonl and writes a self-contained static HTML page
(no external assets, no JS framework — expand/collapse uses native <details>).
Fixed columns, left to right: Owner, Interpreter, Analyst, Examiner, Builder,
Sentinel. Each message appears as a card in its SENDER's column, presenting the
message **type**, its **recipient**, and its **content** (plus seq, refs, time).

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

# Fixed column order for the board, left to right.
LANES = ["owner", "interpreter", "analyst", "examiner", "builder", "qa", "sentinel"]
ACCENTS = {
    "owner": "#6b7280", "interpreter": "#2563eb", "analyst": "#7c3aed",
    "examiner": "#0d9488", "builder": "#d97706", "qa": "#db2777", "sentinel": "#dc2626",
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


def card(m):
    # Every card presents: the message TYPE, the RECIPIENT, and the CONTENT.
    sender, to, typ = m["from"], m["to"], m["type"]
    body = html.escape(m.get("body", ""))
    first = body.splitlines()[0] if body else ""
    summary = (first[:80] + "…") if len(first) > 80 else (first or "(empty)")
    refs = m.get("refs") or []
    refs_html = f'<span class="refs">{html.escape(",".join(refs))}</span>' if refs else ""
    ts = m.get("ts") or ""
    ts_html = f'<span class="ts">{html.escape(ts[11:19])}</span>' if len(ts) >= 19 else ""
    return (
        f'<div class="card" style="border-left-color:{ACCENTS.get(sender, "#888")}">'
        f'<div class="hd"><span class="seq">#{m["seq"]}</span>'
        f'<span class="badge">{html.escape(typ)}</span>'                       # type
        f'<span class="to">&rarr; {html.escape(to)}</span>'                    # recipient
        f'{refs_html}{ts_html}</div>'
        f'<details><summary>{summary}</summary><pre>{body}</pre></details>'    # content
        f'</div>'
    )


def render(msgs):
    # Fixed columns, left to right: Owner, Interpreter, Analyst, Examiner, Builder, Sentinel.
    lanes = LANES
    channels = sorted({f'{m["from"]}>{m["to"]}' for m in msgs})
    participants = {p for m in msgs for p in (m["from"], m["to"])}
    headers = "".join(
        f'<div class="lane-hd" style="color:{ACCENTS.get(r, "#888")}">{r.capitalize()}</div>'
        for r in lanes
    )
    rows = []
    for m in msgs:
        sender = m["from"]
        cells = [f'<div class="cell">{card(m) if r == sender else ""}</div>' for r in lanes]
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
  .ts {{ color: #9ca3af; font-family: ui-monospace, monospace; margin-left: auto; font-size: 11px; }}
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
    ap.add_argument("--refresh", type=int, default=0,
                    help="if >0, embed a meta-refresh so an open browser tab auto-reloads every N seconds")
    a = ap.parse_args()
    home, _chain, msgs = load(a.home)
    out = pathlib.Path(a.out) if a.out else home / "comms-site" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    page = render(msgs)
    if a.refresh > 0:  # written into the fresh render each time — cannot accumulate
        page = page.replace('<meta charset="utf-8">',
                            f'<meta charset="utf-8"><meta http-equiv="refresh" content="{a.refresh}">', 1)
    out.write_text(page)
    print(f"wrote {out} ({len(msgs)} messages)")


if __name__ == "__main__":
    main()
