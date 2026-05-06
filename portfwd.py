#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════════╗
║           P Y - F O R W A R D E R   v3.0                 ║
║       Advanced TCP Port Forwarder / Pivot Tool            ║
║       Compatible with Metasploit / msfconsole             ║
╚═══════════════════════════════════════════════════════════╝
  Author  : Enhanced from original forwarder.py / fowrdin.py
  Usage   : python3 portfwd.py --help
"""

import socket
import threading
import argparse
import sys
import os
import time
import signal
from datetime import datetime

# ──────────────────────────────────────────────
#  ANSI COLOR CODES  (hacker terminal palette)
# ──────────────────────────────────────────────
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    DIM     = "\033[2m"
    BLINK   = "\033[5m"

    @staticmethod
    def disable():
        for attr in ['RESET','BOLD','RED','GREEN','YELLOW','BLUE','CYAN','WHITE','DIM','BLINK']:
            setattr(C, attr, "")


# ──────────────────────────────────────────────
#  GLOBAL STATE
# ──────────────────────────────────────────────
active_connections = 0
total_connections  = 0
bytes_in           = 0
bytes_out          = 0
lock               = threading.Lock()
shutdown_event     = threading.Event()
listeners          = []          # list of (server_socket, lport, rhost, rport)
logfile_handle     = None


# ──────────────────────────────────────────────
#  LOGGING
# ──────────────────────────────────────────────
def ts():
    return datetime.now().strftime("%H:%M:%S")

def log(msg, level="INFO"):
    levels = {
        "INFO"  : f"{C.DIM}[{ts()}]{C.RESET} {C.CYAN}[*]{C.RESET}",
        "GOOD"  : f"{C.DIM}[{ts()}]{C.RESET} {C.GREEN}[+]{C.RESET}",
        "WARN"  : f"{C.DIM}[{ts()}]{C.RESET} {C.YELLOW}[!]{C.RESET}",
        "ERROR" : f"{C.DIM}[{ts()}]{C.RESET} {C.RED}[-]{C.RESET}",
        "DATA"  : f"{C.DIM}[{ts()}]{C.RESET} {C.BLUE}[~]{C.RESET}",
        "FATAL" : f"{C.DIM}[{ts()}]{C.RESET} {C.RED}{C.BOLD}[X]{C.RESET}",
    }
    prefix = levels.get(level, levels["INFO"])
    line   = f"{prefix} {msg}"
    print(line)
    if logfile_handle:
        clean = f"[{ts()}] [{level}] {msg}"
        logfile_handle.write(clean + "\n")
        logfile_handle.flush()


# ──────────────────────────────────────────────
#  BANNER
# ──────────────────────────────────────────────
def banner():
    b = f"""
{C.GREEN}{C.BOLD}
  ██████╗ ██╗   ██╗      ███████╗██╗    ██╗██████╗
  ██╔══██╗╚██╗ ██╔╝      ██╔════╝██║    ██║██╔══██╗
  ██████╔╝ ╚████╔╝ █████╗█████╗  ██║ █╗ ██║██║  ██║
  ██╔═══╝   ╚██╔╝  ╚════╝██╔══╝  ██║███╗██║██║  ██║
  ██║        ██║         ██║     ╚███╔███╔╝██████╔╝
  ╚═╝        ╚═╝         ╚═╝      ╚══╝╚══╝ ╚═════╝{C.RESET}
{C.CYAN}  ┌─────────────────────────────────────────────────┐
  │  v3.0 │ TCP Port Forwarder │ MSF Compatible     │
  │  Multi-Port │ Logging │ Live Stats │ Pivoting   │
  └─────────────────────────────────────────────────┘{C.RESET}
"""
    print(b)


# ──────────────────────────────────────────────
#  SOCKET HELPERS
# ──────────────────────────────────────────────
def make_server_socket(host, port):
    """Create a reusable TCP server socket."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # FIX: allows quick restart
    s.bind((host, port))
    s.listen(10)
    s.settimeout(1.0)   # allows clean shutdown checks
    return s


