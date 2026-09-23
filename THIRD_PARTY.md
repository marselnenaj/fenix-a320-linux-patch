# Components and source

* Wine: https://github.com/xodus-gaming/wine at
  `b1dd32734a34472a28eb5be9922df06e07ac0834`; LGPL-2.1-or-later and upstream
  per-file notices. The unchanged archive is included as `sources/wine-source.tar.gz`.
* Wine's xgameruntime submodule: https://github.com/xodus-gaming/xgameruntime at
  `64aebcabb8c66121eae25d3bf0ace4b582ebb0da`; included as
  `sources/xgameruntime-source.tar.gz`, with original notices.
* All modifications to these sources are in `patches/`, in manifest order.
  The patches are LGPL-2.1-or-later. See `licenses/LGPL-2.1.txt`.
* The installer, integration wrapper and window guard are MIT. The integration
  scripts originate from the MIT-licensed Flightdeck launcher, with its notices retained.

The complete sources are in the same binary ZIP and in a separate corresponding
source archive in each release. Build and relinking instructions are in BUILDING.md.
The runner itself, its fonts, DXVK and vkd3d binaries are supplied by the user's
Flightdeck installation and are not redistributed by this project.

The optional native Direct2D geometry-provider patch is retained to reproduce the
tested Wine binary exactly. Its environment flag is not enabled by this installer;
no native Windows geometry DLL is supplied or required for the CPU display path.

Fenix and Microsoft software is installed separately through the respective
official installers. Their names are used to identify compatibility. This project
does not grant licenses for them or modify their licensing/activation checks.
