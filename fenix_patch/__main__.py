# SPDX-License-Identifier: MIT
import argparse
import json
import os
import sys
from . import core, targets


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fenix A320 Linux Patch — MSFS 2020/2024 on Steam, MSFS 2024 in Flightdeck")
    parser.add_argument("command", choices=("status", "install", "configure", "restore", "installer", "manager", "open", "targets", "gui"), nargs="?", default="gui")
    parser.add_argument("--steam", choices=("msfs2020", "msfs2024"), help="Steam edition of the simulator")
    parser.add_argument("--steam-root", help="Steam directory, when it is not found automatically")
    parser.add_argument("--proton", help="Unmodified, exactly supported Proton build to base the Fenix Proton on")
    parser.add_argument("--runtime", help="Flightdeck runtime directory")
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
            preset = [targets.select(args.runtime, args.steam, args.steam_root)] if args.runtime or args.steam else None
            gui(preset or targets.detect(args.steam_root), args.bundle, args.proton)
            return 0
        if args.command == "targets":
            print(json.dumps([{"kind": item.kind, "label": item.label} for item in targets.detect(args.steam_root)], indent=2))
            return 0
        target = targets.select(args.runtime, args.steam, args.steam_root)
        if args.command == "status":
            print(json.dumps(target.status(), indent=2))
        elif args.command == "install":
            target.install(args.bundle, progress, args.proton)
        elif args.command == "configure":
            target.configure(progress)
        elif args.command == "restore":
            target.restore(progress)
        elif args.command == "installer":
            if not args.exe:
                parser.error("installer requires --exe /path/to/FenixInstaller.exe")
            target.app(progress, args.exe)
        elif args.command == "open":
            target.app(progress)
        elif args.command == "manager":
            target.app(progress, manager=True)
    except (core.PatchError, OSError, ValueError, KeyError) as error:
        print(json.dumps({"error": str(error)}) if args.json else "Fenix patch: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