# ──────────────────────────────────────────────
#  CORE FORWARDING LOGIC
# ──────────────────────────────────────────────
def forward_data(src, dst, direction, verbose, buf_size):
    """Forward bytes from src → dst. Runs in its own thread."""
    global bytes_in, bytes_out
    try:
        while not shutdown_event.is_set():
            try:
                data = src.recv(buf_size)
            except socket.timeout:
                continue
            if not data:
                break
            try:
                dst.sendall(data)
            except OSError:
                break

            length = len(data)
            with lock:
                if "C→R" in direction:
                    bytes_out += length
                else:
                    bytes_in += length

            if verbose:
                log(f"{C.BLUE}{direction}{C.RESET}  {C.YELLOW}{length}{C.RESET} bytes", "DATA")
    except Exception:
        pass
    finally:
        # Half-close to unblock the other side
        for sock in (src, dst):
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass


def handle_client(client_socket, client_addr, rhost, rport, args):
    """Handle a single client connection."""
    global active_connections, total_connections

    with lock:
        active_connections += 1
        total_connections  += 1
        cid = total_connections

    client_socket.settimeout(args.timeout)

    log(
        f"{C.GREEN}New session {C.BOLD}#{cid}{C.RESET}"
        f"  from {C.YELLOW}{client_addr[0]}:{client_addr[1]}{C.RESET}"
        f"  active={C.CYAN}{active_connections}{C.RESET}",
        "GOOD"
    )

    # ── Connect to target ──────────────────────
    try:
        remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote.settimeout(args.timeout)
        remote.connect((rhost, rport))
        log(f"Session #{cid} → {C.CYAN}{rhost}:{rport}{C.RESET}", "INFO")
    except Exception as e:
        log(f"Session #{cid}: target {rhost}:{rport} unreachable — {e}", "ERROR")
        client_socket.close()
        with lock:
            active_connections -= 1
        return

    buf = args.bufsize

    # ── Spawn bidirectional relay threads ──────
    t1 = threading.Thread(
        target=forward_data,
        args=(client_socket, remote, "C→R", args.verbose, buf),
        daemon=True, name=f"fwd-cr-{cid}"
    )
    t2 = threading.Thread(
        target=forward_data,
        args=(remote, client_socket, "R→C", args.verbose, buf),
        daemon=True, name=f"fwd-rc-{cid}"
    )
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # ── Cleanup ────────────────────────────────
    for s in (client_socket, remote):
        try:
            s.close()
        except Exception:
            pass

    with lock:
        active_connections -= 1

    log(
        f"{C.RED}Session #{cid} closed{C.RESET}"
        f"  active={C.CYAN}{active_connections}{C.RESET}",
        "WARN"
    )


# ──────────────────────────────────────────────
#  LISTENER LOOP (one per port rule)
# ──────────────────────────────────────────────
def run_listener(lhost, lport, rhost, rport, args):
    """Accept loop for one forwarding rule."""
    try:
        server = make_server_socket(lhost, lport)
    except Exception as e:
        log(f"Cannot bind {lhost}:{lport} → {e}", "FATAL")
        return

    listeners.append(server)
    log(
        f"Listening  {C.GREEN}{lhost}:{lport}{C.RESET}"
        f"  ──→  {C.CYAN}{rhost}:{rport}{C.RESET}",
        "GOOD"
    )

    while not shutdown_event.is_set():
        try:
            client_sock, addr = server.accept()
        except socket.timeout:
            continue
        except OSError:
            break

        threading.Thread(
            target=handle_client,
            args=(client_sock, addr, rhost, rport, args),
            daemon=True
        ).start()

    try:
        server.close()
    except Exception:
        pass


