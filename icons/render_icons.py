#!/usr/bin/env python3
"""
Renders the full MedRef icon set from the three source SVGs:
  icon_master.svg              -- flattened icon (gradient bg baked in + glyph)
  icon_adaptive_background.svg -- gradient only, full bleed, no corner rounding
  icon_adaptive_foreground.svg -- glyph only, transparent bg, scaled into the
                                   ~61% Android adaptive-icon safe zone

Produces:
  play_store/ic_launcher-web-512.png          (Google Play listing icon)
  android/mipmap-<density>/ic_launcher.png     (legacy flattened launcher icon)
  android/mipmap-<density>/ic_launcher_foreground.png / _background.png
                                                (adaptive icon layers)
  pwa/icon-<size>.png                          (any-purpose PWA icons)
  pwa/maskable-icon-512.png                    (maskable PWA icon)
  pwa/apple-touch-icon.png                     (180x180, flattened, opaque)
  pwa/favicon.ico                              (16/32/48 multi-res)

Run with: python3 -I render_icons.py   (requires rsvg-convert on PATH, Pillow)
"""
import subprocess, os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))

def svg_to_png(svg_path, size, out_path):
    subprocess.run(["rsvg-convert","-w",str(size),"-h",str(size),svg_path,"-o",out_path], check=True)

def composite(bg_path, fg_path, out_path):
    bg = Image.open(bg_path).convert("RGBA")
    fg = Image.open(fg_path).convert("RGBA")
    bg.paste(fg,(0,0),fg)
    bg.save(out_path)

MASTER = os.path.join(HERE,"icon_master.svg")
ADAPT_BG = os.path.join(HERE,"icon_adaptive_background.svg")
ADAPT_FG = os.path.join(HERE,"icon_adaptive_foreground.svg")

# ---- Play Store listing icon ----
out = os.path.join(HERE,"play_store"); os.makedirs(out, exist_ok=True)
svg_to_png(MASTER, 512, os.path.join(out,"ic_launcher-web-512.png"))

# ---- Legacy + adaptive Android launcher mipmaps ----
densities = {"mdpi":48, "hdpi":72, "xhdpi":96, "xxhdpi":144, "xxxhdpi":192}
adaptive_asset_size = 432  # standard adaptive-icon layer export size (108dp @ xxxhdpi)
out = os.path.join(HERE,"android");
for d, px in densities.items():
    dd = os.path.join(out, f"mipmap-{d}"); os.makedirs(dd, exist_ok=True)
    svg_to_png(MASTER, px, os.path.join(dd,"ic_launcher.png"))          # legacy flattened
    svg_to_png(ADAPT_BG, px, os.path.join(dd,"ic_launcher_background.png"))
    svg_to_png(ADAPT_FG, px, os.path.join(dd,"ic_launcher_foreground.png"))
# anydpi adaptive source layers at full resolution, for Android Studio's Image Asset tool
dd = os.path.join(out,"mipmap-anydpi-v26"); os.makedirs(dd, exist_ok=True)
svg_to_png(ADAPT_BG, adaptive_asset_size, os.path.join(dd,"ic_launcher_background.png"))
svg_to_png(ADAPT_FG, adaptive_asset_size, os.path.join(dd,"ic_launcher_foreground.png"))

# ---- PWA icons (for the HTML prototype's manifest + home-screen install) ----
out = os.path.join(HERE,"pwa"); os.makedirs(out, exist_ok=True)
for size in (192,256,384,512):
    svg_to_png(MASTER, size, os.path.join(out,f"icon-{size}.png"))

# maskable: composite the safe-zone foreground over the full-bleed background
tmp_bg = os.path.join(out,"_tmp_bg_512.png"); tmp_fg = os.path.join(out,"_tmp_fg_512.png")
svg_to_png(ADAPT_BG, 512, tmp_bg)
svg_to_png(ADAPT_FG, 512, tmp_fg)
composite(tmp_bg, tmp_fg, os.path.join(out,"maskable-icon-512.png"))
os.remove(tmp_bg); os.remove(tmp_fg)

# apple touch icon -- opaque, flattened, no transparency (iOS ignores alpha and
# shows it as solid black, so bake the master icon onto itself with no alpha)
svg_to_png(MASTER, 180, os.path.join(out,"apple-touch-icon.png"))
im = Image.open(os.path.join(out,"apple-touch-icon.png")).convert("RGB")
im.save(os.path.join(out,"apple-touch-icon.png"))

# favicon.ico -- multi-resolution
sizes = [16,32,48]
imgs = []
for s in sizes:
    p = os.path.join(out, f"_fav_{s}.png")
    svg_to_png(MASTER, s, p)
    imgs.append(Image.open(p))
imgs[0].save(os.path.join(out,"favicon.ico"), sizes=[(s,s) for s in sizes],
             append_images=imgs[1:])
for s in sizes:
    os.remove(os.path.join(out, f"_fav_{s}.png"))

print("Icon set rendered under:", HERE)
