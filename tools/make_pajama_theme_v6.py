# -*- coding: utf-8 -*-
"""assets/pajama-girl.png v6: anime-style girl, pink fuzzy hood, holding mini Futa + lemon bun."""
import math, random
from PIL import Image, ImageDraw

S = 4
W, H = 290*S, 436*S
INK = (76, 38, 40, 255)
HOOD = (244, 96, 168, 255)
HOOD_DK = (208, 66, 136, 255)
HOOD_LT = (255, 156, 203, 255)
ROBE = (251, 213, 217, 255)
ROBE_DK = (238, 186, 194, 255)
SLEEVE = (235, 128, 172, 255)
SLEEVE_LT = (248, 168, 200, 255)
PLUSH = (233, 96, 156, 255)
PLUSH_LT = (250, 150, 190, 255)
LINING = (170, 205, 235, 255)
DARK = (90, 48, 64, 255)
SKIN = (250, 214, 198, 255)
HAIR = (54, 38, 44, 255)
HAIR_LT = (96, 74, 82, 255)
LEMON = (251, 243, 155, 255)
LEMON_DK = (214, 186, 96, 255)
WHITE = (252, 238, 240, 255)
SHOE = (58, 38, 44, 255)
BUTTON = (198, 66, 88, 255)
CYAN = (170, 239, 246, 255)
BLUSH = (248, 160, 170, 255)

img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
def sc(v): return int(round(v*S))
def E(cx,cy,rx,ry,fill,outline=INK,width=2.0):
    d.ellipse([sc(cx-rx),sc(cy-ry),sc(cx+rx),sc(cy+ry)], fill=fill, outline=outline, width=max(1,sc(width)))
def blob(cx,cy,rx,ry,fill,outline=INK,width=2.0,wobble=0.012,n=160,seed=1):
    rnd=random.Random(seed); pts=[]
    for i in range(n):
        a=2*math.pi*i/n; r=1.0+rnd.uniform(-wobble,wobble)
        pts.append((sc(cx+rx*r*math.cos(a)), sc(cy+ry*r*math.sin(a))))
    d.polygon(pts, fill=fill, outline=outline, width=max(1,sc(width)))
def P(pts,fill,outline=INK,width=2.0):
    d.polygon([(sc(x),sc(y)) for x,y in pts], fill=fill, outline=outline, width=max(1,sc(width)))
def R(x0,y0,x1,y1,r,fill,outline=INK,width=2.0):
    d.rounded_rectangle([sc(x0),sc(y0),sc(x1),sc(y1)], radius=sc(r), fill=fill, outline=outline, width=max(1,sc(width)))
def L(x0,y0,x1,y1,color,width=1.6):
    d.line([sc(x0),sc(y0),sc(x1),sc(y1)], fill=color, width=max(1,sc(width)))
def fur(cx,cy,rx,ry,color,count=90,seed=5,length=4.0):
    rnd=random.Random(seed)
    for i in range(count):
        a=2*math.pi*rnd.uniform(-1,1)
        x=cx+rx*math.cos(a); y=cy+ry*math.sin(a)
        L(x,y,x+length*math.cos(a),y+length*math.sin(a),color,1.0)
def bar(cx,cy,w,h,angle,fill,outline=INK,width=1.0):
    pts=[]
    for lx,ly in ((-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2)):
        xr=lx*math.cos(angle)-ly*math.sin(angle)
        yr=lx*math.sin(angle)+ly*math.cos(angle)
        pts.append((sc(cx+xr), sc(cy+yr)))
    d.polygon(pts, fill=fill, outline=outline, width=max(1,sc(width)))

