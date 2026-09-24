# Components and source

* Wine: https://github.com/xodus-gaming/wine at
  `b1dd32734a34472a28eb5be9922df06e07ac0834`; LGPL-2.1-or-later and upstream
  per-file notices. The unchanged archive is included as `sources/wine-source.tar.gz`.
* Wine's xgameruntime submodule: https://github.com/xodus-gaming/xgameruntime at
  `64aebcabb8c66121eae25d3bf0ace4b582ebb0da`; included as
  `sources/xgameruntime-source.tar.gz`, with original notices.
* All modifications to these sources are in `patches/`, in manifest order.
  The patches are LGPL-2.1-or-later. See `licenses/LGPL-2.1.txt`.
* The selected-cursor sharing fix is backported from GloriousEggroll's
  [GE-Proton patch](https://github.com/GloriousEggroll/proton-ge-custom/commit/16a62e92).
  Its authorship and Wine's per-file notices are retained.
* The installer, integration wrappers, window guard and MCDU refresh helper are MIT. The integration
  scripts originate from the MIT-licensed Flightdeck launcher, with its notices retained.

The complete sources are in the same binary ZIP and in a separate corresponding
source archive in each release. Build and relinking instructions are in BUILDING.md.
The runner itself, its fonts, DXVK and vkd3d binaries are supplied by the user's
Flightdeck installation and are not redistributed by this project.

The Direct2D geometry provider is downloaded separately from Microsoft's
[Platform Update for Windows 7 (KB2670838)](https://www.microsoft.com/en-us/download/details.aspx?id=36805).
The installer extracts only the x64 geometry library as `d2d1_geometry.dll`,
using a separately downloaded `msdelta.dll` from Microsoft's public symbol
server to decode the update. Neither DLL nor the update is redistributed.
URLs and SHA-256 pins are in `fenix_patch/core.py`; package, delta-basis and
output checksums are checked before committing the staging profile.

`WINE_D2D1_GEOMETRY_PROVIDER=FenixDisplay.exe` limits this dependency to Fenix's
geometry calculations. Wine owns public Direct2D objects and rendering. The
original system `d2d1.dll` is not replaced with Microsoft's implementation.
The extraction helper is original MIT code in `native/geometry-setup.c`;
its binary and complete source are included.

Fenix and Microsoft software is installed separately through the respective
official installers. Their names are used to identify compatibility. This project
does not grant licenses for them or modify their licensing/activation checks.

The MCDU refresh helper calls the user’s existing `SimConnect_internal.dll` from
the installed MSFS 2024 game directory. No SimConnect library or SDK is bundled
or downloaded. `tests/mcdu-simconnect-fixture.c` is an original synthetic endpoint
for boundary checks and contains no Microsoft implementation.
