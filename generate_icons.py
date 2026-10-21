#!/usr/bin/env python3
"""
Generate PWA icons for AIVIN
Creates all required icon sizes from a base image or generates simple icons
"""

import os
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Warning: Pillow not installed. Install with: pip install Pillow")


def create_icon_with_text(size, text="AN", bg_color="#00BCD4", text_color="#FFFFFF"):
    """Create a simple icon with text"""
    if not PIL_AVAILABLE:
        print(f"Cannot create {size}x{size} icon - Pillow not installed")
        return None

    # Create image with rounded corners
    img = Image.new("RGB", (size, size), bg_color)
    draw = ImageDraw.Draw(img)

    # Try to load a font, fallback to default
    try:
        # Try different font sizes based on image size
        font_size = int(size * 0.4)
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        try:
            font = ImageFont.load_default()
        except:
            font = None

    # Draw text in center
    if font:
        # Get text bounding box
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Calculate position to center text
        x = (size - text_width) // 2
        y = (size - text_height) // 2 - bbox[1]

        draw.text((x, y), text, fill=text_color, font=font)
    else:
        # Fallback: draw a simple shape
        margin = size // 4
        draw.ellipse([margin, margin, size - margin, size - margin], fill=text_color)

    # Add a border
    border_width = max(1, size // 50)
    draw.rectangle([0, 0, size - 1, size - 1], outline=text_color, width=border_width)

    return img


def create_icon_with_logo(size):
    """Create icon with medical logo"""
    if not PIL_AVAILABLE:
        return None

    img = Image.new("RGB", (size, size), "#00BCD4")
    draw = ImageDraw.Draw(img)

    # Draw a medical cross
    center = size // 2
    cross_width = size // 8
    cross_length = size // 2.5

    # Horizontal bar
    draw.rectangle(
        [
            center - cross_length,
            center - cross_width,
            center + cross_length,
            center + cross_width,
        ],
        fill="#FFFFFF",
    )

    # Vertical bar
    draw.rectangle(
        [
            center - cross_width,
            center - cross_length,
            center + cross_width,
            center + cross_length,
        ],
        fill="#FFFFFF",
    )

    # Draw a heart pulse line at bottom
    pulse_y = int(size * 0.75)
    points = [
        (int(size * 0.2), pulse_y),
        (int(size * 0.3), pulse_y),
        (int(size * 0.35), int(size * 0.65)),
        (int(size * 0.4), int(size * 0.85)),
        (int(size * 0.45), pulse_y),
        (int(size * 0.8), pulse_y),
    ]
    draw.line(points, fill="#FFFFFF", width=max(2, size // 100))

    return img


def generate_all_icons(output_dir, icon_type="logo"):
    """Generate all required PWA icon sizes"""

    if not PIL_AVAILABLE:
        print("ERROR: Pillow is required to generate icons")
        print("Install with: pip install Pillow")
        return False

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Icon sizes required for PWA
    sizes = [72, 96, 128, 144, 152, 192, 384, 512]

    print(f"Generating {len(sizes)} icons...")
    print(f"Output directory: {output_path.absolute()}")
    print("-" * 50)

    for size in sizes:
        try:
            if icon_type == "logo":
                img = create_icon_with_logo(size)
            else:
                img = create_icon_with_text(size)

            if img:
                filename = f"icon-{size}x{size}.png"
                filepath = output_path / filename
                img.save(filepath, "PNG", optimize=True)
                print(f"✓ Created: {filename} ({size}x{size})")
            else:
                print(f"✗ Failed: icon-{size}x{size}.png")

        except Exception as e:
            print(f"✗ Error creating {size}x{size} icon: {e}")

    # Generate shortcut icons
    print("\nGenerating shortcut icons...")
    shortcuts = [
        ("check", "AN", "#00BCD4"),
        ("dashboard", "📊", "#00ACC1"),
        ("qr", "QR", "#0097A7"),
    ]

    for name, text, color in shortcuts:
        try:
            img = create_icon_with_text(96, text, color, "#FFFFFF")
            if img:
                filename = f"shortcut-{name}.png"
                filepath = output_path / filename
                img.save(filepath, "PNG", optimize=True)
                print(f"✓ Created: {filename}")
        except Exception as e:
            print(f"✗ Error creating shortcut-{name}.png: {e}")

    print("-" * 50)
    print(f"✓ Icon generation complete!")
    print(f"✓ Total files created: {len(list(output_path.glob('*.png')))}")

    return True


def create_favicon(output_dir):
    """Create favicon.ico"""
    if not PIL_AVAILABLE:
        return

    try:
        output_path = Path(output_dir)

        # Create 32x32 icon
        img = create_icon_with_logo(32)
        if img:
            favicon_path = output_path / "favicon.ico"
            img.save(favicon_path, "ICO")
            print(f"✓ Created: favicon.ico")
    except Exception as e:
        print(f"✗ Error creating favicon: {e}")


def main():
    """Main function"""
    print("=" * 50)
    print("AIVIN PWA Icon Generator")
    print("=" * 50)
    print()

    # Determine output directory
    script_dir = Path(__file__).parent
    static_dir = script_dir / "monolith" / "static"
    icons_dir = static_dir / "icons"

    if not static_dir.exists():
        print(f"Creating static directory: {static_dir}")
        static_dir.mkdir(parents=True, exist_ok=True)

    # Generate icons
    success = generate_all_icons(icons_dir, icon_type="logo")

    if success:
        # Generate favicon
        create_favicon(static_dir)

        print()
        print("=" * 50)
        print("✓ All done!")
        print("=" * 50)
        print()
        print("Next steps:")
        print("1. Icons are ready in: monolith/static/icons/")
        print("2. Restart Django server")
        print("3. Test PWA on mobile device")
        print("4. Use 'Add to Home Screen' to install")
    else:
        print()
        print("=" * 50)
        print("✗ Icon generation failed")
        print("=" * 50)
        print()
        print("Make sure Pillow is installed:")
        print("  pip install Pillow")


if __name__ == "__main__":
    main()
