"""Generate application icon."""
from PIL import Image, ImageDraw
import os


def generate_icon():
    """Create a modern download icon (arrow pointing down into a tray)."""
    size = 256
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Background circle / rounded rectangle (gradient-like modern blue)
    padding = 10
    draw.rounded_rectangle(
        [padding, padding, size - padding, size - padding],
        radius=48,
        fill='#1a73e8'
    )
    
    # Down arrow
    arrow_color = 'white'
    center_x = size // 2
    
    # Vertical shaft of arrow
    line_width = 28
    draw.rectangle(
        [center_x - line_width // 2, 55, center_x + line_width // 2, 155],
        fill=arrow_color
    )
    
    # Arrow head (triangle)
    draw.polygon(
        [(center_x - 55, 145), (center_x + 55, 145), (center_x, 205)],
        fill=arrow_color
    )
    
    # Tray line (rounded bar at bottom)
    draw.rounded_rectangle(
        [50, 215, size - 50, 232],
        radius=6,
        fill=arrow_color
    )
    
    # Save as .ico
    assets_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(assets_dir, exist_ok=True)
    icon_path = os.path.join(assets_dir, 'icon.ico')
    img.save(
        icon_path,
        format='ICO',
        sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    )
    print(f"Icon saved to {icon_path}")
    return icon_path


if __name__ == '__main__':
    generate_icon()
