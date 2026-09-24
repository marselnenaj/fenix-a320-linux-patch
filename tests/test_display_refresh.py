# SPDX-License-Identifier: MIT
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / "integration/fenix-display-refresh.py"
SPEC = importlib.util.spec_from_file_location("display_refresh", SOURCE)
refresh = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(refresh)


class DisplayRefreshTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.journal = self.root / "private/fenix-display-refresh.json"
        self.journal.parent.mkdir()
        for name in ("local/msfs-prefix/drive_c/windows/system32/FenixMCDURefresh.exe",
                     "games/MSFS2024/SimConnect_internal.dll"):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"fixture")
        self.services = {"fenixdisplay.exe": (10, "1")}
        self.state = False
        self.writes = []
        self.calls = []
        refresh.STOP.clear()

    def api(self, _query, _opener):
        return {"home": {"value": self.state}, "left": {"value": "<root>LEFT</root>"},
                "right": {"value": "<root>RIGHT</root>"}}

    def home(self, value, _opener):
        self.state = value
        self.writes.append(value)

    def command(self, args, **kwargs):
        self.assertEqual(args[2], "--probe" if not self.calls else "--refresh")
        self.calls.append(args)
        return Mock(returncode=0)

    def run_refresh(self, command=None):
        with patch.object(refresh, "processes", return_value=self.services), \
             patch.object(refresh, "owns_api", return_value=True), \
             patch.object(refresh, "api", side_effect=self.api), \
             patch.object(refresh, "home", side_effect=self.home), \
             patch.object(refresh.subprocess, "run", side_effect=command or self.command), \
             patch.object(refresh.time, "sleep"):
            return refresh.refresh(self.root, Path("/fixture/wine"), {}, None, self.journal, self.services)

    def test_default_mode_and_pages_are_preserved(self):
        self.assertTrue(self.run_refresh())
        self.assertEqual(self.writes, [True, False])
        self.assertIs(self.state, False)
        self.assertFalse(self.journal.exists())
        self.assertEqual(len(self.calls), 2)

    def test_existing_home_cockpit_mode_is_restored(self):
        self.state = True
        self.assertTrue(self.run_refresh())
        self.assertEqual(self.writes, [False, True, True])
        self.assertIs(self.state, True)

    def test_failed_probe_does_not_change_preferences(self):
        with self.assertRaises(ValueError):
            self.run_refresh(lambda *a, **k: Mock(returncode=1))
        self.assertEqual(self.writes, [])
        self.assertFalse(self.journal.exists())

    def test_failed_brightness_refresh_restores_preference(self):
        def command(args, **kwargs):
            return Mock(returncode=0 if args[2] == "--probe" else 1)
        with self.assertRaises(ValueError):
            self.run_refresh(command)
        self.assertIs(self.state, False)
        self.assertFalse(self.journal.exists())

    def test_process_change_does_not_send_commands(self):
        with patch.object(refresh, "processes", return_value={}):
            with self.assertRaisesRegex(ValueError, "process changed"):
                refresh.refresh(self.root, Path("wine"), {}, None, self.journal, self.services)
        self.assertFalse(self.journal.exists())

    def test_different_api_owner_does_not_send_commands(self):
        with patch.object(refresh, "processes", return_value=self.services), \
             patch.object(refresh, "owns_api", return_value=False):
            with self.assertRaisesRegex(ValueError, "process changed"):
                refresh.refresh(self.root, Path("wine"), {}, None, self.journal, self.services)

    def test_uncertain_write_is_restored_from_durable_journal(self):
        refresh.save_journal(self.journal, False)
        self.state = True
        with patch.object(refresh, "home", side_effect=OSError("offline")):
            with self.assertRaises(OSError):
                refresh.recover(self.journal, None)
        self.assertTrue(self.journal.exists())
        with patch.object(refresh, "home", side_effect=self.home), \
             patch.object(refresh, "api", side_effect=self.api):
            refresh.recover(self.journal, None)
        self.assertFalse(self.journal.exists())
        self.assertIs(self.state, False)

    def test_unconfirmed_restore_retains_journal(self):
        refresh.save_journal(self.journal, False)
        self.state = True
        with patch.object(refresh, "home"), patch.object(refresh, "api", side_effect=self.api):
            with self.assertRaisesRegex(ValueError, "restoration pending"):
                refresh.recover(self.journal, None)
        self.assertTrue(self.journal.exists())

    def test_invalid_and_symlinked_journals_are_rejected(self):
        self.journal.write_text(json.dumps({"format": 1, "home": "false"}))
        with self.assertRaises(ValueError):
            refresh.recover(self.journal, None)
        self.journal.unlink()
        target = self.root / "untouched"
        target.write_text("private fixture")
        self.journal.symlink_to(target)
        with self.assertRaises(ValueError):
            refresh.recover(self.journal, None)
        self.assertEqual(target.read_text(), "private fixture")

    def test_cancellation_before_change_is_quiet(self):
        refresh.STOP.set()
        self.assertFalse(self.run_refresh())
        self.assertEqual(self.writes, [])
        self.assertFalse(self.journal.exists())


if __name__ == "__main__":
    unittest.main()
