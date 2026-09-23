# Optional early helper placement

The portable window guard starts with the simulator and hides only matching
Fenix helper processes. For Hyprland, early window rules can prevent a brief
flash while each helper first appears. Add the equivalent rules through your
distribution's normal user configuration; the installer does not edit it.

For Omarchy's Lua configuration (`o` is the existing Omarchy helper):

```lua
o.window({class="^steam_proton$", initial_title="^ProSimA322 (System|Display|MCDU)$"}, {
  workspace="special:fenix-helper silent", no_initial_focus=true,
  focus_on_activate=false, pin=false
})
```

Match the **initial title** as well as the class. `steam_proton` alone also
matches the simulator and unrelated applications. If you use a separate window
placement/history service, exclude those helper titles from generic Steam rules.
Do not copy somebody else's monitor coordinates or saved window geometry.

This example is for the Lua configuration used during local verification;
Hyprland configurations using another syntax need the equivalent native rules.
