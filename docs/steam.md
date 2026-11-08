# Steam editions of MSFS 2020 and MSFS 2024

The standalone installer can patch the Steam editions directly; Flightdeck is
not required. **The maintainer has not run this path with a real Steam
simulator.** User reports cover working displays on Steam MSFS 2024 with the
`cachyos-11` base and, after preview.11's Gateway correction, Steam MSFS 2020
with Fenix 3.0.0.7454 on CachyOS 11 / NVIDIA-PRIME. The installer, Proton tool
and Windows profile handling were checked in a reproduced Steam library.
These observations do not establish complete-flight stability.

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
   then apply the settings. This sets the supported display renderer and starts Fenix with the
   simulator. Fenix may create the file for the Legacy FCU readouts only once
   the aircraft has been loaded; the setup then asks you to load it once and
   apply the setting again.

## Update

Run `./install.sh` from the new release and choose **Update patch**, or
`./install.sh install --steam msfs2024`. Close the simulator and Fenix first.
The overlay in the *Proton Fenix A320* tool is replaced; the Windows profile,
Fenix and its sign-in are retained, and Restore still returns the
profile from before the first installation. An automatic CPU setting migrates
to GPU on the supported Proton 11 overlays; an explicit CPU fallback is retained.
CachyOS Proton 10 remains CPU-only. When MSFS 2020 and 2024 share the
tool, update both: the second one only records the new version.

If an update stops with **The Wine runner differs from the supported build**,
one of the checked runner files does not match the expected build. Updates from
preview.11 are supported; that version alone is not a reason to restore the
profile or reinstall the aircraft. Keep the installation as it is while the
mismatch is investigated. In your issue, include the patch version you are
updating from and to, the Proton variant, and the full error. New source builds
also show the runner directory and expected/actual SHA-256 hashes. In an older
release, use `sha256sum` on the named file inside the installed
`Proton-Fenix-A320-<variant>` directory to obtain the actual hash. Review local
paths before posting. Do not replace individual runner DLLs or bypass the
checksum check; the overlay requires a matching Wine build.

### Repair Fenix Proton (unreleased)

In new source builds, close MSFS and Fenix for every simulator sharing the tool,
then choose **Repair Fenix Proton** at the bottom of the setup window. Terminal
setup offers **[p] Repair Fenix Proton**. The equivalent command is:

```sh
./install.sh repair --steam msfs2024
```

Use `msfs2020` for that simulator. Repair replaces only the manifest-pinned
overlay files; the untouched Wine loader and ABI partners must match the
supported build. It verifies a complete replacement before atomically switching
tools and retains the previous tool under `compatibilitytools.d/.fenix-repair-*`.
The existing aircraft, sign-in, profile and original restore point are retained.
For a known older patch, repair also runs the normal patch update. If that
update stops, retry **Update patch**; the verified new tool is already in place.
The previous tool backup is not removed automatically.

An unknown base build or unfinished installation is still rejected. Do not
override checksums or substitute individual DLLs. A successful repair establishes
runner integrity; it does not establish that a simulator startup failure with
another cause is fixed. The exact causes of the reports in #21 remain unverified.

```sh
./install.sh targets
./install.sh status    --steam msfs2024
./install.sh install   --steam msfs2024
./install.sh select    --steam msfs2024
./install.sh installer --steam msfs2024 --exe "$HOME/Downloads/FenixInstaller.exe"
./install.sh open      --steam msfs2024
./install.sh configure --steam msfs2024
./install.sh configure --steam msfs2024 --renderer cpu
./install.sh configure --steam msfs2024 --renderer gpu
./install.sh restore   --steam msfs2024
```

Steam is found in `~/.local/share/Steam`, `~/.steam`, the Flatpak and the Snap
locations, including additional libraries; `--steam-root` names another one.
Flatpak and Snap Steam are detected but untested.

`--renderer cpu|gpu` is a persistent preference. The GPU option requires a
complete GPU-capable overlay for that exact Proton build; it cannot enable GPU
on older or CPU-only overlays. See [GPU displays](gpu-displays.md) for the
compatibility fixes and the remaining validation limits.

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
  Flightdeck, it runs the simulator without esync/fsync. The 0.1.0 source
  candidate also explicitly disables ntsync using each pinned Wine
  generation's switch; existing tools receive it during an update. Published
  preview.10 needs the manual comparison in [v3 startup diagnostics](display-startup.md).
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
* The overlay's checks ran with server synchronization. The 0.1.0 source
  candidate explicitly selects it even when `/dev/ntsync` exists. Behavior
  with an active ntsync backend has not been validated here.

* The automatic MCDU refresh after a display restart is started by Flightdeck's
  launcher and is not part of the Steam path. The fallback window guard for the
  native Wayland driver is not started either; X11/Xwayland uses the patched driver.
* Verifying the simulator's files in Steam does not affect the profile. Deleting
  the simulator's compatibility data in Steam removes the patched profile.
* preview.5 linked a library that Steam's runtime container does not have, so
  the simulator exited right after starting. Update to preview.6 or later.
