# SPDX-License-Identifier: MIT
"""Guided setup in the user's browser, served only to this computer.

Python's standard library is enough; no GUI toolkit has to be installed. The
address contains a random secret, and requests for another host name are
refused, so other web pages cannot reach the installer.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import subprocess
import threading
import time
import webbrowser

from . import core, guide

IDLE_SECONDS = 15 * 60


class Session:
    def __init__(self, found, bundle, proton):
        self.found, self.bundle, self.proton = list(found), bundle, proton
        self.index = 0
        self.busy = None
        self.log = []
        self.error = None
        self.view = None
        self.lock = threading.Lock()
        self.seen = time.monotonic()
        self.closed = threading.Event()

    def state(self):
        with self.lock:
            self.seen = time.monotonic()
            busy = self.busy
        if not self.found:
            return {"targets": [], "busy": None, "log": [], "error": None, "view": None}
        if busy is None or self.view is None:
            # While an operation runs, its intermediate state is not a problem to report.
            self.view = guide.overview(self.found[self.index])
        return {"targets": [item.label for item in self.found], "index": self.index, "busy": busy,
                "log": self.log[-200:], "error": self.error, "view": self.view,
                "installers": guide.installers(), "can_pick": guide.can_pick_file()}

    def run(self, action, executable=None):
        with self.lock:
            if self.busy:
                raise core.PatchError("Another step is still running.")
            self.busy, self.error = action, None
        target = self.found[self.index]
        def work():
            try:
                guide.perform(target, action, self.bundle, self.log.append, executable, self.proton)
            except (core.PatchError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
                self.error = str(error)
                self.log.append("Error: " + str(error))
            finally:
                with self.lock:
                    self.busy = None
        threading.Thread(target=work, daemon=True).start()

    def select(self, index):
        with self.lock:
            if self.busy:
                raise core.PatchError("Another step is still running.")
            if not 0 <= index < len(self.found):
                raise core.PatchError("No such simulator.")
            self.index, self.view, self.error = index, None, None


def handler(session, secret):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, code, body, kind="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(data)

        def route(self):
            port = self.server.server_address[1]
            if self.headers.get("Host") not in ("127.0.0.1:%d" % port, "localhost:%d" % port):
                return None
            prefix = "/" + secret + "/"
            return self.path[len(prefix):] if self.path.startswith(prefix) else None

        def do_GET(self):
            route = self.route()
            if route == "":
                self.reply(200, PAGE.encode(), "text/html; charset=utf-8")
            elif route == "api/state":
                self.reply(200, session.state())
            else:
                self.reply(404, {"error": "Not found"})

        def do_POST(self):
            route = self.route()
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if route is None or self.headers.get("Content-Type") != "application/json" or length > 65536:
                    return self.reply(404, {"error": "Not found"})
                body = json.loads(self.rfile.read(length) or b"{}")
                if route == "api/run":
                    session.run(str(body.get("action")), body.get("executable") or None)
                elif route == "api/select":
                    session.select(int(body.get("index", -1)))
                elif route == "api/pick":
                    return self.reply(200, {"path": guide.pick_file()})
                elif route == "api/quit":
                    if session.busy:
                        raise core.PatchError("Finish the running step first.")
                    session.closed.set()
                else:
                    return self.reply(404, {"error": "Not found"})
                self.reply(200, {"ok": True})
            except (core.PatchError, ValueError, TypeError) as error:
                self.reply(400, {"error": str(error)})
    return Handler


def serve(found, bundle, proton=None, open_browser=True, port=0):
    session = Session(found, bundle, proton)
    secret = secrets.token_urlsafe(24)
    server = ThreadingHTTPServer(("127.0.0.1", port), handler(session, secret))
    server.daemon_threads = True
    url = "http://127.0.0.1:%d/%s/" % (server.server_address[1], secret)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print("Fenix A320 Linux Patch — setup is open in your browser.\nIf no window appeared, open: " + url +
          "\nKeep this running until you are done; Ctrl+C or “Close installer” ends it.", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        while not session.closed.wait(5):
            with session.lock:
                idle = session.busy is None and time.monotonic() - session.seen > IDLE_SECONDS
            if idle:
                print("No browser window is connected any more; closing.", flush=True)
                break
    except KeyboardInterrupt:
        if session.busy:
            print("\nA step is still running; wait for it to finish.", flush=True)
            while session.busy:
                time.sleep(1)
    finally:
        server.shutdown()
    return url


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fenix A320 · Linux setup</title>
<style>
:root { --bg:#f4f5f7; --card:#fff; --text:#16181d; --muted:#5d6470; --line:#dfe2e8; --accent:#1f6feb; --accent-text:#fff;
        --ok:#1a7f43; --warn-bg:#fff4d6; --warn-text:#6b4a00; --err-bg:#fde8e8; --err-text:#8f1d1d; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#111317; --card:#1a1d23; --text:#e9ebef; --muted:#9aa2af; --line:#2c313a; --accent:#4c8dff; --accent-text:#08101f;
          --ok:#4cc67d; --warn-bg:#3a2f0e; --warn-text:#f3d489; --err-bg:#3d1717; --err-text:#ffb4b4; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--text); font:16px/1.5 system-ui, sans-serif; }
main { max-width:720px; margin:0 auto; padding:32px 16px 64px; }
h1 { font-size:26px; margin:0 0 4px; }
.sub { color:var(--muted); margin:0 0 20px; }
select, input[type=text] { width:100%; padding:9px 10px; border:1px solid var(--line); border-radius:8px; background:var(--card); color:var(--text); font:inherit; }
.banner { padding:12px 14px; border-radius:10px; margin:0 0 16px; }
.warn { background:var(--warn-bg); color:var(--warn-text); } .err { background:var(--err-bg); color:var(--err-text); }
.good { background:var(--card); border:1px solid var(--ok); }
ol { list-style:none; margin:0; padding:0; }
li.step { background:var(--card); border:1px solid var(--line); border-radius:12px; margin:0 0 10px; padding:14px 16px; }
li.step.current { border-color:var(--accent); box-shadow:0 0 0 1px var(--accent); }
.head { display:flex; align-items:center; gap:12px; }
.dot { flex:none; width:28px; height:28px; border-radius:50%; border:2px solid var(--line); display:grid; place-items:center; font-weight:600; font-size:14px; color:var(--muted); }
.done .dot { background:var(--ok); border-color:var(--ok); color:#fff; }
.current .dot { border-color:var(--accent); color:var(--accent); }
.title { font-weight:600; flex:1; } .todo .title { color:var(--muted); }
.body { margin:10px 0 0 40px; } .body p { margin:0 0 12px; } .note { color:var(--muted); font-size:14px; }
.row { display:flex; gap:8px; margin:0 0 12px; }
button { font:inherit; border-radius:8px; padding:9px 16px; border:1px solid var(--line); background:var(--card); color:var(--text); cursor:pointer; }
button.primary { background:var(--accent); border-color:var(--accent); color:var(--accent-text); font-weight:600; }
button.link { border:none; background:none; color:var(--accent); padding:0; font-size:14px; }
button:disabled { opacity:.55; cursor:default; }
.progress { display:flex; gap:10px; align-items:center; color:var(--muted); }
.spin { width:16px; height:16px; border:2px solid var(--line); border-top-color:var(--accent); border-radius:50%; animation:spin 1s linear infinite; flex:none; }
@keyframes spin { to { transform:rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .spin { animation:none; } }
details { margin:18px 0; } summary { cursor:pointer; color:var(--muted); }
pre { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:10px; white-space:pre-wrap; overflow-wrap:anywhere; max-height:260px; overflow:auto; font-size:13px; margin:8px 0 0; }
footer { display:flex; gap:8px; flex-wrap:wrap; margin-top:20px; }
a { color:var(--accent); }
</style>
</head>
<body>
<main>
  <h1>Fenix A320 · Linux setup</h1>
  <p class="sub" id="sub">Looking for your simulator …</p>
  <div id="chooser" hidden><select id="target" aria-label="Simulator"></select><p></p></div>
  <div id="banner"></div>
  <ol id="steps"></ol>
  <details id="logbox"><summary>Activity log</summary><pre id="log"></pre></details>
  <footer id="footer"></footer>
</main>
<script>
"use strict";
let state = null, chosenFile = null, ended = false;
const $ = id => document.getElementById(id);
function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (key === "class") node.className = value; else if (key.startsWith("on")) node[key] = value;
    else if (value !== false && value != null) node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children) if (child != null) node.append(child);
  return node;
}
async function post(path, body) {
  const response = await fetch(path, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body || {})});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Request failed");
  return result;
}
async function run(action, executable) {
  try { await post("api/run", {action, executable}); } catch (error) { alert(error.message); }
  refresh();
}
function fileRow() {
  const input = el("input", {type: "text", id: "file", placeholder: "/home/you/Downloads/FenixInstaller.exe",
                             "aria-label": "Fenix Installer file", value: chosenFile ?? (state.installers[0] || "")});
  input.oninput = () => { chosenFile = input.value; };
  const row = el("div", {class: "row"}, input);
  if (state.can_pick) row.append(el("button", {onclick: async () => {
    try { const result = await post("api/pick"); if (result.path) { chosenFile = result.path; render(); } } catch (error) { alert(error.message); }
  }}, "Browse…"));
  return row;
}
function render() {
  const view = state.view, busy = state.busy;
  if (!view) {
    $("sub").textContent = "No simulator was found.";
    $("banner").replaceChildren(el("div", {class: "banner warn"},
      "Start Microsoft Flight Simulator once in Steam (or set it up in Flightdeck), close it, then start this installer again."));
    $("steps").replaceChildren(); $("footer").replaceChildren(el("button", {onclick: quit}, "Close installer"));
    return;
  }
  $("sub").textContent = view.title + " · community preview";
  $("chooser").hidden = state.targets.length < 2;
  const select = $("target");
  if (select.options.length !== state.targets.length)
    select.replaceChildren(...state.targets.map((label, index) => el("option", {value: index}, label)));
  select.value = state.index; select.disabled = !!busy;
  const banners = [];
  if (state.error && !busy) banners.push(el("div", {class: "banner err", role: "alert"}, state.error));
  if (view.message && !busy) banners.push(el("div", {class: "banner warn"}, view.message));
  if (view.complete && !busy) banners.push(el("div", {class: "banner good"}, el("strong", {}, "Everything is set up. "), view.finish));
  $("banner").replaceChildren(...banners);
  const focused = document.activeElement && document.activeElement.id === "file";
  $("steps").replaceChildren(...view.steps.map((step, index) => {
    const current = step.id === view.current, running = busy === step.id;
    const item = el("li", {class: "step " + (step.done ? "done" : current || running ? "current" : "todo")},
      el("div", {class: "head"}, el("span", {class: "dot", "aria-hidden": "true"}, step.done ? "✓" : String(index + 1)),
        el("span", {class: "title"}, step.title),
        step.done && !busy && ["installer", "open", "configure"].includes(step.id)
          ? el("button", {class: "link", onclick: () => step.needs_file ? redo(step) : run(step.id)}, "Run again") : null));
    if (running) {
      item.append(el("div", {class: "body"}, el("div", {class: "progress", role: "status"}, el("span", {class: "spin"}),
        el("span", {}, state.log[state.log.length - 1] || "Working …"))));
    } else if ((current && !busy) || step.redo) {
      const body = el("div", {class: "body"}, el("p", {}, step.text));
      if (step.link) body.append(el("p", {}, el("a", {href: step.link, target: "_blank", rel: "noreferrer"}, "Open your Fenix account")));
      if (step.needs_file) body.append(fileRow());
      body.append(el("button", {class: "primary", onclick: () => run(step.id, step.needs_file ? $("file").value.trim() : undefined)}, step.button));
      if (step.note) body.append(el("p", {class: "note"}, step.note));
      item.append(body);
    }
    return item;
  }));
  if (focused && $("file")) { $("file").focus(); $("file").setSelectionRange($("file").value.length, $("file").value.length); }
  const log = $("log"); log.textContent = state.log.join("\n"); log.scrollTop = log.scrollHeight;
  $("logbox").hidden = !state.log.length;
  const footer = [];
  if (view.can_restore) footer.push(el("button", {disabled: !!busy, onclick: () => {
    if (confirm("Restore the Windows profile from before the patch? The current profile is kept as a local copy.")) run("restore");
  }}, "Restore original profile"));
  footer.push(el("button", {disabled: !!busy, onclick: quit}, "Close installer"));
  $("footer").replaceChildren(...footer);
}
let redoStep = null;
function redo(step) { redoStep = step.id; for (const item of state.view.steps) item.redo = item.id === redoStep; render(); }
async function quit() {
  try { await post("api/quit"); ended = true; document.querySelector("main").replaceChildren(
    el("h1", {}, "Fenix A320 · Linux setup"), el("p", {class: "sub"}, "The installer is closed. You can close this tab.")); }
  catch (error) { alert(error.message); }
}
async function refresh() {
  if (ended) return;
  try {
    const response = await fetch("api/state");
    const next = await response.json();
    if (next.view && redoStep) for (const step of next.view.steps) step.redo = step.id === redoStep && !next.busy;
    if (next.busy) redoStep = null;
    const changed = JSON.stringify(next) !== JSON.stringify(state);
    state = next;
    if (changed) render();
  } catch (error) {
    $("banner").replaceChildren(el("div", {class: "banner err"}, "The installer is no longer running. Start ./install.sh again."));
  }
}
$("target").onchange = async event => { try { await post("api/select", {index: Number(event.target.value)}); } catch (error) { alert(error.message); } chosenFile = null; refresh(); };
refresh(); setInterval(refresh, 1500);
</script>
</body>
</html>
"""
