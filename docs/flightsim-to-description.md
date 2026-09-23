# Fenix A320 Linux Patch — Flightdeck / MSFS 2024

A community compatibility installer for using your purchased Fenix A320 with
Microsoft Flight Simulator 2024 through Flightdeck on Linux.

Includes Wine fixes for black/white cockpit displays, MCDU output, FCU/radio
font outlines, display geometry, startup issues and helper windows appearing
over the simulator. The installer configures the tested CPU rendering path and
Legacy FCU readouts, retains a profile backup and provides restore support.

**Installation:** extract the ZIP, run `./install.sh`, and follow steps 1–4.
You can also use Flightdeck's Add-ons → Fenix A320 panel. Close the simulator
and Fenix before installation. Download the official Fenix Installer from your
own account when prompted, then sign in and activate normally.

**Requirements:** MSFS 2024 already working in Flightdeck, a purchased Fenix
A320, the pinned Xodus Wine 11 runner, x86_64 Linux, glibc 2.38+, Python 3.10+
and GNU cp. Python Tk is needed for the standalone graphical installer.

**Tested versions:** Fenix 2.4.0.4720 / MSFS 2024 1.8.16.0 / Hyprland.
Community preview: full-flight testing and other desktops remain to be validated.
CPU rendering does not provide weather radar. Other Wine/Proton builds and
MSFS 2020 are not supported by this first release.

No aircraft, Fenix/Microsoft executable, fonts, license, account or saved profile
is included. The package includes our installer and Wine components, patches,
complete corresponding sources and licenses. Independent of Fenix Simulations,
Microsoft and Asobo.

Source, instructions and issues:
https://github.com/marselnenaj/fenix-a320-linux-patch
