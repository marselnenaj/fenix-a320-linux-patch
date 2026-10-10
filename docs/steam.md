# Steam editions of MSFS 2020 and MSFS 2024

The standalone installer can patch the Steam editions directly; Flightdeck is
not required. **This path has not been run with a real Steam simulator yet.**
Its installer, Proton tool and Windows profile handling were verified in a
reproduced Steam library with the pinned Proton; the Fenix displays themselves
were verified only in Flightdeck's MSFS 2024. MSFS 2020 with Fenix is untested.

## Why a separate Proton

The fixes are replacement Wine modules compiled for one exact Wine build.
Steam updates *Proton Experimental* in place, usually several times a month,
so its files stop matching and an overlay cannot be kept on it. The installer
therefore creates its own compatibility tool, **Proton Fenix A320**, in Steam's
`compatibilitytools.d` and leaves every other Proton untouched. Steam never
updates that folder. Only the simulator uses it; other games keep whatever
Proton you play them with, and it does not matter which Proton the simulator
used before.

The base is an unmodified build that matches an overlay in `bundle.json`. The
default is CachyOS Proton `cachyos-11.0-20261005-slr`: the Wine 11 generation
that Proton Experimental currently uses, published as a fixed download. It is
used when installed, otherwise downloaded from its GitHub release (about
350 MB) and verified by checksum. Valve publishes no fixed downloads of its
own Proton builds. `--proton /path` selects another supported build, for
example the earlier `cachyos-10.0-sunset-slr`.

## Install

1. Start the simulator once in Steam, so that its Windows profile exists. Close it.
2. Run `./install.sh` and follow the guided setup, or
   `./install.sh install --steam msfs2024` (`msfs2020`).
3. Let Steam use the new Proton. With Steam closed, the setup's second step or
   `./install.sh select --steam msfs2024` enters it for the simulator. By hand:
   restart Steam, open the simulator's *Properties → Compatibility*, enable
   *Force the use of a specific Steam Play compatibility tool* and choose
   **Proton Fenix A320 (…)**. `status` reports whether Steam has this selection.
4. Continue as usual: run the official Fenix Installer, open Fenix and sign in,
   then apply CPU displays + Legacy readouts.

```sh
./install.sh targets
./install.sh status    --steam msfs2024
./install.sh install   --steam msfs2024
./install.sh select    --steam msfs2024
./install.sh installer --steam msfs2024 --exe "$HOME/Downloads/FenixInstaller.exe"
./install.sh open      --steam msfs2024
./install.sh configure --steam msfs2024
./install.sh restore   --steam msfs2024
```

Steam is found in `~/.local/share/Steam`, `~/.steam`, the Flatpak and the Snap
locations, including additional libraries; `--steam-root` names another one.
Flatpak and Snap Steam are detected but untested.

## What changes

* `steamapps/compatdata/<appid>` is copied, prepared and then exchanged. The
  profile from before the patch is kept in
  `steamapps/fenix-a320-linux-patch/<appid>/before-…`, next to the setup log,
  downloads and the patch state.
* The simulator's `Packages` folder inside the profile (Official and Community
  content) is **moved** into the new profile instead of being copied, so no
  second copy of the simulator content is needed. Restore moves it back.
* `compatibilitytools.d/Proton-Fenix-A320-<variant>` holds the Proton copy with
  the overlay and a `user_settings.py` with the Fenix environment. Like
  Flightdeck, it runs the simulator without esync/fsync.
* `select` changes one entry in Steam's `config/config.vdf`: the compatibility
  tool of this simulator. It refuses while Steam runs, keeps a copy of the file
  next to the patch state and rejects a file it does not fully understand.
  Whether Steam accepts the entry was not checked with a running Steam client.

`restore` returns the earlier profile, keeps the newer one as `retained-…` and
removes the Fenix Proton when no other simulator uses it. With Steam closed it
also returns the simulator's earlier compatibility setting; otherwise choose
another Proton for the simulator in Steam afterwards.

## Limits of this preview

* The installation has to run inside a desktop session. Without a display,
  Microsoft's .NET setup does not finish under Wine 11; the installer refuses
  to start instead.
* Without the kernel's `ntsync` device, Wine 11 uses server-side
  synchronization. The overlay's checks ran in that mode only.

* The automatic MCDU refresh after a display restart is started by Flightdeck's
  launcher and is not part of the Steam path. The fallback window guard for the
  native Wayland driver is not started either; X11/Xwayland uses the patched driver.
* Verifying the simulator's files in Steam does not affect the profile. Deleting
  the simulator's compatibility data in Steam removes the patched profile.
* Updating a patched Steam profile from an older patch release is not
  implemented yet; restore and install again.
