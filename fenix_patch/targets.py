# SPDX-License-Identifier: MIT
"""The two kinds of simulator installation behind one small interface."""
from pathlib import Path

from . import core, steam


class Flightdeck:
    kind = "flightdeck"

    def __init__(self, runtime):
        self.runtime = str(runtime)
        self.label = "Flightdeck · " + self.runtime

    def install(self, bundle, progress, proton=None):
        core.install(self.runtime, bundle, progress)

    def configure(self, progress):
        core.configure(self.runtime, progress)

    def restore(self, progress):
        core.restore(self.runtime, progress)

    def app(self, progress, executable=None, manager=False):
        core.windows_app(self.runtime, executable, progress, manager=manager)

    def status(self):
        return core.snapshot(self.runtime)


class Steam:
    kind = "steam"

    def __init__(self, item):
        self.item = item
        self.label = "Steam · %s · %s" % (item.title, item.library)

    def install(self, bundle, progress, proton=None):
        steam.install(self.item, bundle, progress, proton)

    def configure(self, progress):
        steam.configure(self.item, progress)

    def restore(self, progress):
        steam.restore(self.item, progress)

    def app(self, progress, executable=None, manager=False):
        steam.windows_app(self.item, executable, progress, manager=manager)

    def status(self):
        return steam.snapshot(self.item)


def detect(steam_root=None):
    """Steam simulators first, then an existing Flightdeck MSFS 2024 runtime."""
    found = [Steam(item) for item in steam.targets(steam_root)]
    runtime = core.default_runtime()
    if (runtime / "private/runtime.json").is_file():
        found.append(Flightdeck(runtime))
    return found


def select(runtime=None, game=None, steam_root=None):
    if runtime and game:
        raise core.PatchError("Use either --runtime (Flightdeck) or --steam, not both.")
    if runtime:
        return Flightdeck(runtime)
    if game:
        return Steam(steam.target(game, steam_root))
    found = detect(steam_root)
    if len(found) == 1:
        return found[0]
    if not found:
        raise core.PatchError("No simulator was found. Start MSFS once in Steam, or pass --steam-root or --runtime.")
    raise core.PatchError("Several simulators were found. Choose one with --steam msfs2020, --steam msfs2024 or --runtime:\n" +
                          "\n".join("  " + item.label for item in found))