# long hair behind body
P([(62,150),(44,250),(38,352),(54,426),(98,430),(110,356),(114,272),(104,182)], HAIR)
P([(228,150),(246,250),(252,352),(236,426),(192,430),(180,356),(176,272),(186,182)], HAIR)
# legs / shoes
R(118,398,142,414,8,WHITE); R(150,398,174,414,8,WHITE)
L(118,406,142,406,INK,1.2); L(150,406,174,406,INK,1.2)
R(106,412,148,430,11,SHOE); R(144,412,186,430,11,SHOE)
# robe
P([(92,252),(198,252),(212,320),(224,398),(180,410),(145,414),(110,410),(66,398),(78,320)], ROBE)
P([(190,254),(212,320),(224,398),(196,406),(204,318),(182,258)], ROBE_DK)
# center fluffy lapels
for x in (124, 156):
    blob(x, 330, 11, 76, SLEEVE, seed=41+x, wobble=0.02)
    fur(x, 330, 11, 76, SLEEVE_LT, 40, 43+x, 2.0)
for by in (286, 322, 358, 390):
    E(145, by, 4.0, 4.0, BUTTON, INK, 1.1)
# pockets with blue patch
for x0 in (72, 176):
    R(x0, 330, x0 + 44, 382, 12, SLEEVE)
    fur(x0 + 22, 356, 20, 24, SLEEVE_LT, 30, 61+x0, 2.0)
    px = x0 + 22
    P([(px-5,344),(px+3,344),(px-2,354),(px+4,354),(px-4,366),(px,356),(px-6,356)], CYAN, INK, 1.0)
fur(145, 404, 78, 8, SLEEVE_LT, 40, 71, 2.4)
# long front hair locks
P([(82,206),(72,276),(64,350),(70,408),(90,408),(96,344),(100,254),(96,212)], HAIR)
P([(208,206),(218,276),(226,350),(220,408),(200,408),(194,344),(190,254),(194,212)], HAIR)
for side in (-1, 1):
    base = 145 + side * 58
    for k in range(3):
        L(base - side*4, 240 + k*40, base + side*3, 300 + k*36, HAIR_LT, 1.2)
# puffy sleeves
P([(92,256),(70,288),(58,326),(70,352),(94,358),(104,332),(106,292)], SLEEVE)
P([(198,256),(220,288),(232,326),(220,352),(196,358),(186,332),(184,292)], SLEEVE)
fur(80, 330, 22, 26, SLEEVE_LT, 26, 81, 2.2)
fur(210, 330, 22, 26, SLEEVE_LT, 26, 82, 2.2)
# hood
blob(145,150,108,112,HOOD,seed=11,wobble=0.015)
fur(145,150,108,112,HOOD_LT,190,15,5.0)
E(145,176,76,78,DARK,INK,2.0)
d.arc([sc(69),sc(94),sc(221),sc(258)],205,335,fill=LINING,width=sc(9))
d.arc([sc(69),sc(94),sc(221),sc(258)],205,335,fill=INK,width=sc(1.0))
P([(92,112),(104,112),(98,128),(108,128),(94,152),(100,134),(90,134)], CYAN, INK, 1.0)
# face
E(145,182,66,68,SKIN,INK,1.8)
P([(78,176),(80,132),(104,108),(145,102),(186,108),(210,132),(212,176),(200,164),(186,152),(170,172),(154,150),(145,176),(132,150),(116,172),(100,152),(88,164)], HAIR)
P([(82,166),(78,206),(92,214),(96,166)], HAIR)
P([(208,166),(212,206),(198,214),(194,166)], HAIR)
for k in range(4):
    L(108 + k*8, 132 + k*4, 104 + k*8, 158 + k*5, HAIR_LT, 1.0)
for cx in (116, 174):
    E(cx,192,15,18,(60,34,44,255),(42,25,31,255),1.4)
    E(cx,194,11,14,(96,58,74,255),(0,0,0,0),0)
    E(cx,196,9,11,(48,26,36,255),(0,0,0,0),0)
    E(cx-4,186,4.5,5.5,(255,255,255,255),(0,0,0,0),0)
    E(cx+5,199,2.6,3.2,(255,255,255,220),(0,0,0,0),0)
    d.arc([sc(cx-16),sc(174),sc(cx+16),sc(196)], 200, 340, fill=INK, width=sc(2.0))
    d.arc([sc(cx-12),sc(168),sc(cx+12),sc(178)], 200, 340, fill=INK, width=sc(1.6))
