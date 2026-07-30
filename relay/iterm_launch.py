#!/usr/bin/env python3
"""Launch one EDD swarm as separate, visible iTerm2 windows (no tmux).

Opens one iTerm window per role, tiled side by side across the screen so you can
watch them all at once, each running `claude` in the project dir primed with its
playbook. On a screen too narrow to tile every window above MIN_WINDOW_WIDTH, it
falls back to cascading windows at FULL screen width instead — a window narrow
enough to clip Claude Code's own status footer looks permanently "busy" to
iterm_dispatch.py's idle/busy detection, silently wedging the whole swarm, so a
readable (if overlapping) window is the safer default. Records role -> iTerm
session UUID in <RELAY_HOME>/iterm/windows.json so the companion dispatcher
(iterm_dispatch.py) can wake the right session (UUIDs are stable; window ids get
recycled when a window closes and would misdeliver a wake). Each window is also
given a role badge + colour (via iterm_decorate.py).

  python3 relay/iterm_launch.py <swarm-name> <project-dir>

Env:
  CLAUDE_CMD        command to run in each window (default: claude --dangerously-skip-permissions)
  START_DELAY       seconds to let claude boot before sending the kickoff (default: 12)
  MIN_WINDOW_WIDTH  px below which tiling gives way to full-width cascading (default: 480)
"""
import json
import os
import pathlib
import subprocess
import sys
import time

TOOL_DIR = pathlib.Path(__file__).resolve().parent
# The relay chain, then its out-of-chain observers (qa = test-design reviewer,
# warden = security expert, reaper = mutation testing, courier = acceptance-test
# runner, sentinel = comms auditor). Left-to-right window order follows this list;
# observers sit to the right of the chain. All are mapped in windows.json so their
# drivers (iterm_qa.py / iterm_warden.py / iterm_reaper.py / iterm_courier.py /
# iterm_sentinel.py) can wake the right session by UUID.
ROLES = ["interpreter", "analyst", "examiner", "builder", "qa", "warden", "reaper", "courier", "sentinel"]
CLAUDE_CMD = os.environ.get("CLAUDE_CMD", "claude --dangerously-skip-permissions")
START_DELAY = float(os.environ.get("START_DELAY", "12"))
MENUBAR = 38  # top offset so windows clear the menu bar

# Below this width, Claude Code's own TUI stops rendering its bottom status line
# ("for agents" / "? for shortcuts" / "shift+tab to cycle") — exactly the text
# iterm_dispatch.py and the observer triggers scan for to tell idle from busy. A
# window narrower than this looks permanently "busy" to every watcher and its mail
# silently never gets delivered, wedging the whole swarm. Tune via env if needed.
MIN_WINDOW_WIDTH = int(os.environ.get("MIN_WINDOW_WIDTH", "480"))
CASCADE_STEP = 28  # px offset per window when cascading, so title bars stay clickable

# Per-role model: everyone runs on Sonnet except the two hardest-reasoning roles —
# the Interpreter (human-facing planning) and the Sentinel (audits the whole ledger),
# which run on Opus. Each role's window launches `claude --model <this>`.
DEFAULT_MODEL = "sonnet"
MODELS = {"interpreter": "opus", "sentinel": "opus"}


def osa(script: str) -> str:
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
    return r.stdout.strip()


