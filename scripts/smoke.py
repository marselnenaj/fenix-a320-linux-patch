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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner", required=True, type=Path)
    args = parser.parse_args()
    original = args.runner.resolve(strict=True)
    core.verify_runner(original, core.manifest())
    core.verify_bundle(ROOT)
    work = ROOT / "build/smoke"
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
        for name in ("loader-case-probe", "writecopy-probe", "iocp-smoke", "audio-notification-probe"):
            output = work / ("Fenix.exe" if name == "loader-case-probe" else name + ".exe")
            libraries = ["-lole32", "-luuid"] if name == "audio-notification-probe" else []
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
            run(probe, "0")
            control = work / "UnrelatedApplication.exe"
            shutil.copy2(probe, control)
            run(control, "1")
        finally:
            guard.terminate()
            guard.wait(timeout=10)
    finally:
        subprocess.run([str(runner / "files/bin/wineserver"), "-k"], env=env, check=False)
        subprocess.run([str(runner / "files/bin/wineserver"), "-w"], env=env, timeout=30, check=False)


if __name__ == "__main__": main()
