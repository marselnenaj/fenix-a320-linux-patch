# SPDX-License-Identifier: MIT
import http.client
from http.server import ThreadingHTTPServer
import json
import threading
import time
import unittest

from fenix_patch import core, web


class Target:
    kind, label, title = "steam", "Steam · Fixture", "Fixture on Steam"

    def __init__(self):
        self.installed = False
        self.release = threading.Event()

    @property
    def prefix(self):
        return core.ROOT / "absent profile"

    def status(self):
        return {"state": "installed" if self.installed else "available", "installed": self.installed,
                "can_restore": self.installed, "idle": True, "message": ""}

    def install(self, bundle, progress, proton=None):
        progress("working")
        self.release.wait(5)
        self.installed = True

    def select(self, progress):
        raise core.PatchError("Quit Steam completely")


class WebTests(unittest.TestCase):
    def setUp(self):
        self.target = Target()
        self.session = web.Session([self.target], "bundle", None)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), web.handler(self.session, "secret"))
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.target.release.set()
        self.server.shutdown()
        self.server.server_close()

    def request(self, method, path, body=None, host=None, kind="application/json"):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {"Host": host or "127.0.0.1:%d" % self.port}
        if body is not None:
            headers["Content-Type"] = kind
        connection.request(method, path, json.dumps(body) if body is not None else None, headers)
        response = connection.getresponse()
        data = response.read()
        connection.close()
        return response.status, data

    def state(self):
        return json.loads(self.request("GET", "/secret/api/state")[1])

    def wait_idle(self):
        for _ in range(100):
            if not self.state()["busy"]:
                return
            time.sleep(0.02)
        self.fail("operation did not finish")

    def test_only_the_secret_local_address_is_served(self):
        self.assertEqual(self.request("GET", "/secret/")[0], 200)
        self.assertEqual(self.request("GET", "/")[0], 404)
        self.assertEqual(self.request("GET", "/wrong/api/state")[0], 404)
        self.assertEqual(self.request("GET", "/secret/api/state", host="attacker.example:%d" % self.port)[0], 404)
        # A cross-site form cannot send JSON, and nothing may start that way.
        self.assertEqual(self.request("POST", "/secret/api/run", {"action": "install"}, kind="text/plain")[0], 404)
        self.assertFalse(self.target.installed or self.state()["busy"])

    def test_one_step_runs_at_a_time_and_errors_are_shown(self):
        self.assertEqual(self.state()["view"]["current"], "install")
        self.assertEqual(self.request("POST", "/secret/api/run", {"action": "install"})[0], 200)
        state = self.state()
        self.assertEqual((state["busy"], state["view"]["current"]), ("install", "install"))
        self.assertEqual(self.request("POST", "/secret/api/run", {"action": "install"})[0], 400)
        self.assertEqual(self.request("POST", "/secret/api/quit", {})[0], 400)
        self.target.release.set()
        self.wait_idle()
        state = self.state()
        self.assertEqual((state["view"]["current"], state["log"], state["error"]), ("select", ["working"], None))
        self.request("POST", "/secret/api/run", {"action": "select"})
        self.wait_idle()
        self.assertIn("Quit Steam", self.state()["error"])
        self.assertEqual(self.request("POST", "/secret/api/run", {"action": "format-disk"})[0], 200)
        self.wait_idle()
        self.assertEqual(self.state()["error"], "Unknown action")
        self.assertEqual(self.request("POST", "/secret/api/quit", {})[0], 200)
        self.assertTrue(self.session.closed.is_set())


if __name__ == "__main__":
    unittest.main()
