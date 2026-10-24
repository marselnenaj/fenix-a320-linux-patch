# 0.1.0 release scope

This is the first regular community patch release. The installer, Linux launch
and display helpers, memory sampler and maintainer tooling are Rust. Wine/DXVK
patches and Windows ABI helpers keep their existing native implementation.

The native overlay and Windows helper hashes match preview.11. This release
changes Linux helper implementation and packaging; it makes no new simulator
or full-flight compatibility claim.

| Area | Evidence and limits |
| --- | --- |
| Installer, upgrade and restore | Rust workspace checks cover isolated installation, preserved aircraft/settings, interrupted updates and restore. |
| Linux image loader | Synthetic real-child checks exercise inherited licensed descriptors, native and portable views, unchanged encrypted originals and temporary-view cleanup. |
| Display recovery | Rust checks cover both preference modes, failed probes/refresh, cancellation, journal retention, profile/PID and listener ownership. Live observations from earlier releases remain the available cockpit evidence. |
| Corresponding sources | Release ZIP and source archive retain exact upstream sources, patches, notices and all current Rust sources. |
| Flightdeck | Contract 2 requires 0.2.22. Earlier launchers retain their installed patch and require a launcher update. Exact prior manifests are retained for all four runners. |
| Gateway/EFB | Preview.11's loader correction and the issue #7 reporter's GPU/display-safe-mode evidence are retained. [Scope](display-startup.md). |
| FenixSystem memory | [Issue #12](system-memory.md) remains open for the signature-query ownership lead and Fenix support response. No memory fix is claimed. |
| Fenix v3 stability | Bounded starts and cockpit displays were tested previously; full flights and the earlier Wine assertion remain unqualified. |

All release assets must be rebuilt from the final main commit and verified
before publication. Old preview releases and the superseded draft archives
must not be relabelled as this release.
