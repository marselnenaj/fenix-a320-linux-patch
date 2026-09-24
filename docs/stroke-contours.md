# Long navigation-display line: stroke contour correction

On 2026-09-24, the captain navigation display in PLAN mode showed a thin green
line extending through and beyond the map circle, while the route itself was
present. This is distinct from the earlier `ComputePointAtLength` failure.

Read-only inspection of the real cached route geometry found a join with
directions `(-0.929665, 0.368406)` and `(0.934250, -0.356619)`, at
`(14.5995, -2.99297)`, with stroke width `0.4`. Wine's unrestricted shader
produced a miter ratio of `158.144`. Its direction agreed with the extra line
in the captured map. Fenix's stroke styles use a zero miter-limit value, which
the original Wine draw path ignored along with the other style properties.

`wine-d2d1-stroke-contours.patch` reuses the existing opt-in native geometry
provider to compute a widened contour with the actual join, cap, dash and
miter properties. Public graphics objects and rendering remain in Wine.
Normal stroked geometry realizations retain that contour so it is computed
when the route geometry changes, not on every rendered frame. Direct styled
draws with normal stroke transforms use the same contour path. Fixed and
hairline transforms retain their previous rendering path. Unmatched or disabled provider scopes retain
the previous implementation. No native Microsoft DLL is distributed.

Verification:

- `tests/stroke-joins-probe.cpp` compares direct drawing and cached realizations
  with independently constructed native Widen reference contours. It includes
  near-reversals, an exact reversal, right angles, all four join types, miter
  limits 0/1/4, rotation and nonuniform scaling. Before: 144 of 192 cases failed
  with 35,558 differing pixels. After: all 192 passed with zero differing pixels.
  Release validation adds non-default caps, built-in dash patterns and custom
  dash arrays: all 768 comparisons pass with zero differing pixels.
- An unmatched-provider control reproduces the original 144 failures.
- Existing path metrics (3,564 reference plus 800 concurrent cases), geometry
  realizations, groups/layers and elliptical-arc regressions all pass.
- Exact patch replay against the saved preceding source matches the built
  source without fuzz.
- The official Fenix **RESTART DISPLAY** button loaded the new DLL. Simulator,
  Fenix main, System and CDU process identities remained unchanged. Both the
  Wine DLL and native geometry provider were confirmed mapped.
- The actual before/after cockpit captures retain the same route, location,
  range and PLAN mode. The extraneous line disappears while the route remains.
  Green pixels outside the route and its labels decrease from 147 to zero.
  Intended dash patterns now render as requested as well.

The fix is retained as source patches and release payload. Full-flight coverage
is broader than this targeted verification.

The subsequent MCDU report exposed a gap in the live verification: both MCDU
images were dim immediately after the display restart. Their contents later
became bright again without changing this DLL. See `mcdu-restart.md`; the MCDU
startup/update issue remains open and must be checked before a release.
