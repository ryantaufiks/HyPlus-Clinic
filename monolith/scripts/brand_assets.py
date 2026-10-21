"""Turn the uploaded Hy+ artwork into the web assets the app uses.

Usage (from monolith/): python3 scripts/brand_assets.py static/brand static/img static/icons
Needs Pillow. Reads hyplus_mainlogo.png, hyplus_logoicon.png and hyplus_icon.png.
"""
import sys
from PIL import Image, ImageChops

src, img_dir, icon_dir = sys.argv[1:4]

def crop(im, margin=0.0, threshold=8):
    # Trim to the visible artwork; a higher threshold also drops faint anti-aliasing halos.
    box = im.getchannel("A").point(lambda a: 255 if a > threshold else 0).getbbox()
    im = im.crop(box)
    if margin:
        m = round(max(im.size) * margin)
        canvas = Image.new("RGBA", (im.width + 2 * m, im.height + 2 * m), (0, 0, 0, 0))
        canvas.paste(im, (m, m))
        im = canvas
    return im

def fit_height(im, h):
    return im.resize((round(im.width * h / im.height), h), Image.LANCZOS)

# 1. Main logo (Hy+ Hyplus Clinic) for headers; 3x the largest display height.
logo = crop(Image.open(f"{src}/hyplus_mainlogo.png").convert("RGBA"), threshold=40)
fit_height(logo, 180).save(f"{img_dir}/hyplus-logo.png", optimize=True)

# 2. The Hy+ mark alone (transparent) for the kiosk and compact places.
mark = crop(Image.open(f"{src}/hyplus_logoicon.png").convert("RGBA"), threshold=40)
fit_height(mark, 360).save(f"{img_dir}/hyplus-mark.png", optimize=True)

# 3. App icon with its own rounded corners ("any" purpose icons and favicons).
icon = Image.open(f"{src}/hyplus_icon.png").convert("RGBA")
rounded = crop(icon)
side = max(rounded.size)
square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
square.paste(rounded, ((side - rounded.width) // 2, (side - rounded.height) // 2))
for size in (16, 32, 48, 72, 96, 128, 144, 152, 192, 384, 512):
    square.resize((size, size), Image.LANCZOS).save(f"{icon_dir}/icon-{size}x{size}.png", optimize=True)

# 4. Full-bleed icons (Android maskable, iOS home screen): the white Hy+ lifted
#    from the app icon onto the same diagonal gradient, inside the safe zone.
rgb = rounded.convert("RGB")
r, g, b = rgb.split()
lightest = ImageChops.darker(ImageChops.darker(r, g), b)  # min(r, g, b)
glyph_alpha = ImageChops.multiply(lightest.point(lambda v: max(0, min(255, (v - 150) * 255 // 90))), rounded.getchannel("A"))
glyph = Image.new("RGBA", rounded.size, (255, 255, 255, 255))
glyph.putalpha(glyph_alpha)
glyph = glyph.crop(glyph_alpha.getbbox())

BLUE, GREEN = (11, 88, 140), (44, 172, 150)  # bottom-left to top-right, sampled from the icon

def full_bleed(size):
    n = size * 2
    # t = 255 at the bottom-left corner (blue), 0 at the top-right (green).
    down = Image.linear_gradient("L").resize((n, n))           # 0 at the top, 255 at the bottom
    left = Image.linear_gradient("L").rotate(-90).resize((n, n))  # 255 at the left, 0 at the right
    t = ImageChops.add(down, left, scale=2.0)
    bg = Image.composite(Image.new("RGB", (n, n), BLUE), Image.new("RGB", (n, n), GREEN), t).convert("RGBA")
    w = round(n * 0.58)
    mark = glyph.resize((w, round(glyph.height * w / glyph.width)), Image.LANCZOS)
    bg.alpha_composite(mark, ((n - mark.width) // 2, (n - mark.height) // 2))
    return bg.resize((size, size), Image.LANCZOS).convert("RGB")

for size in (192, 512):
    full_bleed(size).save(f"{icon_dir}/maskable-{size}x{size}.png", optimize=True)
full_bleed(180).save(f"{icon_dir}/apple-touch-icon.png", optimize=True)
print("ok", logo.size, mark.size, square.size, glyph.size)
