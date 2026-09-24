# SPDX-License-Identifier: MIT
"""Check actual X11 mapping while the Win32 probe keeps its window alive."""
import ctypes as c
import os
import re
import subprocess


class Attributes(c.Structure):
    _fields_ = [(name, c.c_int) for name in ("x", "y", "width", "height", "border_width", "depth")]
    _fields_ += [("visual", c.c_void_p), ("root", c.c_ulong), ("class_", c.c_int),
                ("bit_gravity", c.c_int), ("win_gravity", c.c_int), ("backing_store", c.c_int),
                ("backing_planes", c.c_ulong), ("backing_pixel", c.c_ulong), ("save_under", c.c_int),
                ("colormap", c.c_ulong), ("map_installed", c.c_int), ("map_state", c.c_int),
                ("all_event_masks", c.c_long), ("your_event_mask", c.c_long),
                ("do_not_propagate_mask", c.c_long), ("override_redirect", c.c_int), ("screen", c.c_void_p)]


def check_host_windows(command, env, cwd, hidden):
    expected = hidden if isinstance(hidden, tuple) else (hidden, hidden)
    if not env.get("DISPLAY"):
        raise RuntimeError("X11 window checks require DISPLAY (Xwayland or Xvfb is sufficient)")
    x11 = c.CDLL("libX11.so.6")
    x11.XOpenDisplay.argtypes = [c.c_char_p]
    x11.XOpenDisplay.restype = c.c_void_p
    x11.XGetWindowAttributes.argtypes = [c.c_void_p, c.c_ulong, c.POINTER(Attributes)]
    x11.XCloseDisplay.argtypes = [c.c_void_p]
    display = x11.XOpenDisplay(env["DISPLAY"].encode())
    if not display:
        raise RuntimeError("Cannot open test X11 display")
    count = 0
    try:
        with subprocess.Popen(command, env=env, cwd=cwd, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, bufsize=1) as child:
            try:
                for line in child.stdout:
                    print(line.rstrip(), flush=True)
                    if line.startswith("window_visible="):
                        break
                    match = re.match(r"host xid=(\d+) helper=(\d+) logical_visible=(\d+)", line)
                    if not match:
                        continue
                    xid, helper, visible = map(int, match.groups())
                    attributes = Attributes()
                    if not xid or not x11.XGetWindowAttributes(display, xid, c.byref(attributes)):
                        raise RuntimeError("Probe did not expose a live X11 window")
                    if count >= len(expected) or bool(helper) != expected[count] or visible != 1 or bool(attributes.map_state) == expected[count]:
                        raise RuntimeError(f"Unexpected X11 state: helper={helper}, Win32={visible}, mapped={attributes.map_state}")
                    count += 1
                if child.wait(timeout=30) or count != 2:
                    raise RuntimeError("Incomplete window mapping probe")
            except BaseException:
                child.kill()
                child.wait()
                raise
    finally:
        x11.XCloseDisplay(display)
