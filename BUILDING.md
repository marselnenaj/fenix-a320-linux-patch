# Rebuild and publish

The binary ZIP includes complete, unchanged upstream source archives in
`sources/`, their pinned checksums in `bundle.json`, and all modifications in
`patches/`. Patches apply in manifest order. Retain upstream per-file notices.

The initial build used x86_64 Arch Linux, GCC/MinGW-w64, autoconf, GNU make,
Python 3 and Perl. Install Wine's normal development dependencies, including
FreeType, fontconfig, X11, ALSA/PulseAudio, Vulkan headers and MinGW-w64.
The shipped ELF modules require glibc 2.38 or newer. An older-distribution build
must be tested and published as a separately pinned artifact.

```sh
python3 scripts/build.py --record-build
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/release.py
```

Start with no `build/` directory. `--prepare-only` verifies and applies all patches
without compiling. The build verifies both source archives, populates the
xgameruntime submodule, generates spec/Vulkan headers from the included XML,
and configures Wine with `--enable-win64 --disable-tests --enable-silent-rules
--without-ffmpeg`. It builds the nine targets listed in `scripts/build.py` and
the independent MIT window guard. Debug sections are stripped from release files.

The mapped-image patch includes generated protocol 931 headers/trace; do not
regenerate them with a bumped protocol. Existing 32-bit runner clients must
remain compatible. Rebuild hashes can differ with compiler/platform/timestamps;
`--record-build` explicitly records a new binary set for review. Rebuild and
repin the Flightdeck manifest/release together after validating a changed build.

For local modifications, change the corresponding source patch and its hash,
then rebuild. The installer validates its own manifest, so modified binaries
can be installed by updating that manifest and building your own release.
Do not overwrite binaries in an active Wine session.

## Release files

`scripts/release.py` exports only allowlisted project files. It requires all
source archives and validates binary hashes. It creates:

* `*-linux-x86_64.zip`: standalone installer, Wine overlay, complete sources.
* `*-source.tar.gz`: complete corresponding source, including upstream archives.
* `SHA256SUMS`: checksums for both downloads.
* `flightdeck-release.json`: the pinned URL/hash used by Flightdeck.

Create a GitHub **prerelease** tagged `v0.1.0-preview.1` and attach the two
archives plus SHA256SUMS. The tag must contain this project source and
`bundle.json`; do not commit payload binaries or private prefixes. Use
`docs/release-notes.md` as the release body. The same Linux ZIP can be uploaded
to flightsim.to with `docs/flightsim-to-description.md`.

In Flightdeck, run `python3 scripts/sync-fenix.py /path/to/this/repository`
after building the release. This copies the reviewed MIT installer engine and
the two checksum manifests. Flightdeck executes its vendored engine and only
extracts the fixed payload files from the verified ZIP.

The ZIP is suitable for distribution only with its source archives and notices
intact. Microsoft redistributables and Fenix software are separate downloads;
never add them, fonts, logs, settings, account data or a Wine prefix to a release.
