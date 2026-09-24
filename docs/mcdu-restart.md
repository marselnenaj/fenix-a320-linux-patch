# Automatic MCDU refresh after a display restart

Preview.3 includes a bounded compatibility workaround for a cached dark MCDU
startup image. The live official **RESTART DISPLAY** check passed with unchanged
MCDU pages, original brightness and unchanged simulator, System and CDU process
identities. This is an external display refresh, not a proprietary binary patch.

## Behavior

Flightdeck starts a small supervisor with the simulator and stops it when the
simulator exits. It waits for the matching Fenix services and display data,
then refreshes once after each new Fenix Display process has settled.

The helper briefly switches Fenix's **Home Cockpit Mode** display preference and
restores the original value. This makes Fenix redraw its cached MCDU image.
Near maximum MCDU brightness, where switching the preference alone can leave
the same brightness value, a normal DIM/BRT pair forces the redraw and verifies
that brightness returns to its original value. Already held brightness buttons
are left alone. No MCDU page keys, flight-plan entries, power or flight controls
are sent. Pop-out brightness can briefly change during recovery.

The local API listener must belong to the Fenix gateway in the same Wine profile.
Redirects and proxies are disabled. A per-runtime lock prevents duplicate
supervisors. A durable journal retains the original display preference until
readback confirms restoration, including recovery after an interrupted request.
The native helper uses only the user's installed MSFS 2024 SimConnect library.

If the local Fenix API or simulator interface is unavailable, the helper defers
rather than changing unrelated aircraft state. The tested scope is Fenix
2.4.0.4720, MSFS 2024 1.8.16.0, CPU rendering and the pinned Wine runner.

## Evidence

Before this workaround, an unchanged IDENT page peaked at RGB 205 before an
official Display restart and stayed at 24 after 5, 15 and 60 seconds. Normal
page changes restored the original image, consistent with a stale startup cache.
Window visibility, the portable guard, GPU safe mode and single-thread rendering
did not independently correct that behavior.

With the automatic helper, both MCDUs retained their original MENU/IDENT pages
and bright images at the recorded 5, 15 and 60 second observations. Only Display
restarted. The earlier cold start and native helper-window suppression also
passed. Fenix vendor binaries were unchanged.

The supervisor and installer have 31 passing Python checks, including interrupted
preference restoration, wrong service ownership and cancellation. Six synthetic
native endpoint scenarios cover maximum, near-maximum, mixed and low brightness,
a held pilot button and refused input. Brightness and button-release state were
preserved in every scenario. These boundary checks are synthetic, not a claim of
six additional live cockpit sessions.

Route geometry was checked earlier in the live cockpit and with 3,564 reference
plus 800 concurrent metrics cases and 768 stroke comparisons. The final fresh
cockpit session had no programmed route; a full flight remains unverified.
Raw screenshots, account-bearing metadata, vendor code and profile data are
excluded from the release.
