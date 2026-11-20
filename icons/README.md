# LabRef App Icon

Original artwork (not a reproduction of any stock/licensed icon pack) — a
test-tube rack with coloured liquids beside a microscope silhouette, on a
teal gradient background matching the app's brand accent colour
(`#0f766e`-family, the same teal used throughout the Light theme).

## Source files

- `icon_master.svg` — the flattened icon: gradient background baked in +
  glyph. Use this for anything that doesn't need separate adaptive layers:
  the Play Store listing icon, PWA "any purpose" icons, the Apple touch
  icon, the favicon.
- `icon_adaptive_background.svg` — gradient only, full-bleed, no corner
  rounding (the OS applies its own mask shape — circle, squircle, rounded
  square, teardrop — depending on device/launcher).
- `icon_adaptive_foreground.svg` — glyph only, transparent background,
  pre-scaled and centered so it sits safely inside Android's ~61%
  adaptive-icon safe zone regardless of which mask shape the OS applies.
  Verified against a circular mask with no clipping (see
  `render_icons.py`'s approach if you want to re-check after any edit).

## Rendered assets (already generated — re-run `render_icons.py` only if
## the source SVGs change)

```
play_store/ic_launcher-web-512.png     Google Play Store listing icon
android/mipmap-{mdpi,hdpi,xhdpi,xxhdpi,xxxhdpi}/
    ic_launcher.png                    legacy flattened launcher icon
    ic_launcher_background.png         adaptive icon background layer
    ic_launcher_foreground.png         adaptive icon foreground layer
android/mipmap-anydpi-v26/
    ic_launcher_background.png         full-resolution adaptive source
    ic_launcher_foreground.png         (432px, for Android Studio's Image
                                        Asset tool / manual XML setup)
pwa/icon-{192,256,384,512}.png         general-purpose PWA manifest icons
pwa/maskable-icon-512.png              PWA "maskable" icon (same safe-zone
                                        logic as the Android adaptive layers)
pwa/apple-touch-icon.png               180px, opaque (iOS ignores alpha)
pwa/favicon.ico                        multi-res (16/32/48) browser favicon
```

## Using these in the native Android build (Capacitor or plain Gradle)

Copy the `android/mipmap-*/` folders directly into the generated project's
`android/app/src/main/res/` — the folder names already match Android's
density-bucket convention. For the adaptive icon XML
(`res/mipmap-anydpi-v26/ic_launcher.xml`), point `<background>` and
`<foreground>` at the `ic_launcher_background`/`ic_launcher_foreground`
drawables generated here. See ANDROID_PACKAGING.md for the full packaging
plan.

## If the icon needs revisions

Edit the SVG source files directly (they're hand-authored, not exported
from a design tool, so hex colours and shape coordinates are legible in
the file) and re-run:

```bash
cd icons
python3 -I render_icons.py
```

This regenerates every PNG asset listed above from the three source SVGs
in one pass. Requires `rsvg-convert` on `PATH` and Pillow (`pip install
Pillow`) for the favicon/compositing steps.
