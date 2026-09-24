#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Refresh the stale MCDU startup image once per Fenix Display process.

Use only Fenix's local display preference and the installed simulator's normal
brightness inputs. Never send page/flight-plan keys or modify vendor binaries.
"""
import json
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import urllib.request

HOME_COCKPIT_REF = "fenix.controls.homeCockpit"
QUERY = ('{dataRef{home:dataRef(name:"' + HOME_COCKPIT_REF + '"){value}'
         'left:dataRef(name:"aircraft.mcdu1.display"){value}'
         'right:dataRef(name:"aircraft.mcdu2.display"){value}}}')
STOP = threading.Event()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("Fenix API redirect rejected")


def api(query, opener):
    request = urllib.request.Request("http://127.0.0.1:8083/graphql",
        data=json.dumps({"query": query}).encode(), headers={"Content-Type": "application/json"})
    with opener.open(request, timeout=2) as response:
        payload = response.read(65537)
    if len(payload) > 65536:
        raise ValueError("Fenix API response too large")
    result = json.loads(payload)
    if result.get("errors") or not isinstance(result.get("data", {}).get("dataRef"), dict):
        raise ValueError("Fenix API unavailable")
    return result["data"]["dataRef"]


def home(value, opener):
    result = api('mutation{dataRef{writeBool(name:"' + HOME_COCKPIT_REF + '",value:' +
                 str(value).lower() + ')}}', opener)
    if result.get("writeBool") is not True:
        raise ValueError("Fenix display preference was not accepted")


def identity(proc):
    return (int(proc.name), proc.joinpath("stat").read_text().rsplit(")", 1)[1].split()[19])


def processes(prefix, proc_root=Path("/proc")):
    found = {}
    expected = {"fenixdisplay.exe", "fenixsystem.exe", "fenixcdu.exe", "fenix.exe", "fenix.gqlgateway.exe"}
    for proc in proc_root.iterdir():
        if not proc.name.isdecimal():
            continue
        try:
            args = proc.joinpath("cmdline").read_bytes().split(b"\0")
            name = args[0].decode(errors="replace").replace("\\", "/").rsplit("/", 1)[-1].lower()
            if name not in expected:
                continue
            env = proc.joinpath("environ").read_bytes().split(b"\0")
            if b"WINEPREFIX=" + os.fsencode(prefix) not in env:
                continue
            if name in found:  # Ambiguous service ownership: do not change it.
                return {}
            found[name] = identity(proc)
        except (OSError, ValueError, IndexError):
            continue
    return found


def owns_api(services, proc_root=Path("/proc")):
    gateway = services.get("fenix.gqlgateway.exe")
    if gateway is None:
        return False
    try:
        proc = proc_root / str(gateway[0])
        if identity(proc) != gateway:
            return False
        sockets = {os.readlink(fd) for fd in (proc / "fd").iterdir()}
        # Wine's gateway and wineserver hold the same listener. Match the inode
        # to this gateway, so a second Wine profile on port 8083 is never used.
        for row in (proc / "net/tcp").read_text().splitlines()[1:]:
            fields = row.split()
            if fields[1] in ("00000000:1F93", "0100007F:1F93") and fields[3] == "0A":
                return "socket:[" + fields[9] + "]" in sockets
    except (OSError, ValueError, IndexError):
        pass
    return False


def save_journal(path, value):
    temporary = path.with_suffix(".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump({"format": 1, "home": value}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def recover(journal, opener):
    if not journal.exists():
        return
    if journal.is_symlink() or journal.stat().st_size > 1024:
        raise ValueError("Invalid display refresh journal")
    saved = json.loads(journal.read_text())
    if saved.get("format") != 1 or type(saved.get("home")) is not bool:
        raise ValueError("Invalid display refresh journal")
    home(saved["home"], opener)
    actual = api(QUERY, opener)["home"]["value"]
    if actual is not saved["home"]:
        raise ValueError("Display preference restoration pending")
    journal.unlink()


def refresh(root, wine, env, opener, journal, service_identity):
    prefix = root / "local/msfs-prefix"
    if processes(prefix) != service_identity or not owns_api(service_identity):
        raise ValueError("Fenix process changed")
    state = api(QUERY, opener)
    original = state["home"]["value"]
    if type(original) is not bool or not all(isinstance(state[key]["value"], str) and
            "<root>" in state[key]["value"] for key in ("left", "right")):
        raise ValueError("MCDU display data not ready")
    helper = prefix / "drive_c/windows/system32/FenixMCDURefresh.exe"
    library = root / "games/MSFS2024/SimConnect_internal.dll"
    if not helper.is_file() or not library.is_file():
        raise ValueError("Installed display refresh dependency unavailable")
    command = [str(wine), str(helper)]
    library_path = "Z:" + str(library).replace("/", "\\")

    def run(mode):
        result = subprocess.run([*command, mode, library_path], env=env, cwd=helper.parent,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=15, check=False)
        if result.returncode:
            raise ValueError("MCDU brightness refresh unavailable")

    run("--probe")
    if STOP.is_set() or processes(prefix) != service_identity:
        return False
    save_journal(journal, original)
    try:
        home(not original, opener)
        time.sleep(0.35)
        # Brightness buttons affect the cached bitmap only in Home Cockpit Mode.
        if original:
            home(True, opener)
            time.sleep(0.35)
        run("--refresh")
    finally:
        # A request may have applied even if its response timed out. Keep the
        # journal until readback confirms restoration, including on next launch.
        recover(journal, opener)
    return True


def main():
    if len(sys.argv) != 2:
        return 2
    root = Path(sys.argv[1]).resolve(strict=True)
    if json.loads((root / "private/runtime.json").read_text()).get("game_id", "msfs2024") != "msfs2024":
        return 0
    lease = os.open(root / "private/fenix-display-refresh.lock",
                    os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lease)
        return 0
    prefix = root / "local/msfs-prefix"
    wine = (root / "runner/files/bin/wine").resolve(strict=True)
    journal = root / "private/fenix-display-refresh.json"
    env = dict(os.environ, WINEPREFIX=str(prefix), WINEDEBUG="-all")
    for key in ("WINE_DLL_FILE_MAP", "WINESERVERSOCKET", "WINEPRELOADRESERVE", "WINELOADERNOEXEC", "WINELOADER", "WINEDLLPATH"):
        env.pop(key, None)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, lambda *_: STOP.set())
    seen = None
    completed = None
    ready_since = 0
    attempts = 0
    while not STOP.wait(1):
        services = processes(prefix)
        display = services.get("fenixdisplay.exe")
        if len(services) != 5 or display is None or not owns_api(services):
            seen, ready_since = None, 0
            continue
        if display != seen:
            seen, ready_since, attempts = display, time.monotonic(), 0
        if journal.exists():
            try:
                recover(journal, opener)
            except (OSError, ValueError, KeyError, TypeError):
                continue
        if display == completed or attempts >= 3 or time.monotonic() - ready_since < 8:
            continue
        try:
            if refresh(root, wine, env, opener, journal, services):
                completed = display
                print("Fenix: MCDU startup image refreshed; display preference restored.", flush=True)
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
            attempts += 1
            ready_since = time.monotonic()
            print("Fenix: display refresh deferred; waiting for local display services.", flush=True)
    try:
        if owns_api(processes(prefix)):
            recover(journal, opener)
    except (OSError, ValueError, KeyError, TypeError):
        pass  # The journal is retained for the next simulator start.
    os.close(lease)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
