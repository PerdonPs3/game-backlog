"""Build a smooth Help clip from real fictional-account UI captures.

Pass the capture directory as the first argument. Development dependencies:
Pillow and imageio-ffmpeg. Native popup menus are recreated from actual option
labels because browser screenshots omit operating-system popup surfaces.
"""
from pathlib import Path
import sys
import imageio_ffmpeg
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageStat

SOURCE = Path(sys.argv[1])
TARGET = Path(__file__).resolve().parents[1] / 'app/static/videos'
FONT = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 27)
MENU_FONT = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 17)
FPS = 30


def screenshot(name):
    return Image.open(SOURCE / (name + '.jpg')).convert('RGB')


def menu(base, x, y, labels, selected):
    base = base.copy()
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle((x, y, x+285, min(base.height-5, y+34*len(labels)+12)), radius=8, fill='#101215', outline='#9d7b46', width=2)
    for index, label in enumerate(labels):
        top = y+6+34*index
        if label == selected:
            draw.rounded_rectangle((x+5, top, x+280, top+32), radius=4, fill='#614b2c')
        draw.text((x+14, top+4), label, font=MENU_FONT, fill='#fff0da')
    return base


def scroll_offset(before, after):
    first = before.crop((40, 80, 1200, 690)).resize((116, 610))
    second = after.crop((40, 80, 1200, 690)).resize((116, 610))
    def error(offset):
        diff = ImageChops.difference(first.crop((0, offset, 116, 610)), second.crop((0, 0, 116, 610-offset)))
        return sum(ImageStat.Stat(diff).mean)
    return min(range(520), key=error)


scenes = []


def add(name, seconds, label, point, transition='fade', click=False, image=None):
    scenes.append(dict(image=image or screenshot(name), seconds=seconds,
        label=label, point=point, transition=transition, click=click))


add('empty', 1.6, 'Search for a game', (240, 270), click=True)
add('focused', .5, 'Search for a game', (240, 270), 'cut')
for letter in range(1, 8):
    add(f'type-{letter}', .24, 'Type the title', (310, 290), 'cut')
add('results', 2.5, 'Choose the matching game', (310, 350), click=True)
add('selected', 2.2, 'Check the selected game', (330, 250))
add('platform-open', .8, 'Choose your platform', (280, 415), 'scroll', click=True)
add('platform-open', 2.4, 'Choose your platform', (265, 355), image=menu(screenshot('platform-open'), 146, 270,
    ['Choose a platform', 'Google Stadia', 'Linux', 'Mac', 'Nintendo Switch', 'PC (Microsoft Windows)', 'PlayStation 4', 'Xbox One'], 'Linux'), click=True)
add('platform-picked', 1.7, 'Platform selected', (280, 415))
add('platform-picked', 2.4, 'Choose your status', (560, 490), image=menu(screenshot('platform-picked'), 459, 443,
    ['Backlog', 'Playing', 'Completed', 'On hold', 'Dropped'], 'Playing'), click=True)
add('status-picked', 1.7, 'Playing · You can change this later', (560, 415))
add('status-picked', 1.2, 'Your rating is optional', (920, 415), 'cut', click=True)
add('rating', 2.1, 'A half-star rating works too', (920, 415))
for step in range(1, 7):
    add(f'scroll-{step}', .23, 'Notes and extra details are optional', (1120, 570), 'scroll')
add('save', 2.4, 'Save your game', (210, 552), 'cut', click=True)
add('library', 2.1, 'Back in your library', (190, 510))
add('library-result', 3.3, 'Saved · Linux · Playing · 4.5/5', (200, 430), 'scroll')

total_frames = sum(round(scene['seconds']*FPS) for scene in scenes)
writer = imageio_ffmpeg.write_frames(str(TARGET/'help-add-game.mp4'), (1280, 800),
    fps=FPS, codec='libx264', pix_fmt_in='rgb24', pix_fmt_out='yuv420p',
    quality=8, macro_block_size=1, output_params=['-movflags', '+faststart', '-crf', '23'])
writer.send(None)
previous_image = scenes[0]['image']
previous_point = (170, 220)
elapsed = 0
cues = []
try:
    for index, scene in enumerate(scenes):
        image = scene['image']
        frames = round(scene['seconds']*FPS)
        transition_frames = min(frames, round(.45*FPS))
        offset = scroll_offset(previous_image, image) if scene['transition']=='scroll' else 0
        cues.append((elapsed/FPS, (elapsed+frames)/FPS, scene['label']))
        for tick in range(frames):
            t = min(1, tick/max(1, transition_frames-1))
            ease = t*t*(3-2*t)
            if scene['transition']=='scroll' and offset>0 and t<1:
                # Interpolate actual page scrolling, preserving fixed navigation.
                stitched = Image.new('RGB', (image.width, image.height+offset))
                stitched.paste(previous_image)
                stitched.paste(image.crop((0, image.height-offset, image.width, image.height)), (0, image.height))
                shift = round(offset*ease)
                current = stitched.crop((0, shift, image.width, image.height+shift))
                current.paste(image.crop((0, 0, image.width, 75)), (0, 0))
            elif scene['transition']=='fade' and t<1:
                current = Image.blend(previous_image, image, ease)
            else:
                current = image
            frame = Image.new('RGB', (1280, 800), '#101215')
            frame.paste(current.resize((1280, 720), Image.Resampling.LANCZOS), (0, 80))
            draw = ImageDraw.Draw(frame)
            draw.text((30, 23), scene['label'], font=FONT, fill='#ffd28d')
            move = min(1, tick/max(1, FPS*.65))
            move = move*move*(3-2*move)
            x = (previous_point[0]+(scene['point'][0]-previous_point[0])*move)*1280/image.width
            y = 80+(previous_point[1]+(scene['point'][1]-previous_point[1])*move)*720/image.height
            if scene['click'] and .75<tick/FPS<1.2:
                radius = 12+(tick/FPS-.75)*45
                draw.ellipse((x-radius, y-radius, x+radius, y+radius), outline='#ffbe57', width=3)
            draw.polygon([(x,y),(x+4,y+27),(x+11,y+20),(x+19,y+33),(x+25,y+29),(x+17,y+17),(x+28,y+15)], fill='white', outline='#101215', width=2)
            draw.rectangle((0, 795, round(1280*(elapsed+tick+1)/total_frames), 799), fill='#ffbe57')
            if index==0 and tick==25:
                frame.save(TARGET/'help-add-game-poster.webp', quality=88)
            writer.send(frame.tobytes())
        previous_image, previous_point = image, scene['point']
        elapsed += frames
finally:
    writer.close()


def timestamp(seconds):
    value = round(seconds*1000)
    return f'00:{value//60000:02d}:{value//1000%60:02d}.{value%1000:03d}'


blocks = [f'{timestamp(start)} --> {timestamp(end)}\n{label}' for start, end, label in cues]
(TARGET/'help-add-game.vtt').write_text('WEBVTT\n\n'+'\n\n'.join(blocks)+'\n', encoding='utf-8')
print(f'Created {total_frames/FPS:.2f}-second tutorial ({total_frames} frames).')
