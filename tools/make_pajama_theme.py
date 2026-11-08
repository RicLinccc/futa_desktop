# -*- coding: utf-8 -*-
"""assets/pajama-girl.png v5: big-head chibi matching Futa's proportions."""
import math, random
from PIL import Image, ImageDraw

S = 4
W, H = 290*S, 436*S
INK = (76, 38, 40, 255)
HOOD = (244, 96, 168, 255)
HOOD_DK = (208, 66, 136, 255)
HOOD_LT = (255, 156, 203, 255)
ROBE = (251, 213, 217, 255)
ROBE_DK = (236, 184, 192, 255)
SLEEVE = (226, 134, 174, 255)
PLUSH = (233, 108, 162, 255)
PLUSH_LT = (250, 158, 194, 255)
LINING = (176, 205, 232, 255)
DARK = (120, 58, 74, 255)
SKIN = (248, 209, 190, 255)
HAIR = (72, 46, 52, 255)
LEMON = (251, 243, 155, 255)
LEMON_DK = (202, 151, 55, 255)
LEAF = (124, 166, 92, 255)
WHITE = (251, 226, 228, 255)
SHOE = (58, 38, 44, 255)
BUTTON = (198, 66, 88, 255)
CYAN = (170, 239, 246, 255)

img = Image.new("RGBA", (W,H), (0,0,0,0))
d = ImageDraw.Draw(img)
def sc(v): return int(round(v*S))
def E(cx,cy,rx,ry,fill,outline=INK,width=2.2):
    d.ellipse([sc(cx-rx),sc(cy-ry),sc(cx+rx),sc(cy+ry)], fill=fill, outline=outline, width=max(1,sc(width)))
def blob(cx,cy,rx,ry,fill,outline=INK,width=2.2,wobble=0.012,n=160,seed=1):
    rnd=random.Random(seed); pts=[]
    for i in range(n):
        a=2*math.pi*i/n; r=1.0+rnd.uniform(-wobble,wobble)
        pts.append((sc(cx+rx*r*math.cos(a)), sc(cy+ry*r*math.sin(a))))
    d.polygon(pts, fill=fill, outline=outline, width=max(1,sc(width)))
def P(pts,fill,outline=INK,width=2.2):
    d.polygon([(sc(x),sc(y)) for x,y in pts], fill=fill, outline=outline, width=max(1,sc(width)))
def R(x0,y0,x1,y1,r,fill,outline=INK,width=2.2):
    d.rounded_rectangle([sc(x0),sc(y0),sc(x1),sc(y1)], radius=sc(r), fill=fill, outline=outline, width=max(1,sc(width)))
def L(x0,y0,x1,y1,color,width=2.0):
    d.line([sc(x0),sc(y0),sc(x1),sc(y1)], fill=color, width=max(1,sc(width)))
def fur(cx,cy,rx,ry,color=HOOD_LT,count=90,seed=5,length=4.0):
    rnd=random.Random(seed)
    for i in range(count):
        a=2*math.pi*rnd.uniform(-1,1)
        x=cx+rx*math.cos(a); y=cy+ry*math.sin(a)
        L(x,y,x+length*math.cos(a),y+length*math.sin(a),color,1.0)

# ---- tiny legs ----
R(116,388,142,408,8,WHITE); R(152,388,178,408,8,WHITE)
L(116,400,142,400,INK,1.4); L(152,400,178,400,INK,1.4)
R(104,404,146,428,12,SHOE); R(148,404,190,428,12,SHOE)
L(122,414,120,421,(110,90,96,255),1.1); L(170,414,172,421,(110,90,96,255),1.1)

# ---- small body ----
P([(86,256),(204,256),(218,330),(228,390),(184,402),(145,406),(106,402),(62,390),(72,330)], ROBE)
P([(190,258),(218,330),(228,390),(198,398),(206,326),(182,262)], ROBE_DK)
L(145,262,145,396,ROBE_DK,2.0)
for by in (282,312,342,372,394): E(145,by,4.0,4.0,BUTTON,INK,1.2)
R(92,338,126,370,9,SLEEVE); R(164,338,198,370,9,SLEEVE)
for cx in (109,181):
    P([(cx-5,344),(cx+3,344),(cx-2,354),(cx+4,354),(cx-4,366),(cx,356),(cx-6,356)], CYAN, INK, 1.1)
# hem fluff
fur(145,398,80,7,ROBE_DK,50,21,3.0)