# ──────────────────────────────────────────────
#  LIVE STATS DISPLAY
# ──────────────────────────────────────────────
def stats_loop(interval=5):
    """Print live stats every N seconds."""
    while not shutdown_event.is_set():
        time.sleep(interval)
        if shutdown_event.is_set():
            break
        with lock:
            a = active_connections
            t = total_connections
            bi = bytes_in
            bo = bytes_out

        def fmt(b):
            if b >= 1_048_576:
                return f"{b/1_048_576:.1f} MB"
            elif b >= 1024:
                return f"{b/1024:.1f} KB"
            return f"{b} B"

        print(
            f"\n{C.DIM}{'─'*55}{C.RESET}\n"
            f"  {C.CYAN}STATS{C.RESET}  "
            f"Active={C.GREEN}{a}{C.RESET}  "
            f"Total={C.YELLOW}{t}{C.RESET}  "
            f"↑{C.BLUE}{fmt(bo)}{C.RESET}  "
            f"↓{C.GREEN}{fmt(bi)}{C.RESET}"
            f"\n{C.DIM}{'─'*55}{C.RESET}\n"
        )


# ──────────────────────────────────────────────
#  MULTI-PORT RULE PARSER
# ──────────────────────────────────────────────
def parse_multi(rule_str):
    """
    Format: LPORT:RHOST/RPORT[,LPORT:RHOST/RPORT,...]
    Example: 4444:127.0.0.1/5555,8080:10.0.0.1/80
    """
    rules = []
    for item in rule_str.split(","):
        item = item.strip()
        try:
            lport_str, rest  = item.split(":", 1)
            rhost,     rport_str = rest.split("/", 1)
            rules.append((int(lport_str), rhost.strip(), int(rport_str)))
        except ValueError:
            print(f"{C.RED}[!] Bad rule format: '{item}'  (expected LPORT:RHOST/RPORT){C.RESET}")
            sys.exit(1)
    return rules


# ──────────────────────────────────────────────
#  METASPLOIT PRESET HELPER
# ──────────────────────────────────────────────
def msf_hint(lport, rhost, rport):
    """Print copy-paste Metasploit handler commands."""
    print(f"""
{C.GREEN}{C.BOLD}┌─ MSF HANDLER (run in msfconsole) ─────────────────────┐{C.RESET}
{C.CYAN}  use exploit/multi/handler
  set PAYLOAD windows/x64/meterpreter/reverse_tcp
  set LHOST 0.0.0.0
  set LPORT {lport}
  set ExitOnSession false
  exploit -j{C.RESET}
{C.GREEN}{C.BOLD}└────────────────────────────────────────────────────────┘

{C.YELLOW}┌─ ON THE TARGET ────────────────────────────────────────┐{C.RESET}
{C.CYAN}  # Payload should connect back to: {rhost}:{rport}
  # This forwarder will relay the shell to MSF on :{lport}{C.RESET}
{C.YELLOW}└────────────────────────────────────────────────────────┘{C.RESET}
""")


# ──────────────────────────────────────────────
#  SIGNAL HANDLER
# ──────────────────────────────────────────────
def handle_signal(sig, frame):
    print(f"\n{C.YELLOW}[!] Interrupt received — shutting down...{C.RESET}")
    shutdown_event.set()
    for s in listeners:
        try:
            s.close()
        except Exception:
            pass
    if logfile_handle:
        logfile_handle.close()
    sys.exit(0)


