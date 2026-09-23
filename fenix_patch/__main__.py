# SPDX-License-Identifier: MIT
import argparse
import json
import os
import sys
from . import core


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fenix A320 Linux Patch — Flightdeck MSFS 2024")
    parser.add_argument("command", choices=("status", "install", "configure", "restore", "installer", "manager", "open", "gui"), nargs="?", default="gui")
    parser.add_argument("--runtime", default=str(core.default_runtime()), help="Flightdeck runtime directory")
    parser.add_argument("--bundle", default=str(core.ROOT), help="Extracted, matching binary release")
    parser.add_argument("--exe", help="Official Fenix Installer downloaded from your account")
    parser.add_argument("--json", action="store_true", help="Emit structured progress for launchers")
    args = parser.parse_args(argv)
    os.umask(0o077)
    def progress(message):
        print(json.dumps({"message": message}) if args.json else message, flush=True)
    try:
        if args.command == "gui":
            from .gui import main as gui
            gui(args.runtime, args.bundle)
        elif args.command == "status":
            print(json.dumps(core.snapshot(args.runtime), indent=2))
        elif args.command == "install":
            core.install(args.runtime, args.bundle, progress)
        elif args.command == "configure":
            core.configure(args.runtime, progress)
        elif args.command == "restore":
            core.restore(args.runtime, progress)
        elif args.command == "installer":
            if not args.exe:
                parser.error("installer requires --exe /path/to/FenixInstaller.exe")
            core.windows_app(args.runtime, args.exe, progress)
        elif args.command == "open":
            core.windows_app(args.runtime, progress=progress)
        elif args.command == "manager":
            core.windows_app(args.runtime, progress=progress, manager=True)
    except (core.PatchError, OSError, ValueError, KeyError) as error:
        print(json.dumps({"error": str(error)}) if args.json else "Fenix patch: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
