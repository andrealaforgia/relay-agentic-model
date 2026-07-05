#!/usr/bin/env python3
"""Rock-solid event-driven dispatcher for the iTerm2 relay (no tmux).

Identity is the iTerm SESSION UUID, not the window id. Window ids are small ints
that iTerm RECYCLES when a window closes — so a wake addressed by window id could
land in a stranger's session (it did, once: a closed agent's id got reused by the
operator's own window). A session UUID is unique for the life of that session and
is never reused, so addressing by it means a wake reaches exactly the intended
session or nobody — misdelivery is impossible. It also needs no name-matching,
which is unreliable because claude renames the window title to its current task.

windows.json maps role -> session UUID. Each scan, for every mailbox role with
pending, ledger-verified mail:
  * session gone (UUID matches nothing) -> warn, never wake (agent needs relaunch)
  * busy ("esc to interrupt")           -> leave it alone (it is working/draining)
  * idle + past cooldown                -> WAKE; retry next scan if still pending
                                           (a dropped/eaten wake self-heals)

The wake is sent in TWO steps (text with NO newline, pause, then a bare newline)
because claude's TUI treats text+newline arriving together as a paste.

Watching INBOX dirs (not ledger deltas) also means the owner<->interpreter
conversation (logged straight to the ledger) never triggers a spurious wake.

  python3 relay/iterm_dispatch.py --home /path/to/project/.relay
"""
import argparse
import json
import os
import pathlib
import subprocess
import time

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
NOTFOUND = "<<RELAY_SESSION_NOT_FOUND>>"

WAKE = ("A message arrived — drain your inbox: process every pending message in "
        "your inbox per your playbook (read, act, send, ack), then stop and wait.")

COOLDOWN = 12.0   # seconds after a wake before we'll re-wake the same idle role


def osa(script: str) -> str:
    # Never let a transient AppleScript hang kill the watcher: a timed-out or failed
    # osascript call returns "" so the caller skips this tick and retries next loop.
    # "" reads as an unknown/busy session (not a gone one), so no false "session GONE".
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=20)
        return r.stdout
    except Exception:
        return ""


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def resolve(arg_home):
    home = pathlib.Path(arg_home or os.environ.get("RELAY_HOME") or SCRIPT_DIR).resolve()
    topo = home / "topology.json"
    if not topo.exists():
        topo = SCRIPT_DIR / "topology.json"
    t = json.loads(topo.read_text())
    roles = list(t["mailboxRoles"])
    allowed = set(t["allowed"].keys())
    win_map = json.loads((home / "iterm" / "windows.json").read_text())  # role -> session UUID
    return home, roles, allowed, win_map


def load_ledger(home):
    led = home / "ledger.jsonl"
    out = {}
    if led.exists():
        for line in led.read_text().splitlines():
            try:
                o = json.loads(line)
                out[o.get("seq")] = o
            except json.JSONDecodeError:
                pass
    return out


def legit_pending(home, role, allowed, ledger):
    """Count only inbox files that are genuine relay messages: a matching ledger
    entry, addressed to this role, FROM a sender permitted by topology (a chain
    neighbour, or the Sentinel via its sentinel>* edges). Neutralises a file
    dropped straight into the mailbox. Returns (count, forged_filenames)."""
    inbox = home / "mailbox" / role / "inbox"
    if not inbox.is_dir():
        return 0, []
    good, forged = 0, []
    for p in inbox.iterdir():
        if p.name.startswith("."):
            continue
        try:
            m = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            forged.append(p.name)
            continue
        seq, frm, to = m.get("seq"), m.get("from"), m.get("to")
        led = ledger.get(seq)
        if (to == role and frm and f"{frm}>{role}" in allowed
                and led and led.get("from") == frm and led.get("to") == to):
            good += 1
        else:
            forged.append(p.name)
    return good, forged


def session_contents(sid):
    """Return the visible text of the session with this UUID, or None if no such
    session exists (the window was closed). Iterating is how AppleScript locates a
    session by its stable id."""
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
    if out.strip() == NOTFOUND:
        return None
    return out


def is_busy(contents):
    tail = contents[-600:]
    if "esc to interrupt" in tail:
        return True
    if "for agents" in tail or "? for shortcuts" in tail:
        return False
    return True   # unknown render state -> wait


def wake_session(sid, dry):
    if dry:
        print(f"    [dry-run] wake session {sid}", flush=True)
        return
    # Writes ONLY to the session with this exact UUID; if it is gone, nothing happens.
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
    ap.add_argument("--home", default=None, help="RELAY_HOME of the swarm to watch")
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()

    home, roles, allowed, win_map = resolve(a.home)
    last_wake = {r: 0.0 for r in roles}
    warned = set()
    print(f"iterm dispatcher (UUID-addressed, retry-until-delivered, ledger-verified) "
          f"watching {home/'mailbox'}" + (" [dry-run]" if a.dry_run else ""), flush=True)
    while True:
        ledger = load_ledger(home)
        for r in roles:
            sid = win_map.get(r)
            if not sid:
                continue
            n, forged = legit_pending(home, r, allowed, ledger)
            for f in forged:
                if f not in warned:
                    print(f"!! IGNORING forged inbox file {r}/inbox/{f} "
                          f"(no valid ledger entry from a permitted sender — not delivered)", flush=True)
                    warned.add(f)
            if n == 0:
                continue
            contents = session_contents(sid)
            if contents is None:
                key = f"gone:{sid}"
                if key not in warned:
                    print(f"!! {r} session {sid} is GONE (window closed) — cannot deliver "
                          f"{n} msg(s); relaunch the {r} and re-map windows.json", flush=True)
                    warned.add(key)
                continue
            if (time.monotonic() - last_wake[r]) < COOLDOWN:
                continue
            if is_busy(contents):
                continue
            print(f"{r}: {n} pending, idle  ->  wake", flush=True)
            wake_session(sid, a.dry_run)
            last_wake[r] = time.monotonic()
        if a.once:
            break
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
