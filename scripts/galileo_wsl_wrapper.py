#!/usr/bin/env python3
"""GhostSignal Galileo bridge: makes the WSL `usrp_galileo` binary look like a
native Windows `galileo-sdr-sim`. Translates Windows file-path arguments to WSL
paths (via `wslpath`) and forwards to the Linux binary in the Ubuntu distro.

Installed as C:\\Users\\chexu\\bin\\galileo_wsl_wrapper.py, invoked by
galileo-sdr-sim.cmd (same dir, on PATH). GhostSignal resolves the tool by the
bare name `galileo-sdr-sim` and runs it like any other generator.
"""
import os
import sys
import shlex
import subprocess

DISTRO = "Ubuntu"
WSL_BIN = "/root/galileo-sdr-sim/build/usrp_galileo"
# Flags whose following value is a filesystem path and must be translated.
PATH_FLAGS = {"-e", "-x", "-u", "-g", "-o", "-r", "-n"}


def to_wsl_path(win_path: str) -> str:
    """Convert a Windows path to its /mnt/<drive>/... WSL form in pure Python.

    We do NOT shell out to `wslpath`: passing a backslash path through wsl.exe
    strips the backslashes. A forward-slash /mnt path survives wsl.exe's arg
    forwarding intact. Already-POSIX paths (/mnt/..., /root/...) pass through.
    """
    if win_path.startswith("/"):
        return win_path
    p = os.path.abspath(win_path)
    drive, rest = os.path.splitdrive(p)
    if not drive:
        return p.replace("\\", "/")
    return "/mnt/" + drive[0].lower() + rest.replace("\\", "/")


def main() -> int:
    args = sys.argv[1:]
    forwarded = []
    i = 0
    while i < len(args):
        a = args[i]
        forwarded.append(a)
        if a in PATH_FLAGS and i + 1 < len(args):
            forwarded.append(to_wsl_path(args[i + 1]))
            i += 2
            continue
        i += 1
    # Build a quoted shell command and run via `bash -lc` so bash parses the
    # args. (Passing them as direct `wsl.exe <cmd> <args>` mangles paths — the
    # forwarder drops characters like a trailing ".csv".)
    inner = WSL_BIN + " " + " ".join(shlex.quote(a) for a in forwarded)
    cmd = ["wsl.exe", "-d", DISTRO, "-u", "root", "bash", "-lc", inner]
    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    sys.exit(main())
