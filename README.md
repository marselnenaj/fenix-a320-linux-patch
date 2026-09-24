# Fenix A320 Linux Patch

Compatibility fixes and an installer for **Fenix A320 with MSFS 2024 in
[Flightdeck](https://github.com/marselnenaj/flightdeck-msfs-2024-linux-xbox)**.
Community preview; independent of Fenix Simulations, Microsoft and Asobo.

This packages the Wine fixes tested with Fenix **2.4.0.4720**, MSFS 2024
**1.8.16.0** and Xodus Wine **11.0 / 7c0b4354**. PFD, ND, ECAM, MCDU, clock,
FCU and radio display rendering were checked in a running cockpit. A complete
flight and other Fenix versions have not been independently validated.

## Install

1. Install and run MSFS 2024 once using Flightdeck. Close the simulator and Fenix.
2. Download and extract the **Linux installer ZIP** from
   [Releases](https://github.com/marselnenaj/fenix-a320-linux-patch/releases).
3. Run `./install.sh` inside the extracted folder. Choose your Flightdeck runtime,
   then **Install patch + Microsoft .NET**. No `sudo` is needed.
4. Download the official Fenix Installer from your
   [Fenix account](https://fenixsim.com/dashboard/). Choose **Run official Fenix
   Installer**, complete its prerequisites and aircraft installation, then close it.
5. Choose **Open Fenix / sign in**. Activate your purchased aircraft normally,
   then close Fenix and its helpers.
6. Choose **Apply CPU displays + Legacy readouts**. Launch MSFS through Flightdeck.

Flightdeck's **Add-ons → Fenix A320** panel provides the same workflow without
opening a terminal. It downloads a pinned, checksummed patch release. Login and
activation remain in the official Fenix software.

Requirements: x86_64 Linux, Python 3.10+, glibc **2.38+**, GNU `cp`, and the
exact Xodus runner pinned in `bundle.json`. The graphical installer also needs
Python Tk (`python-tk` on Arch, `python3-tk` on Ubuntu). The Microsoft Framework
downloads need internet access. The official Fenix Installer handles its
WebView2, .NET Desktop Runtime and Visual C++ prerequisites.

This preview does **not** accept arbitrary Proton/Wine builds, MSFS 2020,
Steam prefixes or a modified runner. A mismatched runner is rejected before
changes. Existing local development patches are detected by Flightdeck and
left in use; automatic migration is not attempted.

## Command line

```sh
./install.sh status --runtime /path/to/flightdeck/runtime
./install.sh install --runtime /path/to/flightdeck/runtime
./install.sh installer --runtime /path/to/flightdeck/runtime --exe "$HOME/Downloads/FenixInstaller.exe"
./install.sh open --runtime /path/to/flightdeck/runtime
./install.sh configure --runtime /path/to/flightdeck/runtime
./install.sh restore --runtime /path/to/flightdeck/runtime
```

`install` creates an independent runner and Windows profile, installs native
Microsoft .NET Framework 4.8 when needed, copies the existing runner's fonts and
graphics dependencies, and then installs the compatibility overlay after the staging Wine session exits. It retains the
original runner, profile and launch scripts. An interrupted installation has a
recovery journal. Repeating an already completed installation verifies its files.
Running `install` from preview.2 also updates a verified preview.1 installation,
retaining installed aircraft, settings and the original restore point. Flightdeck
performs that update before opening Fenix applications when needed.

`restore` restores the profile from before the patch and retains the newer
profile in a separate local directory. Settings or add-ons installed since the
patch remain in that retained profile; Community content outside the profile is
not removed. Flightdeck's separate Xbox save storage is not part of this restore.

## Displays and windows

The current working configuration uses **CPU** rendering and **Legacy** FCU
readouts. Weather radar is unavailable with this rendering path. Brightness
knobs remain normal aircraft controls; the installer does not force lighting
values or autopilot modes. FMA text depends on the active flight modes.

The bundled window guard hides only the three matching Fenix service/display
windows. Fenix's main application and installer remain accessible for sign-in.
Window hiding can briefly flash on some compositors; see the optional
[Hyprland rules](docs/hyprland.md) for placement before a helper is shown.
The portable guard needs testing on additional desktop environments.

## What is distributed

The release contains our installer/window guard, Wine patches, ten Wine
replacement binaries and their complete source archives/build instructions.
**No Fenix or Microsoft binaries, aircraft, fonts, activation data, saved
profiles or private logs are included.** Microsoft redistributables are fetched
from Microsoft and verified against pinned hashes. Existing fonts are read
from your own compatible runner.

Installer/window guard: MIT. Wine patches and derived Wine binaries:
LGPL-2.1-or-later; upstream notices are retained in the included source archives.
See [BUILDING.md](BUILDING.md) and [THIRD_PARTY.md](THIRD_PARTY.md).

For a bug report, include patch/Fenix/MSFS versions, distribution, desktop and
the failing step. Do not upload your Wine profile, account files, license data
or raw logs without reviewing them first.

[Deutsch](docs/README.de.md) · [Release notes](docs/release-notes.md)