def esc(s: str) -> str:
    """Escape a Python string for embedding inside an AppleScript double-quoted literal."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def desktop_width_height():
    out = osa('tell application "Finder" to get bounds of window of desktop')
    # "0, 0, 5120, 1440"
    nums = [int(x.strip()) for x in out.split(",")]
    return nums[2], nums[3]


def window_bounds(n: int, sw: int, sh_: int):
    """One bounds tuple per role. Tiles side by side edge-to-edge when the screen
    is wide enough for every window to stay above MIN_WINDOW_WIDTH; otherwise
    every window gets the FULL screen width (so Claude Code's status footer never
    gets clipped) and they cascade downward instead, overlapping — a working,
    readable window beats a wedged swarm."""
    col_w = sw // n
    if col_w >= MIN_WINDOW_WIDTH:
        bounds = []
        for i in range(n):
            x1 = i * col_w
            x2 = sw if i == n - 1 else (i + 1) * col_w
            bounds.append((x1, MENUBAR, x2, sh_))
        return bounds, False

    print(f"screen too narrow to tile {n} windows at >= {MIN_WINDOW_WIDTH}px each "
          f"({sw}px / {n} = {col_w}px/window) — cascading at full width instead")
    return [(0, MENUBAR + i * CASCADE_STEP, sw, sh_) for i in range(n)], True


def create_window(name: str, start_cmd: str, bounds) -> str:
    """Create the window and return its SESSION UUID (stable, never recycled) —
    not the window id, which iTerm reuses when a window closes and which would let
    a wake land in a stranger's session."""
    x1, y1, x2, y2 = bounds
    script = f'''
tell application "iTerm"
  set w to (create window with default profile)
  set bounds of w to {{{x1}, {y1}, {x2}, {y2}}}
  tell current session of w
    set name to "{esc(name)}"
    write text "{esc(start_cmd)}"
    return id
  end tell
end tell
'''
    return osa(script)


