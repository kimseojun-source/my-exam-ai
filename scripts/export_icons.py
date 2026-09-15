"""Export the user's approved artwork; no redrawing or generated substitute."""
from pathlib import Path
from PIL import Image
import json, shutil, sys
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'assets'/'forest-original.png'
if len(sys.argv)>1:
 source.parent.mkdir(exist_ok=True);shutil.copyfile(sys.argv[1],source)
original=Image.open(source).convert('RGBA')
# Flatten transparency for iOS and the background of legacy launcher icons.
def scaled(size):
 image=Image.new('RGBA',(size,size),'#d6ff00');image.alpha_composite(original.resize((size,size),Image.Resampling.LANCZOS));return image.convert('RGB')
icons=ROOT/'static'/'icons';icons.mkdir(parents=True,exist_ok=True)
for size in (192,512):scaled(size).save(icons/f'icon-{size}.png')
scaled(180).save(icons/'apple-touch-icon.png')
# Separate maskable asset leaves the artwork within the central safe circle.
mask=Image.new('RGB',(512,512),'#d6ff00');small=scaled(420);mask.paste(small,(46,46));mask.save(icons/'maskable-512.png')
res=ROOT/'android'/'res'
for density,size in [('mdpi',48),('hdpi',72),('xhdpi',96),('xxhdpi',144),('xxxhdpi',192)]:
 dest=res/f'mipmap-{density}';dest.mkdir(parents=True,exist_ok=True)
 for name in ['ic_launcher','ic_launcher_round']:scaled(size).save(dest/(name+'.png'))
dest=res/'drawable-nodpi';dest.mkdir(parents=True,exist_ok=True)
foreground=Image.new('RGBA',(432,432),(0,0,0,0));size=336
foreground.alpha_composite(original.resize((size,size),Image.Resampling.LANCZOS),((432-size)//2,(432-size)//2));foreground.save(dest/'ic_launcher_foreground.png')
(res/'values').mkdir(exist_ok=True)
(res/'values'/'colors.xml').write_text('<resources><color name="icon_background">#d6ff00</color></resources>')
(res/'mipmap-anydpi-v26').mkdir(exist_ok=True)
for name in ['ic_launcher','ic_launcher_round']:
 (res/'mipmap-anydpi-v26'/f'{name}.xml').write_text('<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android"><background android:drawable="@color/icon_background"/><foreground android:drawable="@drawable/ic_launcher_foreground"/></adaptive-icon>')
ios=ROOT/'ios'/'Assets.xcassets'/'AppIcon.appiconset';ios.mkdir(parents=True,exist_ok=True)
scaled(1024).save(ios/'AppIcon.png');(ios/'Contents.json').write_text(json.dumps({'images':[{'filename':'AppIcon.png','idiom':'universal','platform':'ios','size':'1024x1024'}],'info':{'author':'xcode','version':1}},indent=2))
manifest={'id':'/','name':"FOR'EST",'short_name':"FOR'EST",'description':'과목별 자료로 함께 공부하는 나만의 1:1 학습 공간','start_url':'/','scope':'/','display':'standalone','orientation':'any','background_color':'#f5f7f1','theme_color':'#d6ff00','lang':'ko','icons':[{'src':f'/icons/icon-{n}.png','sizes':f'{n}x{n}','type':'image/png','purpose':'any'} for n in (192,512)]+[{'src':'/icons/maskable-512.png','sizes':'512x512','type':'image/png','purpose':'maskable'}]}
(ROOT/'static'/'manifest.webmanifest').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
