#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run own-code probes against the release binaries in a fresh disposable prefix."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fenix_patch import core
sys.path.insert(0, str(ROOT / "tests"))
from x11_window_check import check_host_windows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner", required=True, type=Path)
    parser.add_argument("--work", type=Path, default=ROOT / "build/smoke")
    parser.add_argument("--cache", type=Path, default=ROOT / "build/downloads")
    args = parser.parse_args()
    original = args.runner.resolve(strict=True)
    core.verify_runner(original, core.manifest())
    core.verify_bundle(ROOT)
    work = args.work.resolve()
    if work.exists(): raise ValueError("Use a fresh smoke directory")
    work.mkdir(parents=True)
    runner = work / "runner"
    core.copy_tree(original, runner)
    for name in core.manifest()["files"]:
        target = runner / name
        target.unlink()
        shutil.copy2(ROOT / "payload" / name, target)
    prefix = work / "prefix"
    env = core.wine_env(prefix, runner)
    env["WINEDLLOVERRIDES"] = "winemenubuilder.exe=d;mscoree,mshtml="
    def run(*args, **kwargs):
        return subprocess.run([str(runner / "files/bin/wine"), *map(str, args)], env=env,
                              cwd=work, check=True, timeout=180, **kwargs)
    try:
        run("wineboot", "-u", stdout=subprocess.DEVNULL)
        with (work / "geometry-setup.log").open("w") as log:
            wine = core.Wine(prefix, runner, log)
            wine.env = env
            core.graphics_and_fonts(prefix, runner, wine)
            core.prepare_geometry(wine, args.cache.resolve(), ROOT, print)
        for name in ("loader-case-probe", "writecopy-probe", "iocp-smoke", "audio-notification-probe", "shared-cursor-probe"):
            output = work / ("Fenix.exe" if name == "loader-case-probe" else name + ".exe")
            libraries = ["-lole32", "-luuid"] if name == "audio-notification-probe" else []
            if name == "shared-cursor-probe": libraries = ["-luser32", "-lgdi32"]
            subprocess.run(["x86_64-w64-mingw32-gcc", "-O2", "-o", str(output), str(ROOT / "tests" / (name + ".c")), *libraries], check=True)
            if name == "writecopy-probe": env["WINE_TRACK_WRITECOPY"] = "1"
            with (work / (name + ".log")).open("w") as log:
                run(output, stdout=log, stderr=log)
            text = (work / (name + ".log")).read_text()
            print(name + ":\n" + text, flush=True)
            if name == "loader-case-probe":
                if "KERNEL32.DLL" not in text or "KERNELBASE.dll" not in text:
                    raise ValueError("Loader spelling regression")
        probe = work / "FenixDisplay.exe"
        subprocess.run(["x86_64-w64-mingw32-gcc", "-O2", "-o", str(probe), str(ROOT / "tests/window-guard-probe.c"), "-luser32"], check=True)
        guard = subprocess.Popen([str(runner / "files/bin/wine"), str(ROOT / "integration/FenixWindowGuard.exe")], env=env)
        try:
            for executable, title, renamed, hidden in (
                ("FenixDisplay.exe", "ProSimA322 Display", "Fenix Display", True),
                ("FenixSystem.exe", "ProSimA322 System", "FenixSim A320 System 2.4.0.4720", True),
                ("FenixCDU.exe", "ProSimA322 MCDU", "ProSimA322 MCDU", True),
                ("UnrelatedApplication.exe", "ProSimA322 Display", "Fenix Display", False),
                ("Fenix.exe", "ProSimA322 Display", "Fenix Display", False),
                ("FenixDisplay.exe", "Fenix Account", "Fenix Account", False),
                ("FenixSystem.exe", "FenixSim A320 System Login", "FenixSim A320 System 2.", False),
                ("FenixDisplay.exe", "Fenix Settings", "ProSimA322 Display", (False, True)),
            ):
                target = work / executable
                if target != probe: shutil.copy2(probe, target)
                print("X11 scope:", executable, title, flush=True)
                check_host_windows([str(runner / "files/bin/wine"), str(target), "1", title, renamed], env, work, hidden)
            # The guard remains the fallback outside the opt-in X11 driver.
            fallback = dict(env, WINE_FENIX_HELPER_WINDOWS="0")
            subprocess.run([str(runner / "files/bin/wine"), str(probe), "0"], env=fallback, cwd=work, check=True, timeout=30)
        finally:
            guard.terminate()
            guard.wait(timeout=10)
        for name in ("path-metrics-probe", "stroke-joins-probe"):
            target = work / (name + ".exe")
            subprocess.run(["x86_64-w64-mingw32-g++", "-O2", "-static", "-o", str(target),
                            str(ROOT / "tests" / (name + ".cpp")), "-ld2d1", "-ld3d11", "-ldxgi", "-ldxguid", "-lole32"], check=True)
            scoped = work / "FenixDisplay.exe"
            shutil.copy2(target, scoped)
            with (work / (name + ".log")).open("w") as log:
                run(scoped, stdout=log, stderr=log)
            print((work / (name + ".log")).read_text(), flush=True)
            if name == "path-metrics-probe": run(target, "--disabled")
    finally:
        subprocess.run([str(runner / "files/bin/wineserver"), "-k"], env=env, check=False)
        subprocess.run([str(runner / "files/bin/wineserver"), "-w"], env=env, timeout=30, check=False)


if __name__ == "__main__": main()