def write_to_window(sid: str, text: str, submit: bool = False):
    # Address the session by its UUID (not window id). newline NO: type the text
    # without submitting (claude treats text+newline as a paste); submit separately
    # with a bare newline once claude is interactive.
    nl = "" if submit else " newline NO"
    body = '""' if submit else f'"{esc(text)}"'
    script = f'''
tell application "iTerm"
  repeat with w in windows
    repeat with t in tabs of w
      repeat with s in sessions of t
        if (id of s) is "{sid}" then
          tell s
            write text {body}{nl}
          end tell
          return "ok"
        end if
      end repeat
    end repeat
  end repeat
end tell
'''
    osa(script)


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: iterm_launch.py <swarm-name> <project-dir>")
    swarm = sys.argv[1]
    project = pathlib.Path(os.path.expanduser(sys.argv[2])).resolve()
    project.mkdir(parents=True, exist_ok=True)

    relay_home = project / ".relay"
    relay_tool = TOOL_DIR / "relay.mjs"
    agents_dir = TOOL_DIR / "agents"

    # Builder commits its work, so the project must be a git repo; keep .relay out of it.
    if not (project / ".git").exists():
        subprocess.run(["git", "-C", str(project), "init", "-q"], check=False)
    gi = project / ".gitignore"
    if not (gi.exists() and ".relay/" in gi.read_text()):
        with gi.open("a") as f:
            f.write(".relay/\n")

    # Scaffold this swarm's relay state (idempotent — preserves an existing ledger/mailboxes).
    subprocess.run(["node", str(relay_tool), "init"],
                   env={**os.environ, "RELAY_HOME": str(relay_home),
                        "PATH": "/opt/homebrew/bin:" + os.environ.get("PATH", "")},
                   check=True)

    # Per-role startup scripts (avoids AppleScript quoting of the full env+claude line).
    iterm_dir = relay_home / "iterm"
    iterm_dir.mkdir(parents=True, exist_ok=True)
    for r in ROLES:
        sh = iterm_dir / f"{r}.sh"
        sh.write_text(
            "#!/bin/bash\n"
            f"cd '{project}'\n"
            f"export RELAY_HOME='{relay_home}' RELAY_TOOL='{relay_tool}' RELAY_AGENTS='{agents_dir}'\n"
            'export PATH="/opt/homebrew/bin:$PATH"\n'
            "clear\n"
            f"exec {CLAUDE_CMD} --model {MODELS.get(r, DEFAULT_MODEL)}\n"
        )
        sh.chmod(0o755)

    # Tile side by side if the screen is wide enough; cascade at full width otherwise.
    sw, sh_ = desktop_width_height()
    n = len(ROLES)
    bounds_list, cascaded = window_bounds(n, sw, sh_)
    win_ids = {}
    for r, bounds in zip(ROLES, bounds_list):
        wid = create_window(r, f"bash '{iterm_dir / (r + '.sh')}'", bounds)
        win_ids[r] = wid
        print(f"window {r}: id {wid}  bounds {bounds}" + ("  (cascaded)" if cascaded else ""))

    (iterm_dir / "windows.json").write_text(json.dumps(win_ids, indent=2))

    # Let claude boot, then prime each window with its role.
    print(f"waiting {START_DELAY}s for claude to boot...")
    time.sleep(START_DELAY)

    base = ('Use the relay CLI as: node "$RELAY_TOOL" <cmd> (your data root is $RELAY_HOME). '
            "When you receive a 'drain your inbox' message, process every pending message "
            "per the playbook, then stop and wait.")
    for r in ROLES:
        if r == "sentinel":
            kick = ("Read $RELAY_AGENTS/sentinel.md and act as the Sentinel (Communication "
                    "Auditor) for this swarm. Your data root is $RELAY_HOME. When you receive "
                    "an 'audit time' message, audit new ledger messages per the playbook, then stop.")
        elif r == "qa":
            kick = ("Read $RELAY_AGENTS/qa.md and act as the QA test-design reviewer for this "
                    "project — an observer outside the relay chain (you receive no relay mail). "
                    "Your data root is $RELAY_HOME. When you receive a 'QA time' message, review "
                    "the staged diff's tests per the playbook, send the result to the builder over "
                    "qa>builder, then stop.")
        elif r == "warden":
            kick = ("Read $RELAY_AGENTS/warden.md and act as the Warden (Security Expert) for this "
                    "project — an observer outside the relay chain (you receive no relay mail). "
                    "Your data root is $RELAY_HOME. When you receive a 'Warden time' message, scan "
                    "the staged diff for security vulnerabilities per the playbook, send the result "
                    "to the builder over warden>builder, then stop.")
        elif r == "reaper":
            kick = ("Read $RELAY_AGENTS/reaper.md and act as the Reaper (Mutation Testing) for this "
                    "project — an observer outside the relay chain (you receive no relay mail). "
                    "Your data root is $RELAY_HOME. When you receive a 'Reaper time' message, run "
                    "mutation testing on the staged diff's changed production code per the playbook, "
                    "send the result to the builder over reaper>builder, then stop.")
        elif r == "courier":
            kick = ("Read $RELAY_AGENTS/courier.md and act as the Courier (Acceptance Test Runner) for "
                    "this project — an observer outside the relay chain (you receive no relay mail). "
                    "Your data root is $RELAY_HOME. When you receive a 'Courier time' message, run the "
                    "whole acceptance/BDD suite per the playbook, send the result to the builder over "
                    "courier>builder, then stop.")
        else:
            kick = f"Read $RELAY_AGENTS/{r}.md and act as the {r} for this project. {base}"
        write_to_window(win_ids[r], kick)
        print(f"primed {r}")

    # The kickoff's own trailing newline can be eaten if claude is still painting
    # its startup. Once interactive, a separate empty write reliably submits it.
    time.sleep(4)
    for r in ROLES:
        write_to_window(win_ids[r], "", submit=True)  # bare newline = submit the queued kickoff
        print(f"submitted {r}")

    # Decorate each window with its role badge + colour (reuses iterm_decorate.py so
    # its PALETTE stays the single source of truth for colours).
    subprocess.run(["python3", str(TOOL_DIR / "iterm_decorate.py"), "--home", str(relay_home)], check=False)

    print(f"\nLaunched swarm '{swarm}' as iTerm windows.")
    print(f"  project   : {project}")
    print(f"  RELAY_HOME: {relay_home}")
    print(f"  windows   : {' '.join(ROLES)} (role -> id in {iterm_dir/'windows.json'})")
    print(f"\nStart the dispatcher:")
    print(f"  python3 {TOOL_DIR/'iterm_dispatch.py'} --home '{relay_home}'")


if __name__ == "__main__":
    main()
