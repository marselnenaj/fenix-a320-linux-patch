# SPDX-License-Identifier: MIT
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from fenix_patch import core, steam, targets


class SteamTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "Steam client"
        self.library = self.base / "second library"
        self.bundle = self.base / "bundle"
        self.proton = self.root / "compatibilitytools.d/pinned-proton"
        (self.root / "steamapps").mkdir(parents=True)
        self.put(self.root / "steamapps/libraryfolders.vdf",
                 '"libraryfolders"\n{\n "0" { "path" "%s" }\n "1" { "path" "%s" }\n "2" { "path" "/missing/library" }\n}\n'
                 % (self.root, self.library))
        self.put(self.library / "steamapps/appmanifest_2537590.acf", "manifest")
        self.item = steam.Target("msfs2024", self.root, self.library)
        self.prefix = self.item.prefix
        (self.prefix / "drive_c/windows/system32").mkdir(parents=True)
        (self.prefix / "dosdevices").mkdir()
        (self.prefix / "dosdevices/c:").symlink_to(self.prefix / "drive_c")
        self.put(self.prefix / "system.reg", "original registry")
        self.put(self.item.compat / "version", "11.0-100")
        self.settings = self.prefix / "drive_c/users/steamuser/AppData/Roaming/Microsoft Flight Simulator 2024"
        self.put(self.settings / "UserCfg.opt", "settings")
        self.put(self.settings / "Packages/Community/addon/layout.json", "large simulator content")
        self.put(self.proton / "proton", "launcher")
        self.put(self.proton / "version", "fixture version")
        self.put(self.proton / "files/bin/wine", "fixture Wine")
        files = ("files/lib/wine/x86_64-windows/ntdll.dll", "files/bin/wineserver")
        for name in files:
            self.put(self.proton / name, "old " + name)
            self.put(self.bundle / "payload/variants/fixture" / name, "new " + name)
        for name in ("FenixWindowGuard.exe", "FenixMCDURefresh.exe", "fenix-display-refresh.py"):
            self.put(self.bundle / "integration" / name, "synthetic " + name)
        entry = {"runner_version": "1 fixture version",
                 "files": {name: core.digest(self.bundle / "payload/variants/fixture" / name) for name in files},
                 "runner_files": {name: core.digest(self.proton / name) for name in (*files, "files/bin/wine")}}
        self.lock = {"format": 1, "version": "fixture", "runner_version": "base", "files": {}, "runner_files": {"absent": "0"},
                     "integration": {p.name: core.digest(p) for p in (self.bundle / "integration").iterdir()},
                     "variants": {"fixture": entry}}
        self.put(self.bundle / "bundle.json", json.dumps(self.lock))
        def manifest(variant=None):
            return {**self.lock, **self.lock["variants"][variant], "variant": variant} if variant else self.lock
        self.setups = []
        def proton_setup(tool, compat, item, log):
            # Proton would settle its own profile version here.
            self.setups.append((tool, core.digest(tool / "files/bin/wineserver")))
            (compat / "version").write_text("tool version")
        self.patches = [patch.object(core, "manifest", side_effect=manifest), patch.object(core, "host_check"),
                        patch.object(core, "Wine"), patch.object(core, "prepare_framework"),
                        patch.object(core, "graphics_and_fonts"), patch.object(core, "prepare_geometry"),
                        patch.object(steam, "proton_setup", side_effect=proton_setup),
                        patch.object(steam, "PROTON_DOWNLOADS", {})]
        for item in self.patches: item.start()

    def tearDown(self):
        for item in reversed(self.patches): item.stop()
        self.temp.cleanup()

    def put(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)

    @property
    def tool(self):
        return self.root / "compatibilitytools.d/Proton-Fenix-A320-fixture"

    def test_detects_simulator_in_secondary_library_only_with_profile(self):
        found = steam.targets(str(self.root))
        self.assertEqual([(item.game, item.library) for item in found], [("msfs2024", self.library.resolve())])
        with self.assertRaisesRegex(core.PatchError, "start it once"):
            steam.target("msfs2020", str(self.root))
        self.assertEqual(targets.select(game="msfs2024", steam_root=str(self.root)).item.compat, found[0].compat)

    def test_install_creates_separate_tool_and_restore_returns_everything(self):
        original_tool = {p.relative_to(self.proton): p.read_text() for p in self.proton.rglob("*") if p.is_file()}
        messages = []
        steam.install(self.item, self.bundle, messages.append)
        state = core.read_json(self.item.marker)
        self.assertEqual((state["state"], state["tool"], state["variant"]), ("installed", self.tool.name, "fixture"))
        # The user's own Proton is never modified; the overlay lives in the copy.
        self.assertEqual({p.relative_to(self.proton): p.read_text() for p in self.proton.rglob("*") if p.is_file()}, original_tool)
        self.assertEqual((self.tool / "files/bin/wineserver").read_text(), "new files/bin/wineserver")
        self.assertEqual((self.tool / "files/bin/wine").read_text(), "fixture Wine")
        # Proton prepared the profile before the overlay replaced any binary.
        self.assertEqual(self.setups, [(self.tool, core.digest(self.proton / "files/bin/wineserver"))])
        self.assertIn('"Proton-Fenix-A320-fixture"', (self.tool / "compatibilitytool.vdf").read_text())
        namespace = {}
        exec((self.tool / "user_settings.py").read_text(), namespace)
        self.assertIn("FlightSimulator.exe", namespace["user_settings"]["WINE_TRACK_WRITECOPY"])
        self.assertEqual(namespace["user_settings"]["WINE_D2D1_GEOMETRY_PROVIDER"], "FenixDisplay.exe")
        self.assertEqual((self.prefix / "drive_c/windows/system32/ntdll.dll").read_text(), "new files/lib/wine/x86_64-windows/ntdll.dll")
        self.assertEqual((self.item.compat / "version").read_text(), "tool version")
        self.assertEqual(os.readlink(self.prefix / "dosdevices/c:"), "../drive_c")
        # Simulator content was moved, not duplicated.
        previous = self.item.state / state["previous"]
        self.assertEqual((self.settings / "Packages/Community/addon/layout.json").read_text(), "large simulator content")
        self.assertFalse((previous / state["carried"][0]).exists())
        self.assertEqual((previous / "pfx/system.reg").read_text(), "original registry")
        self.assertIn("Properties → Compatibility", messages[-1])
        steam.install(self.item, self.bundle)
        self.assertEqual(core.read_json(self.item.marker), state)
        self.put(self.settings / "Packages/Community/fenix/aircraft.cfg", "installed after the patch")
        self.put(self.prefix / "new-user-state", "retain this")
        steam.restore(self.item)
        self.assertEqual((self.item.compat / "version").read_text(), "11.0-100")
        self.assertFalse((self.prefix / "drive_c/windows/system32/ntdll.dll").exists())
        self.assertEqual((self.settings / "Packages/Community/addon/layout.json").read_text(), "large simulator content")
        self.assertEqual((self.settings / "Packages/Community/fenix/aircraft.cfg").read_text(), "installed after the patch")
        self.assertFalse(self.tool.exists())
        self.assertFalse(self.item.marker.exists())
        self.assertEqual(len([p for p in self.item.state.glob("retained-*/pfx/new-user-state")]), 1)
        self.assertTrue(self.proton.is_dir())

    def test_unsupported_proton_changes_nothing(self):
        self.put(self.proton / "files/bin/wine", "an updated Proton")
        before = sorted(str(p) for p in self.item.compat.rglob("*"))
        with self.assertRaisesRegex(core.PatchError, "No supported Proton"):
            steam.install(self.item, self.bundle)
        self.assertEqual(sorted(str(p) for p in self.item.compat.rglob("*")), before)
        self.assertFalse(self.tool.exists())
        steam.restore(self.item)
        self.assertFalse(self.item.marker.exists())
        self.assertEqual((self.prefix / "system.reg").read_text(), "original registry")

    def test_failed_setup_keeps_original_profile_and_restore_cleans_up(self):
        core.prepare_geometry.side_effect = core.PatchError("synthetic failure")
        with self.assertRaisesRegex(core.PatchError, "synthetic failure"):
            steam.install(self.item, self.bundle)
        self.assertEqual((self.item.compat / "version").read_text(), "11.0-100")
        self.assertEqual((self.settings / "Packages/Community/addon/layout.json").read_text(), "large simulator content")
        self.assertEqual((self.tool / "files/bin/wineserver").read_text(), "old files/bin/wineserver")
        with self.assertRaisesRegex(core.PatchError, "Restore"):
            steam.install(self.item, self.bundle)
        with self.assertRaisesRegex(core.PatchError, "Finish patch installation"):
            steam.configure(self.item)
        steam.restore(self.item)
        self.assertFalse(self.tool.exists())
        self.assertEqual((self.prefix / "system.reg").read_text(), "original registry")
        core.prepare_geometry.side_effect = None
        steam.install(self.item, self.bundle)
        self.assertEqual(core.read_json(self.item.marker)["state"], "installed")

    def test_recovery_at_each_commit_step(self):
        real = os.rename
        for failing in (1, 2, 3):
            with self.subTest(step=failing):
                calls = []
                def rename(source, destination):
                    calls.append(source)
                    if len(calls) == failing:
                        raise OSError("synthetic power loss")
                    return real(source, destination)
                with patch.object(os, "rename", side_effect=rename), self.assertRaises(OSError):
                    steam.install(self.item, self.bundle)
                self.assertEqual(core.read_json(self.item.marker)["state"], "committing")
                # Found by its patch state even while no profile is in place.
                found = steam.target("msfs2024", str(self.root))
                self.assertEqual(found.compat, self.item.compat.resolve())
                self.assertEqual(steam.snapshot(found)["state"], "committing")
                steam.restore(found)
                self.assertEqual((self.item.compat / "version").read_text(), "11.0-100")
                self.assertEqual((self.prefix / "system.reg").read_text(), "original registry")
                self.assertEqual((self.settings / "Packages/Community/addon/layout.json").read_text(), "large simulator content")
                self.assertFalse(self.tool.exists())

    def test_second_simulator_shares_the_tool_until_both_are_restored(self):
        self.put(self.library / "steamapps/appmanifest_1250410.acf", "manifest")
        other = steam.Target("msfs2020", self.root, self.library)
        (other.prefix / "drive_c/windows/system32").mkdir(parents=True)
        self.put(other.prefix / "system.reg", "2020 registry")
        steam.install(self.item, self.bundle)
        self.put(self.proton / "files/bin/wine", "Steam updated this Proton meanwhile")
        steam.install(other, self.bundle)
        self.assertEqual(len(self.setups), 2)
        self.assertFalse(core.read_json(other.marker)["tool_created"])
        steam.restore(self.item)
        self.assertTrue(self.tool.is_dir())
        steam.verify_installed(other, core.read_json(other.marker))
        steam.restore(other)
        self.assertFalse(self.tool.exists())

    def test_changed_tool_and_running_profile_are_rejected(self):
        steam.install(self.item, self.bundle)
        with patch.object(core, "ensure_idle", side_effect=core.PatchError("Close MSFS")):
            with self.assertRaisesRegex(core.PatchError, "Close MSFS"):
                steam.configure(self.item)
        self.put(self.tool / "files/bin/wineserver", "tampered")
        with self.assertRaisesRegex(core.PatchError, "differs from the supported build"):
            steam.configure(self.item)
        with self.assertRaisesRegex(core.PatchError, "differs from the supported build"):
            steam.windows_app(self.item)

    def test_configure_registers_autostart_in_the_matching_simulator_folder(self):
        steam.install(self.item, self.bundle)
        self.put(self.prefix / core.PROGRAM / "Fenix.exe", "MZ")
        self.put(self.prefix / core.CONFIG / "fenixConfig.xml", "<config><displayMode>GPU</displayMode></config>")
        self.put(self.prefix / core.CONFIG / "persistancy.xml", "<state/>")
        steam.configure(self.item)
        entry = ET.parse(self.settings / "exe.xml").getroot().find("Launch.Addon")
        self.assertEqual(entry.findtext("Path"), r"C:\Program Files\FenixSim A320\deps\FenixBootstrapper.exe")
        self.assertEqual(ET.parse(self.prefix / core.CONFIG / "fenixConfig.xml").getroot().findtext("displayMode"), "CPU")
        self.assertTrue(core.read_json(self.item.marker)["configured"])
        status = steam.snapshot(self.item)
        self.assertTrue(status["installed"] and status["fenix_installed"])
        self.assertFalse(status["tool_selected"])
        self.put(self.root / "config/config.vdf", '"CompatToolMapping"\n{\n "2537590"\n {\n  "name"  "Proton-Fenix-A320-fixture"\n  "config" ""\n }\n}\n')
        self.assertTrue(steam.snapshot(self.item)["tool_selected"])

    def test_symlinked_profile_is_rejected(self):
        moved = self.base / "elsewhere"
        os.rename(self.item.compat, moved)
        self.item.compat.symlink_to(moved)
        with self.assertRaisesRegex(core.PatchError, "ordinary directories"):
            steam.install(self.item, self.bundle)


if __name__ == "__main__":
    unittest.main()
