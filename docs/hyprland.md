# Helper windows

The opt-in X11/Xwayland driver patch prevents mapping the three Fenix helper
forms to the desktop. It matches both the executable basename and observed
helper title, including renamed Display and versioned System windows. Win32
visibility remains intact so WinForms startup, paints and timers can continue.
The portable guard recognizes driver-handled windows and leaves them alone.
Other executable/title combinations, Fenix sign-in, the installer and the
simulator use normal window handling.

The installer enables this behavior only in the Fenix runtime. No desktop
configuration is changed. The native Wayland driver still uses the portable
hide guard and needs separate live testing.

Optional early placement for older patches on Omarchy's Lua configuration
(`o` is the existing Omarchy helper):

```lua
o.window({class="^steam_proton$", initial_title="^ProSimA322 (System|Display|MCDU)$"}, {
  workspace="special:fenix-helper silent", no_initial_focus=true,
  focus_on_activate=false, pin=false
})
```

Match the initial title as well as the class. `steam_proton` alone also matches
the simulator and unrelated applications. Other Hyprland configuration syntaxes
need equivalent native rules. Do not copy monitor coordinates or saved geometry.
