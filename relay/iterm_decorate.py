#!/usr/bin/env python3
"""Decorate a running swarm's iTerm windows: a role BADGE + a distinct TAB COLOR
per agent — applied on the fly to live sessions, no relaunch.

Each session is located by its UUID (from iterm/windows.json), its tty is read via
AppleScript, and iTerm escape sequences are written straight to that tty:
  * badge:     OSC 1337 ;SetBadgeFormat=<base64(role)>
  * tab color: OSC 6 ;1;bg;{red|green|blue};brightness;<0-255>
These go to the terminal's OUTPUT stream, so they render without touching the
running agent's input.

  python3 relay/iterm_decorate.py --home /path/to/project/.relay
"""
import argparse
import base64
import json
import os
import pathlib
import subprocess

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent

# role -> (tab colour (r,g,b 0-255), badge text, background hex (dark tint so text stays readable))
PALETTE = {
    "interpreter": ((40, 120, 255), "INTERPRETER", "0c2340"),   # blue  — the human-facing one
    "analyst":     ((40, 180, 90),  "ANALYST",     "0c3d1f"),   # green
    "examiner":    ((235, 160, 30), "EXAMINER",    "3d2a08"),   # amber
    "builder":     ((150, 90, 220), "BUILDER",     "2a123d"),   # purple
    "sentinel":    ((220, 60, 60),  "SENTINEL",    "3d0c12"),   # red   — the auditor
    "documenter":  ((40, 160, 235), "Documenter",  "08243d"),   # blue    — the docs observer
    "qa":          ((236, 72, 153), "QA",          "3d0c2e"),   # magenta — the test-design reviewer
    "warden":      ((6, 182, 212),  "WARDEN",      "07323d"),   # cyan    — the security expert
}


def osa(script):
    return subprocess.run(["osascript", "-e", script], capture_output=True, text=True).stdout.strip()


def session_tty(sid):
    return osa(f'''
tell application "iTerm"
  repeat with w in windows
    repeat with t in tabs of w
      repeat with s in sessions of t
        if (id of s) is "{sid}" then return tty of s
      end repeat
    end repeat
  end repeat
end tell
''')


def decorate(tty, rgb, badge, bg_hex):
    r, g, b = rgb
    b64 = base64.b64encode(badge.encode()).decode()
    seq = (
        f"\033]1337;SetBadgeFormat={b64}\007"          # role badge overlay
        f"\033]1337;SetColors=bg={bg_hex}\007"          # window BACKGROUND (dark tint)
        f"\033]6;1;bg;red;brightness;{r}\007"           # tab strip colour (r,g,b)
        f"\033]6;1;bg;green;brightness;{g}\007"
        f"\033]6;1;bg;blue;brightness;{b}\007"
    )
    with open(tty, "w") as f:
        f.write(seq)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--home", default=None, help="RELAY_HOME of the swarm")
    a = ap.parse_args()
    home = pathlib.Path(a.home or os.environ.get("RELAY_HOME") or SCRIPT_DIR).resolve()
    win_map = json.loads((home / "iterm" / "windows.json").read_text())
    for role, sid in win_map.items():
        if role not in PALETTE:
            continue
        tty = session_tty(sid)
        if not tty.startswith("/dev"):
            print(f"{role}: session not found (uuid {sid}) — skipped")
            continue
        rgb, badge, bg_hex = PALETTE[role]
        decorate(tty, rgb, badge, bg_hex)
        print(f"{role}: badge='{badge}' bg=#{bg_hex} -> {tty}")


if __name__ == "__main__":
    main()
