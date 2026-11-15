"""Encode the Help demonstration from Full HD UI captures.

Use a fictional local account. The source viewport is 1935 x 1080, captured at
1920 x 1072. Real consecutive scroll captures preserve the fixed background;
no page stitching or synthetic background translation is permitted.
Development dependencies: Pillow, imageio-ffmpeg, and Windows Segoe UI.
"""
from pathlib import Path
import json
import sys
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

SOURCE = Path(sys.argv[1])
TARGET = Path(__file__).resolve().parents[1] / 'app/static/videos'
CAPTURE_SIZE = (1920, 1072)
VIDEO_SIZE = (1920, 1152)
FPS = 30
FONT = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 32)
MENU_FONT = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 17)


def screenshot(name):
    picture = Image.open(SOURCE/(name+'.jpg')).convert('RGB')
    if name == 'library' and picture.height == CAPTURE_SIZE[1] and picture.width < CAPTURE_SIZE[0]:
        # Preserve native text pixels if the browser resized during navigation.
        canvas = Image.new('RGB', CAPTURE_SIZE, '#101215')
        canvas.paste(picture, ((CAPTURE_SIZE[0]-picture.width)//2, 0))
        picture = canvas
    if picture.size != CAPTURE_SIZE:
        raise ValueError(f'{name}: expected {CAPTURE_SIZE}, found {picture.size}; recapture without resizing.')
    return picture


def menu(base, x, y, labels, selected):
    """Native popup surfaces are omitted by browser captures; match their labels."""
    base = base.copy()
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle((x,y,x+290,y+34*len(labels)+12),radius=8,fill='#101215',outline='#9d7b46',width=1)
    for index,label in enumerate(labels):
        top=y+6+34*index
        if label==selected:
            draw.rounded_rectangle((x+5,top,x+285,top+32),radius=4,fill='#614b2c')
        draw.text((x+14,top+4),label,font=MENU_FONT,fill='#fff0da')
    return base


def pointer():
    # Supersample a compact standard arrow so diagonals stay clean in fullscreen.
    factor=4
    layer=Image.new('RGBA',(24*factor,32*factor))
    points=[(2,2),(2,23),(7,18),(11,28),(15,26),(11,17),(20,17)]
    ImageDraw.Draw(layer).polygon([(x*factor,y*factor) for x,y in points],fill='white',outline='#17191c',width=5)
    return layer.resize((24,32),Image.Resampling.LANCZOS)


scenes=[]
def add(name,seconds,label,point,transition='fade',click=False,image=None):
    scenes.append(dict(image=image or screenshot(name),seconds=seconds,label=label,point=point,transition=transition,click=click))


add('empty',1.6,'Search for a game',(610,275),click=True)
add('focused',.5,'Search for a game',(610,275),'cut')
for letter in range(1,8):
    add(f'type-{letter}',.24,'Type the title',(650,280),'cut')
add('results',2.5,'Choose the matching game',(675,350),click=True)
add('selected',2.2,'Check the selected game',(700,255))
add('selected',2.8,'Choose your platform',(620,645),image=menu(screenshot('selected'),480,520,
    ['Choose a platform','Google Stadia','Linux','Mac','Nintendo Switch','PC (Microsoft Windows)','PlayStation 4','Xbox One'],'Mac'),click=True)
add('platform-picked',1.7,'Platform selected',(625,495))
add('platform-picked',2.4,'Choose your status',(940,575),image=menu(screenshot('platform-picked'),795,520,
    ['Backlog','Playing','Completed','On hold','Dropped'],'Playing'),click=True)
add('status-picked',1.7,'Playing · You can change this later',(940,495))
add('status-picked',1.2,'Your rating is optional',(1250,490),'cut',click=True)
add('rating',2.1,'A half-star rating works too',(1250,490))
for capture in json.loads((SOURCE/'scroll.json').read_text()):
    add(Path(capture['file']).stem,2/FPS,'Notes and extra details are optional',(1520,800),'microfade')
add('save',2.4,'Save your game',(540,910),'cut',click=True)
add('library',5.0,'Saved · Mac · Playing · 4.5/5',(510,885))


total_frames=sum(round(scene['seconds']*FPS) for scene in scenes)
writer=imageio_ffmpeg.write_frames(str(TARGET/'help-add-game.mp4'),VIDEO_SIZE,fps=FPS,
    codec='libx264',pix_fmt_in='rgb24',pix_fmt_out='yuv420p',macro_block_size=1,
    output_params=['-movflags','+faststart','-crf','17','-preset','slow'])
writer.send(None)
cursor=pointer()
previous_image=scenes[0]['image']
cursor_position=(540.0,220.0)
elapsed=0
cues=[]
try:
    for index,scene in enumerate(scenes):
        image=scene['image']
        frames=round(scene['seconds']*FPS)
        transition_frames=2 if scene['transition']=='microfade' else min(frames,round(.28*FPS))
        cues.append((elapsed/FPS,(elapsed+frames)/FPS,scene['label']))
        for tick in range(frames):
            t=min(1,(tick+1)/max(1,transition_frames))
            ease=t*t*(3-2*t)
            current=Image.blend(previous_image,image,ease) if scene['transition']!='cut' and t<1 else image
            frame=Image.new('RGB',VIDEO_SIZE,'#101215')
            frame.paste(current,(0,80))
            draw=ImageDraw.Draw(frame)
            draw.text((36,20),scene['label'],font=FONT,fill='#ffd28d')
            # Keep the pointer continuous across even the shortest scroll frames.
            cursor_position=tuple(current+(target-current)*.2
                for current,target in zip(cursor_position,scene['point']))
            x=round(cursor_position[0])
            y=80+round(cursor_position[1])
            if scene['click'] and .72<tick/FPS<1.08:
                progress=(tick/FPS-.72)/.36
                ring=Image.new('RGBA',VIDEO_SIZE)
                radius=8+10*progress
                ImageDraw.Draw(ring).ellipse((x-radius,y-radius,x+radius,y+radius),outline=(255,190,87,round(160*(1-progress))),width=2)
                frame.paste(ring,(0,0),ring)
            frame.paste(cursor,(x,y),cursor)
            draw.rectangle((0,1149,round(1920*(elapsed+tick+1)/total_frames),1151),fill='#ffbe57')
            if index==0 and tick==25:
                frame.save(TARGET/'help-add-game-poster.webp',quality=94)
            writer.send(frame.tobytes())
        previous_image=image
        elapsed+=frames
finally:
    writer.close()


def timestamp(seconds):
    value=round(seconds*1000)
    return f'00:{value//60000:02d}:{value//1000%60:02d}.{value%1000:03d}'


# Merge identical adjacent captions, including the consecutive scroll frames.
merged=[]
for start,end,label in cues:
    if merged and merged[-1][2]==label:
        merged[-1]=(merged[-1][0],end,label)
    else:
        merged.append((start,end,label))
blocks=[f'{timestamp(start)} --> {timestamp(end)}\n{label}' for start,end,label in merged]
(TARGET/'help-add-game.vtt').write_text('WEBVTT\n\n'+'\n\n'.join(blocks)+'\n',encoding='utf-8')
print(f'Created {total_frames/FPS:.2f}s tutorial at {VIDEO_SIZE}, CRF 17; scroll uses real captures.')
