"""Build the silent Help clip from six real, fictional-account UI captures.

Development-only dependencies: Pillow and imageio-ffmpeg. Pass the capture
directory as the first argument. Captures must never contain real account data.
"""
from pathlib import Path
import sys

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

SOURCE = Path(sys.argv[1])
TARGET = Path(__file__).resolve().parents[1] / 'app/static/videos'
TARGET.mkdir(parents=True, exist_ok=True)
FONT = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 28)
STEPS = [
    ('01-empty.jpg', 'Search for a game', (270, 270)),
    ('02-results.jpg', 'Select the matching result', (300, 350)),
    ('03-selected.jpg', 'Check the selected game', (330, 255)),
    ('04-platform.jpg', 'Choose platform and status · Rating is optional', (300, 490)),
    ('05-save.jpg', 'Choose Add game · Notes are optional', (215, 545)),
    ('06-library.jpg', 'Saved to your library', (200, 520)),
]
writer = imageio_ffmpeg.write_frames(str(TARGET / 'help-add-game.mp4'),
    (1280, 800), fps=24, codec='libx264', pix_fmt_in='rgb24',
    pix_fmt_out='yuv420p', quality=8, macro_block_size=1,
    output_params=['-movflags', '+faststart', '-crf', '24'])
writer.send(None)
previous = (180, 260)
try:
    for index, (filename, label, point) in enumerate(STEPS):
        source = Image.open(SOURCE / filename).convert('RGB')
        scale_x, scale_y = 1280 / source.width, 720 / source.height
        base = Image.new('RGB', (1280, 800), '#101215')
        base.paste(source.resize((1280, 720), Image.Resampling.LANCZOS), (0, 80))
        caption = ImageDraw.Draw(base)
        caption.text((30, 22), f'{index + 1:02d}  {label}', font=FONT, fill='#ffd28d')
        for tick in range(60):
            frame = base.copy()
            draw = ImageDraw.Draw(frame)
            progress = min(1, tick / 20)
            ease = 1 - (1 - progress) ** 3
            x = (previous[0] + (point[0] - previous[0]) * ease) * scale_x
            y = 80 + (previous[1] + (point[1] - previous[1]) * ease) * scale_y
            if 22 <= tick <= 40:
                radius = 12 + (tick - 22) * 1.5
                draw.ellipse((x-radius, y-radius, x+radius, y+radius), outline='#ffbe57', width=3)
            draw.polygon([(x,y),(x+4,y+27),(x+11,y+20),(x+19,y+33),(x+25,y+29),(x+17,y+17),(x+28,y+15)], fill='white', outline='#101215', width=2)
            draw.rectangle((0, 795, int(1280 * (index * 60 + tick + 1) / 360), 799), fill='#ffbe57')
            if index == 0 and tick == 24:
                frame.save(TARGET / 'help-add-game-poster.webp', quality=88)
            writer.send(frame.tobytes())
        previous = point
finally:
    writer.close()
print(f'Created {TARGET / "help-add-game.mp4"}')
