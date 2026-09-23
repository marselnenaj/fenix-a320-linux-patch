# SPDX-License-Identifier: MIT
"""Small optional Tk front end; the CLI does not require Tk."""
import queue
import threading
import webbrowser
from . import core


def main(runtime, bundle):
    try:
        import tkinter as tk
        from tkinter import filedialog, ttk
    except ImportError:
        raise core.PatchError("Install Python Tk for the graphical installer, or run: ./install.sh install --runtime /path/to/runtime") from None
    window = tk.Tk()
    window.title("Fenix A320 · Linux Patch")
    window.geometry("720x550")
    panel = ttk.Frame(window, padding=24)
    panel.pack(fill="both", expand=True)
    ttk.Label(panel, text="Fenix A320 Linux Patch", font=("sans", 20, "bold")).pack(anchor="w")
    ttk.Label(panel, text="MSFS 2024 · Flightdeck · Community preview", padding=(0, 6)).pack(anchor="w")
    ttk.Label(panel, text="Close MSFS and Fenix before setup. A profile backup is kept.\nRequires your purchased Fenix aircraft and its official installer.").pack(anchor="w", pady=8)
    selected = tk.StringVar(value=runtime)
    row = ttk.Frame(panel); row.pack(fill="x", pady=10)
    ttk.Entry(row, textvariable=selected).pack(side="left", fill="x", expand=True)
    def browse():
        value = filedialog.askdirectory(title="Flightdeck MSFS 2024 runtime", initialdir=selected.get())
        if value: selected.set(value)
    ttk.Button(row, text="Browse…", command=browse).pack(side="right")
    events = queue.Queue()
    buttons = []
    status = tk.StringVar(value="1. Install the patch, then complete steps 2–4.")
    output = tk.Text(panel, height=8, wrap="word", state="disabled")
    busy = False
    def run(operation):
        nonlocal busy
        if busy: return
        busy = True
        for button in buttons: button.configure(state="disabled")
        path = selected.get()
        def worker():
            try: operation(path, lambda message: events.put(message))
            except Exception as error: events.put("Error: " + str(error))
            finally: events.put(None)
        threading.Thread(target=worker, daemon=True).start()
    def installer():
        path = filedialog.askopenfilename(title="Official Fenix Installer", filetypes=[("Windows installer", "*.exe")])
        if path: run(lambda runtime, progress: core.windows_app(runtime, path, progress))
    actions = [
        ("1 · Install patch + Microsoft .NET", lambda: run(lambda path, progress: core.install(path, bundle, progress))),
        ("2 · Run official Fenix Installer…", installer),
        ("3 · Open Fenix / sign in", lambda: run(lambda path, progress: core.windows_app(path, progress=progress))),
        ("4 · Apply CPU displays + Legacy readouts", lambda: run(core.configure)),
        ("Restore original profile (current profile is retained)", lambda: run(core.restore)),
    ]
    for title, command in actions:
        button = ttk.Button(panel, text=title, command=command); button.pack(fill="x", pady=3); buttons.append(button)
    ttk.Button(panel, text="Fenix account / official download", command=lambda: webbrowser.open("https://fenixsim.com/dashboard/")).pack(anchor="w", pady=6)
    ttk.Label(panel, textvariable=status, wraplength=660).pack(anchor="w")
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
