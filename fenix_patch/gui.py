# SPDX-License-Identifier: MIT
"""Small optional Tk front end; the CLI does not require Tk."""
import queue
import threading
import webbrowser
from . import core, targets


def main(found, bundle, proton=None):
    try:
        import tkinter as tk
        from tkinter import filedialog, ttk
    except ImportError:
        raise core.PatchError("Install Python Tk for the graphical installer, or run: ./install.sh install --steam msfs2024") from None
    found = list(found)
    window = tk.Tk()
    window.title("Fenix A320 · Linux Patch")
    window.geometry("760x600")
    panel = ttk.Frame(window, padding=24)
    panel.pack(fill="both", expand=True)
    ttk.Label(panel, text="Fenix A320 Linux Patch", font=("sans", 20, "bold")).pack(anchor="w")
    ttk.Label(panel, text="MSFS 2020 / 2024 · Steam and Flightdeck · Community preview", padding=(0, 6)).pack(anchor="w")
    ttk.Label(panel, text="Close MSFS and Fenix before setup. A profile backup is kept.\nRequires your purchased Fenix aircraft and its official installer.").pack(anchor="w", pady=8)
    row = ttk.Frame(panel); row.pack(fill="x", pady=10)
    choice = ttk.Combobox(row, state="readonly", values=[item.label for item in found])
    choice.pack(side="left", fill="x", expand=True)
    if found: choice.current(0)
    def browse():
        value = filedialog.askdirectory(title="Flightdeck MSFS 2024 runtime", initialdir=str(core.default_runtime()))
        if value:
            found.append(targets.Flightdeck(value))
            choice.configure(values=[item.label for item in found]); choice.current(len(found) - 1)
    ttk.Button(row, text="Flightdeck runtime…", command=browse).pack(side="right", padx=(8, 0))
    events = queue.Queue()
    buttons = []
    status = tk.StringVar(value="1. Install the patch, then complete steps 2–4." if found else
                          "No simulator found. Start MSFS once in Steam and reopen this installer, or choose a Flightdeck runtime.")
    output = tk.Text(panel, height=8, wrap="word", state="disabled")
    busy = False
    def run(operation):
        nonlocal busy
        if busy: return
        if choice.current() < 0:
            status.set("Choose a simulator first.")
            return
        busy = True
        for button in buttons: button.configure(state="disabled")
        target = found[choice.current()]
        def worker():
            try: operation(target, lambda message: events.put(message))
            except Exception as error: events.put("Error: " + str(error))
            finally: events.put(None)
        threading.Thread(target=worker, daemon=True).start()
    def installer():
        path = filedialog.askopenfilename(title="Official Fenix Installer", filetypes=[("Windows installer", "*.exe")])
        if path: run(lambda target, progress: target.app(progress, path))
    actions = [
        ("1 · Install patch + Microsoft .NET", lambda: run(lambda target, progress: target.install(bundle, progress, proton))),
        ("2 · Run official Fenix Installer…", installer),
        ("3 · Open Fenix / sign in", lambda: run(lambda target, progress: target.app(progress))),
        ("4 · Apply CPU displays + Legacy readouts", lambda: run(lambda target, progress: target.configure(progress))),
        ("Restore original profile (current profile is retained)", lambda: run(lambda target, progress: target.restore(progress))),
    ]
    for title, command in actions:
        button = ttk.Button(panel, text=title, command=command); button.pack(fill="x", pady=3); buttons.append(button)
    ttk.Button(panel, text="Fenix account / official download", command=lambda: webbrowser.open("https://fenixsim.com/dashboard/")).pack(anchor="w", pady=6)
    ttk.Label(panel, textvariable=status, wraplength=700).pack(anchor="w")
    output.pack(fill="both", expand=True, pady=8)
    def poll():
        nonlocal busy
        while not events.empty():
            message = events.get()
            if message is None:
                busy = False
                for button in buttons: button.configure(state="normal")
            else:
                status.set(message)
                output.configure(state="normal"); output.insert("end", message + "\n"); output.see("end"); output.configure(state="disabled")
        window.after(150, poll)
    def close():
        if busy: status.set("Finish the running setup before closing this window.")
        else: window.destroy()
    window.protocol("WM_DELETE_WINDOW", close)
    poll(); window.mainloop()