# ──────────────────────────────────────────────
#  ARGUMENT PARSER
# ──────────────────────────────────────────────
def build_parser():
    p = argparse.ArgumentParser(
        description="PY-FWD v3.0 — Advanced TCP Port Forwarder",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=f"""
EXAMPLES:
  # Single forward (send :4444 traffic to MSF on :5555)
  python3 portfwd.py --lport 4444 --rhost 127.0.0.1 --rport 5555

  # Multi-port forwarding
  python3 portfwd.py --multi 4444:127.0.0.1/5555,8080:10.0.0.1/80

  # With verbose output, logfile, and MSF hint
  python3 portfwd.py --lport 4444 --rhost 192.168.1.10 --rport 4444 -v --msf --logfile out.log

  # Pivot: expose internal :80 on attacker :8080
  python3 portfwd.py --lport 8080 --rhost 192.168.0.5 --rport 80 --stats
"""
    )

    single = p.add_argument_group("Single-Port Mode")
    single.add_argument("--lhost",   default="0.0.0.0", metavar="HOST",
                        help="Local bind address (default: 0.0.0.0)")
    single.add_argument("--lport",   type=int, metavar="PORT",
                        help="Local port to listen on")
    single.add_argument("--rhost",   metavar="HOST",
                        help="Remote host to forward to")
    single.add_argument("--rport",   type=int, metavar="PORT",
                        help="Remote port to forward to")

    multi = p.add_argument_group("Multi-Port Mode")
    multi.add_argument("--multi",    metavar="RULES",
                        help="Rules: LPORT:RHOST/RPORT[,...]  e.g. 4444:127.0.0.1/5555,8080:10.0.0.1/80")

    opts = p.add_argument_group("Options")
    opts.add_argument("-v", "--verbose",  action="store_true",
                        help="Print every forwarded data chunk")
    opts.add_argument("--logfile",   metavar="FILE",
                        help="Save log output to file")
    opts.add_argument("--timeout",   type=int, default=60, metavar="SEC",
                        help="Socket timeout in seconds (default: 60)")
    opts.add_argument("--bufsize",   type=int, default=4096, metavar="BYTES",
                        help="Receive buffer size (default: 4096)")
    opts.add_argument("--stats",     action="store_true",
                        help="Print live stats every 10 seconds")
    opts.add_argument("--msf",       action="store_true",
                        help="Show Metasploit handler setup commands")
    opts.add_argument("--no-color",  action="store_true",
                        help="Disable ANSI color output")

    return p


# ──────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────
def main():
    global logfile_handle

    signal.signal(signal.SIGINT,  handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    parser = build_parser()
    args   = parser.parse_args()

    if args.no_color:
        C.disable()

    banner()

    # ── Open logfile ───────────────────────────
    if args.logfile:
        try:
            logfile_handle = open(args.logfile, "a")
            log(f"Logging to {C.YELLOW}{args.logfile}{C.RESET}", "INFO")
        except Exception as e:
            log(f"Cannot open logfile: {e}", "ERROR")

    # ── Determine rules ────────────────────────
    rules = []
    if args.multi:
        rules = parse_multi(args.multi)
    else:
        if not all([args.lport, args.rhost, args.rport]):
            log("Specify --lport, --rhost, --rport  or use --multi. See --help.", "FATAL")
            parser.print_help()
            sys.exit(1)
        rules = [(args.lport, args.rhost, args.rport)]

    # ── Print rule table ───────────────────────
    print(f"  {C.BOLD}{'LPORT':<8}  {'RHOST':<20}  {'RPORT':<8}{C.RESET}")
    print(f"  {'─'*8}  {'─'*20}  {'─'*8}")
    for lport, rhost, rport in rules:
        print(f"  {C.GREEN}{lport:<8}{C.RESET}  {C.CYAN}{rhost:<20}{C.RESET}  {C.YELLOW}{rport:<8}{C.RESET}")
    print()

    # ── MSF hint ──────────────────────────────
    if args.msf and rules:
        lport, rhost, rport = rules[0]
        msf_hint(lport, rhost, rport)

    # ── Start listeners ────────────────────────
    threads = []
    for lport, rhost, rport in rules:
        t = threading.Thread(
            target=run_listener,
            args=(args.lhost, lport, rhost, rport, args),
            daemon=True,
            name=f"listener-{lport}"
        )
        t.start()
        threads.append(t)

    # ── Live stats ────────────────────────────
    if args.stats:
        threading.Thread(target=stats_loop, args=(10,), daemon=True).start()

    log(f"{C.GREEN}Ready — waiting for connections. Press Ctrl+C to quit.{C.RESET}", "GOOD")

    # ── Keep main thread alive cleanly ────────
    try:
        while not shutdown_event.is_set():
            time.sleep(0.5)          # FIX: was `while True: pass` — CPU hog + no interrupt
    except KeyboardInterrupt:
        handle_signal(None, None)


if __name__ == "__main__":
    main()
