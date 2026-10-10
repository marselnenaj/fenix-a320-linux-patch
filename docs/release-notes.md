# Unreleased

* Standalone installation for the Steam editions of MSFS 2020 and 2024
  (`./install.sh install --steam msfs2024`). The installer creates a separate
  compatibility tool, *Proton Fenix A320*, from the pinned CachyOS Proton and
  downloads that build when it is not installed. Proton Experimental and other
  tools are left unchanged. See [steam.md](steam.md).
* The Windows profile is exchanged transactionally; the simulator's `Packages`
  folder is moved instead of copied. Restore returns the earlier profile.
* Proton's shared Wine Mono registration and linked framework placeholders are
  removed before Microsoft .NET setup, which otherwise installs nothing.
* New guided setup in the web browser, served only to the local computer, in
  place of the Tk window: one step at a time, finished steps ticked, resumable.
  No additional packages are needed; `--text` offers the same in a terminal.
* With Steam closed, the installer enters the Fenix Proton for the simulator
  in Steam's configuration and restore removes it again.
* Flightdeck runtimes keep working with the same commands.

Verified in a reproduced Steam library whose profile was created by Proton
Experimental: pinned Proton download, .NET Framework 4.8 (32- and 64-bit CLR
through the tool's launcher), geometry dependency, overlay, Proton's own
profile refresh, restore and repeat installation. **Not yet run with a real
Steam simulator or Fenix on Steam**; MSFS 2020 with Fenix is untested.

# 0.1.0-preview.4 — 3 October 2026

* Add separate, source-matched Fenix overlays for Proton Experimental
  `experimental-11.0-20260924-x86_64` and CachyOS `cachyos-10.0-sunset-slr`.
  Preserve each runner's graphics stack and verify its exact Wine ABI partners.
* Support the classic Wine64 entry point in setup, GSX/.NET helpers and MCDU
  refresh. Keep 32-bit clients compatible with the rebuilt Wine server.
* Retain Proton selection when installing/updating Fenix and restore its original
  selection when explicitly restoring the pre-patch profile.
* Provide unified launch scripts with both the portable Store loader and Fenix
  geometry, helper-window and MCDU refresh support.

Fresh-source builds and native regression probes pass for both Proton overlays,
including 3,564 geometry reference cases, 800 concurrent metric checks and 768
stroke comparisons. Fresh .NET/Fenix dependency installation, 32-/64-bit CLR
execution, official FSDT preparation and Flightdeck profile round trips were
checked in disposable environments. Simulator/Fenix flight behavior and NVIDIA black-view reports
still require hardware/in-game validation. No Fenix, FSDT or Microsoft installer
or proprietary dependency is redistributed.

# 0.1.0-preview.3 — 24 September 2026

* Restore route path metrics instead of returning `E_NOTIMPL`.
* Respect stroke joins, caps, dashes and miter limits, removing long lines at
  acute route joins. Cache widened contours in geometry realizations.
* Download and verify the required geometry dependency from Microsoft during
  both fresh setup and updates; scope it to FenixDisplay.exe. No Microsoft DLL
  is bundled in this release.
* Keep matching X11/Xwayland helper windows off the desktop while preserving
  their internal visibility and startup events. Keep sign-in and other programs
  interactive; retain the portable guard for other Wine display drivers.
* Automatically refresh stale MCDU startup images after Fenix Display restarts.
  Restore the display preference and brightness without changing MCDU pages.
  The helper uses the simulator’s installed SimConnect library; no additional
  Microsoft binary is distributed.
* Update verified preview.1/preview.2 profiles while retaining aircraft,
  settings and the original restore point.

Built from clean, pinned source archives. Installer transaction checks and the
fresh-prefix loader, cursor, IOCP, audio and window-mapping probes pass. Graphics
checks pass 3,564 reference and 800 concurrent metrics cases, plus 768 stroke
comparisons with zero differing pixels.
Route behavior was also checked in the live cockpit before this clean rebuild.
The automatic MCDU refresh passed the live official display-restart check with
unchanged pages, retained brightness and unchanged simulator/System/CDU process
identities. See [mcdu-restart.md](mcdu-restart.md) for behavior and limits.

## 0.1.0-preview.2

* Fix invisible mouse pointers in the official Fenix Installer and livery
  manager by sharing selected Wine cursors between the WebView processes.
* Repair missing 64-bit UI-font registrations before opening Fenix, preventing
  affected installer startup crashes. Existing fonts come from the user's runner.
* Update verified preview.1 profiles without reinstalling Fenix or .NET, keeping
  aircraft, settings and the original restore point.
* Keep manual Fenix windows accessible and suppress Wine's separate fallback
  notification-area window.

The Wine overlay now contains ten modules. Complete corresponding source and
the upstream cursor-patch attribution are included. The pinned runner and
platform requirements are unchanged. This remains a community preview.

## 0.1.0-preview.1

First packaged version of the locally verified MSFS 2024 / Fenix fixes.

* App-scoped loader names and actual first-write tracking for copy-on-write pages.
* NT image names preserved for Xodus's inherited file descriptors; simulator
  basename/resource aliases preserved without writing its decrypted image to disk.
* RFC 3161 content decoding, in-process audio session notifications and correct
  remote-thread activation-context handling.
* Direct2D display effects, geometry groups/realizations, masks, layers and arcs.
* App-scoped unhinted DirectWrite outlines for complete FCU/radio digits.
* Wine server completion-wait lifetime fix.
* CPU rendering, Legacy readouts, standard font registration and normal autostart.
* Transactional setup, checksum/runner checks, restore and Flightdeck UI integration.

Known limits: pinned Xodus runner only; glibc 2.38+; MSFS 2024 only; no weather
radar in CPU mode. Ground cockpit verified on Hyprland; full flight, other desktops
and future Fenix/MSFS versions need further testing. Account activation uses the
official Fenix workflow.

Packaging checks: patches reproduce all 24 modified Wine source files. Synthetic
installer transactions cover corruption, wrong runners, custom scripts, locks,
active profiles and interrupted commit/restore. The stripped release binaries
passed loader-name, copy-on-write, 30,000-message IOCP and audio callback probes
in a separate fresh Wine prefix. Native .NET Framework 4.8 installation and font
registration completed in a separate test runtime. The window guard hides a
matching helper and leaves a different executable with the same title visible.
The Flightdeck flow was tested in Chromium with synthetic API jobs on desktop
and mobile; no account login or vendor aircraft was part of that automated test.