# ---- arms (short stubs) ----
P([(90,262),(78,284),(66,298),(54,306),(52,322),(68,320),(82,302),(96,284)], SLEEVE)
P([(200,262),(214,284),(228,300),(240,306),(242,322),(226,320),(212,304),(198,284)], SLEEVE)
# wrist fur cuffs
blob(70,306,14,11,WHITE,seed=31,wobble=0.05)
blob(228,310,14,11,WHITE,seed=32,wobble=0.05)

# ---- hood / head ----
blob(145,150,112,116,HOOD,seed=11,wobble=0.012)
fur(145,150,112,116,HOOD_LT,170,15,5.5)
# inner opening
E(145,160,84,84,DARK,INK,2.2)
d.arc([sc(61),sc(78),sc(229),sc(240)],205,335,fill=LINING,width=sc(10))
d.arc([sc(61),sc(78),sc(229),sc(240)],205,335,fill=INK,width=sc(1.2))

# ---- face ----
E(145,172,74,72,SKIN,INK,2.0)
# hair bangs
P([(72,160),(78,124),(104,108),(145,104),(186,108),(212,124),(218,160),(198,146),(178,136),(145,150),(112,136),(92,146)], HAIR)
P([(70,164),(66,226),(82,236),(88,164)], HAIR)
P([(220,164),(224,226),(208,236),(202,164)], HAIR)
# eyes
R(108,158,126,192,9,(42,25,31,255)); R(164,158,182,192,9,(42,25,31,255))
E(114,164,3.0,4.2,(255,255,255,255),(0,0,0,0),0); E(170,164,3.0,4.2,(255,255,255,255),(0,0,0,0),0)
L(104,148,128,144,HAIR,2.4); L(162,144,186,148,HAIR,2.4)
E(92,196,9,5.5,(248,150,160,255),(0,0,0,0),0); E(198,196,9,5.5,(248,150,160,255),(0,0,0,0),0)
d.arc([sc(136),sc(200),sc(154),sc(216)], 20, 160, fill=INK, width=sc(2.2))

# ---- pom + flower ----
blob(148,34,25,23,HOOD,seed=13,wobble=0.03)
fur(148,34,25,23,HOOD_LT,45,17,3.8)
blob(166,24,11,10,(158,202,240,255),seed=14,wobble=0.03)
for k in range(5):
    a=2*math.pi*k/5
    E(88+10*math.cos(a),92+10*math.sin(a),7,7,(255,206,226,255),INK,1.0)
E(88,92,4.4,4.4,(255,236,150,255),INK,1.0)

# ---- Futa plush at her left ----
blob(52,330,44,38,PLUSH,seed=17,wobble=0.02)
fur(52,330,44,38,PLUSH_LT,60,19,3.4)
for k in range(5):
    a=2*math.pi*k/5
    E(52+7*math.cos(a),292+7*math.sin(a),5.0,5.0,(255,210,228,255),INK,0.9)
E(52,292,3.3,3.3,(255,236,150,255),INK,0.9)
R(29,316,39,340,6,(42,25,31,255),INK,1.2)
R(65,316,75,340,6,(42,25,31,255),INK,1.2)
R(25,346,79,364,10,(44,24,30,255),INK,1.2)
for x in (37,52,67): P([(x-4,347),(x+4,347),(x,355)],WHITE,INK,0.7)
for x in (45,60): P([(x-4,363),(x+4,363),(x,356)],WHITE,INK,0.7)
E(10,346,8,7,PLUSH,INK,1.4); E(94,346,8,7,PLUSH,INK,1.4)
# hand on plush
E(70,302,11,10,SKIN,INK,1.6)

# ---- lemon in her right hand ----
E(230,312,12,11,SKIN,INK,1.6)
blob(232,342,28,24,LEMON,seed=23,wobble=0.015)
E(232,314,6.2,6.2,LEMON_DK,INK,1.3)
P([(228,315),(214,310),(208,301),(220,303),(230,309)],LEAF,INK,1.0)
P([(236,315),(250,310),(256,301),(244,303),(234,309)],LEAF,INK,1.0)
E(220,332,5.0,3.6,(255,255,226,255),(0,0,0,0),0)
E(225,325,2.8,2.2,(255,255,226,255),(0,0,0,0),0)
L(250,352,254,348,(180,170,160,255),1.2)
R(246,352,264,366,3,WHITE,INK,1.0)

small=img.resize((290,436), Image.Resampling.LANCZOS)
small.save(r"E:\CppProject\futa_desktop\assets\pajama-girl.png")
bg=Image.new("RGB",(290,436),(244,241,237)); bg.paste(small,(0,0),small)
bg.resize((580,872), Image.Resampling.LANCZOS).save(r"E:\CppProject\futa_desktop\assets\pajama-girl-preview.png")
print("saved")