L(145, 210, 142, 214, INK, 1.4)
d.arc([sc(136),sc(216),sc(154),sc(230)], 20, 160, fill=INK, width=sc(1.8))
E(100,214,9,5.5,BLUSH,(0,0,0,0),0)
E(190,214,9,5.5,BLUSH,(0,0,0,0),0)
# pompom flower on top
for cx, cy, r in ((145,34,21),(118,42,16),(172,42,16),(128,16,14),(160,16,14),(158,46,13)):
    blob(cx, cy, r, r, HOOD, seed=13+cx, wobble=0.03)
    fur(cx, cy, r, r, HOOD_LT, 20, 17+cx, 2.6)
E(145, 40, 13, 12, (150, 214, 202, 255), INK, 1.2)
E(170, 24, 8, 7, (158, 202, 240, 255), INK, 1.0)
# mini Futa plush
E(100,318,11,9,PLUSH,INK,1.6); E(190,318,11,9,PLUSH,INK,1.6)
blob(145,348,48,45,PLUSH,seed=17,wobble=0.03)
fur(145,348,48,45,PLUSH_LT,100,19,3.4)
P([(112,306),(122,306),(117,318),(126,318),(112,340),(117,324),(107,324)], CYAN, INK, 0.9)
bar(118,338,9,32,-0.24,(42,25,31,255),INK,0.9)
bar(172,338,9,32, 0.24,(42,25,31,255),INK,0.9)
bar(145,338,10,34,0.0,(42,25,31,255),INK,0.9)
R(108,360,182,390,11,(44,24,30,255),INK,1.0)
for x in (116,130,144,158,172):
    P([(x-5,361),(x+5,361),(x,372)], WHITE, INK, 0.5)
for x in (123,137,151,165):
    P([(x-5,389),(x+5,389),(x,378)], WHITE, INK, 0.5)
R(98,372,108,390,6,PLUSH,INK,1.2); R(182,372,192,390,6,PLUSH,INK,1.2)
L(192,384,200,379,(180,170,160,255),1.0)
R(194,376,212,390,3,WHITE,INK,0.9)
blob(145,404,31,24,LEMON,seed=23,wobble=0.02)
L(138,392,145,384,(214,186,96,255),1.4)
L(152,392,145,384,(214,186,96,255),1.4)
L(145,394,145,386,(214,186,96,255),1.2)
E(145,388,6,4.5,(240,220,120,255),INK,1.0)
E(136,400,5.0,3.6,(255,255,226,255),(0,0,0,0),0)
E(141,394,2.8,2.2,(255,255,226,255),(0,0,0,0),0)
# hands over plush
blob(96,356,15,12,SLEEVE,seed=31,wobble=0.05)
blob(194,356,15,12,SLEEVE,seed=32,wobble=0.05)
E(96,360,11,10,SKIN,INK,1.5)
E(194,360,11,10,SKIN,INK,1.5)
L(92,361,100,361,(236,180,164,255),1.0)
L(190,361,198,361,(236,180,164,255),1.0)
L(96,356,96,364,(236,180,164,255),0.9)
L(194,356,194,364,(236,180,164,255),0.9)

small = img.resize((290, 436), Image.Resampling.LANCZOS)
small.save(r"E:\CppProject\futa_desktop\assets\pajama-girl.png")
bg = Image.new("RGB", (290, 436), (244, 241, 237)); bg.paste(small, (0, 0), small)
bg.resize((580, 872), Image.Resampling.LANCZOS).save(r"E:\CppProject\futa_desktop\assets\pajama-girl-preview.png")
print("saved")
