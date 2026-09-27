import csv,re,colorsys,textwrap,sys
from PIL import Image, ImageDraw, ImageFont
SRC=sys.argv[1]; OUT=sys.argv[2]
R={int(r['map_id'],16):r for r in csv.DictReader(open(SRC))}
K=2                                  # supersample factor
CW,CH,G=150,108,12                   # cell w/h and gutter (logical px)
M=48
def s(v): return int(v*K)
AV='/System/Library/Fonts/Avenir Next.ttc'; DIN='/System/Library/Fonts/Supplemental/DIN Alternate Bold.ttf'
def av(sz,idx=7): return ImageFont.truetype(AV,s(sz),index=idx)
F_ID=ImageFont.truetype(DIN,s(22)); F_NAME=av(12.5,2); F_SMALL=av(11,5); F_PILL=av(11,0); F_H1=av(24,0); F_H2=av(13,7); F_LEG=av(13,5); F_LEGB=av(15,0)
regions=sorted({r['region'] for r in R.values()})
lw=[x for x in regions if x.startswith('LW')]; dw=[x for x in regions if x.startswith('DW')]; sw=[x for x in regions if x.startswith('SW')]
def cols(lst,sat,val,off): return {x:tuple(int(c*255) for c in colorsys.hsv_to_rgb((off+i*0.618)%1,sat,val)) for i,x in enumerate(lst)}
pal={}; pal.update(cols(lw,0.32,0.90,0.02)); pal.update(cols(dw,0.42,0.60,0.10)); pal.update(cols(sw,0.30,0.78,0.47)); pal['SW unused/blank']=(58,60,68)
OVL_BG=(44,50,68)
OVL={0x93:('Curtain overlay','used by 88'),0x94:('Under-bridge overlay','code only · no map'),0x95:('Sky clouds overlay','used by 05 06 07 84'),
     0x96:('Pyramid BG overlay','code only · no map'),0x97:('Fog overlay','used by 80 81 82 89 8A'),0x9C:('Lava overlay','code only · no map'),
     0x9D:('Fog 2 overlay','code only · no map'),0x9E:('Tree canopy overlay','used by 10 18 19 20 21 28 29'),0x9F:('Rain overlay','used by 1E 1F 26 27 2E 2F 30')}
def pos(m):
    if m<0x40: return (m%8, m//8)
    if m<0x80: i=m-0x40; return (i%8, 9.35+i//8)
    i=m-0x80; c=i%8; r=i//8
    if c<4: return (8.25+c, 1+r)
    return (9.25+(c-4), 6.1+r)
def xy(c,r): return (M+c*(CW+G), M+90+r*(CH+G))
Wl=M*2+13.5*(CW+G)+470; Hl=M*2+90+17.5*(CH+G)
img=Image.new('RGB',(s(Wl),s(Hl)),(15,17,22)); d=ImageDraw.Draw(img)
def T(x,y,t,f,c): d.text((s(x),s(y)),t,font=f,fill=c)
def RR(x0,y0,x1,y1,r,fill=None,outline=None,w=1): d.rounded_rectangle([s(x0),s(y0),s(x1),s(y1)],radius=s(r),fill=fill,outline=outline,width=s(w))
def lum(c): return 0.299*c[0]+0.587*c[1]+0.114*c[2]
def txt(c): return (18,20,26) if lum(c)>150 else (240,242,246)
def sub(c): return (60,62,72) if lum(c)>150 else (190,196,210)
# headers
T(M,14,'Oracle of Secrets — overworld map IDs',av(26,0),(245,245,248))
T(M,48,'Kalyxo (top-left) · special world beside the graveyard (top-right) · Eon Abyss under its Kalyxo mirror · static tile analysis 2026-09-27',F_H2,(170,176,190))
def header(c,r,title,subt):
    x,y=xy(c,r); T(x,y-50,title,F_H1,(245,245,248)); T(x,y-20,subt,F_H2,(165,170,185))
header(0,0,'KALYXO','Light World · 00–3F')
header(8.25,1,'SPECIAL WORLD','80–83 · 88–8B · 90–93 · 98–9B')
header(9.25,6.1,'SKY ISLANDS + OVERLAY SLOTS','drawn here for readability · in the game grid they are the right half of the special world')
header(0,9.35,'EON ABYSS / YESTERWIND','Dark World · 40–7F')
parents={}
for m,r in R.items(): parents.setdefault(int(r['parent'],16),[]).append(m)
def fillc(m,r): return OVL_BG if (m in OVL and m!=0x93) else pal.get(r['region'],(90,90,90))
# cells (large areas as one merged block)
done=set()
for p,ms in parents.items():
    r=R[p]; col=fillc(p,r)
    xs=[pos(m)[0] for m in ms]; ys=[pos(m)[1] for m in ms]
    x0,y0=xy(min(xs),min(ys)); x1,y1=xy(max(xs),max(ys)); x1+=CW; y1+=CH
    RR(x0,y0,x1,y1,8,fill=col,outline=(255,255,255) if len(ms)>1 else None,w=2.5 if len(ms)>1 else 1)
    if len(ms)>1:
        mx=(x0+x1)/2; my=(y0+y1)/2; dc=tuple(max(0,v-28) for v in col)
        d.line([s(mx),s(y0+6),s(mx),s(y1-6)],fill=dc,width=s(1.5)); d.line([s(x0+6),s(my),s(x1-6),s(my)],fill=dc,width=s(1.5))
# tags
PAD=(172,110,255); SPC=(255,205,70); WARN=(255,110,110)
tags={}
def tag(m,t,c): tags.setdefault(m,[]).append((t,c))
for a,b in [(0x25,0x65),(0x11,0x51),(0x02,0x42),(0x03,0x43),(0x07,0x47),(0x17,0x57),(0x37,0x77)]: tag(a,'PAD to %02X'%b,PAD); tag(b,'PAD from %02X'%a,PAD)
tag(0x6A,'PAD to 2A',PAD); tag(0x2A,'PAD from 6A',PAD); tag(0x3D,'WHIRLPOOL to ABYSS',PAD)
tag(0x0F,'TO 81 (HAMMER)',SPC); tag(0x81,'FROM 0F GRAVEYARD',SPC)
for a in (0x2A,0x17,0x20): tag(a,'TO 80',SPC)
tag(0x80,'FROM 2A · 17 · 20',SPC); tag(0x33,'TO 91',SPC); tag(0x91,'FROM 33',SPC)
tag(0x83,'TEST BRIDGE TO 84',WARN); tag(0x84,'TEST BRIDGE FROM 83',WARN)
def badges(g):
    out=[]
    for k,ab in (('Glove','G'),('Mitt','M'),('Hammer','H'),('Boots','B')):
        m=re.search(k+r' x\d+ tiles \{([^}]*)\}',g)
        if m and ('ROUTE' in m.group(1) or 'POCKET' in m.group(1)): out.append((ab,'ROUTE' in m.group(1)))
    return out
BADGE={'G':((196,200,208),(20,20,24)),'M':((10,10,12),(255,255,255)),'H':((232,138,52),(20,20,24)),'B':((88,176,255),(20,20,24))}
def draw_badge(x,y,k,route):
    bg,fg=BADGE[k]; r=10
    if k=='H': RR(x,y,x+2*r,y+2*r,4,fill=bg,outline=(255,255,255) if route else (110,110,120),w=2)
    else: d.ellipse([s(x),s(y),s(x+2*r),s(y+2*r)],fill=bg,outline=(255,255,255) if route else (110,110,120),width=s(2))
    tw=d.textlength(k,font=F_PILL)/K; T(x+r-tw/2,y+2.5,k,F_PILL,fg)
for m,r in R.items():
    c,rw=pos(m); x,y=xy(c,rw); col=fillc(m,r); p=int(r['parent'],16)
    T(x+8,y+4,'%02X'%m,F_ID,txt(col))
    yy=y+32
    if m in OVL:
        nm,use=OVL[m]
        if m==0x93: T(x+8,yy,'East Kalyxo draft',F_NAME,txt(col)); yy+=16; nm='also '+nm
        onov=(m!=0x93)
        T(x+8,yy,nm,F_NAME,(150,210,255) if onov else txt(col)); yy+=16
        for l in textwrap.wrap(use,20)[:2]: T(x+8,yy,l,F_SMALL,(200,205,218) if onov else sub(col)); yy+=14
    elif p==m:
        nm=(r['name'] or '').split('(')[0].strip()
        nl=1 if len(tags.get(m,[]))>1 else 2
        for l in textwrap.wrap(nm,17 if nl==2 else 24)[:nl]: T(x+8,yy,l,F_NAME,txt(col)); yy+=16
    ty=y+CH-26
    for t,cc in tags.get(m,[])[:1]:
        tw=d.textlength(t,font=F_PILL)/K
        RR(x+7,ty,x+7+tw+12,ty+18,9,fill=(18,18,24)); T(x+13,ty+1.5,t,F_PILL,cc)
    if len(tags.get(m,[]))>1:
        t,cc=tags[m][1]; tw=d.textlength(t,font=F_PILL)/K; RR(x+7,ty-21,x+7+tw+12,ty-3,9,fill=(18,18,24)); T(x+13,ty-19.5,t,F_PILL,cc)
    for i,(k,route) in enumerate(badges(r['gates'])):
        draw_badge(x+CW-28-i*24,y+6,k,route)
# edges in gutters
EC={'open':(70,220,110),'blocked':(230,70,70),'swim':(80,160,255),'special':(140,144,156)}
drawn=set()
for m,r in R.items():
    for t in r['neighbors'].split():
        mm=re.match(r'([NESW])->\$([0-9A-Fa-f]{2})(?:\(([0-9A-Fa-f]{2})\))?:(\w+)',t)
        if not mm: continue
        dr,tgt,q,st=mm.groups(); tgt=int(q or tgt,16)
        if t.endswith('(special'): st='special'
        key=tuple(sorted((m,tgt)))
        if key in drawn: continue
        drawn.add(key)
        (c1,r1),(c2,r2)=pos(m),pos(tgt)
        if abs(abs(c1-c2)+abs(r1-r2)-1)>1e-6: continue
        if int(R[m]['parent'],16)==int(R[tgt]['parent'],16): continue
        if (m in OVL and m!=0x93) or (tgt in OVL and tgt!=0x93): continue   # overlay slots are not maps
        x1,y1=xy(c1,r1); col=EC.get(st,EC['special'])
        if c2!=c1:
            gx=x1+CW+G/2 if c2>c1 else x1-G/2; gy=y1+CH/2
            if st=='blocked': d.line([s(gx),s(y1+10),s(gx),s(y1+CH-10)],fill=col,width=s(3))
            else: RR(gx-8,gy-5,gx+8,gy+5,4,fill=col)
        else:
            gy=y1+CH+G/2 if r2>r1 else y1-G/2; gx=x1+CW/2
            if st=='blocked': d.line([s(x1+10),s(gy),s(x1+CW-10),s(gy)],fill=col,width=s(3))
            else: RR(gx-5,gy-8,gx+5,gy+8,4,fill=col)
# legend cards
lx,ly=xy(9.25,10.55)
RR(lx-14,ly-14,lx+440,ly+560,12,fill=(24,27,34))
T(lx,ly,'Regions',F_LEGB,(245,245,248)); ly+=28
for g in (lw,sw,dw):
    for rg in g:
        RR(lx,ly+2,lx+18,ly+16,4,fill=pal[rg]); T(lx+28,ly,rg[3:],F_LEG,(215,220,230)); ly+=19
    ly+=8
RR(lx,ly+2,lx+18,ly+16,4,fill=OVL_BG,outline=(90,100,130)); T(lx+28,ly,'Overlay slot (graphics layer, not a map)',F_LEG,(215,220,230))
lx2=lx+470; ly2=xy(9.25,10.55)[1]
RR(lx2-14,ly2-14,lx2+360,ly2+560,12,fill=(24,27,34))
T(lx2,ly2,'Gates',F_LEGB,(245,245,248)); ly2+=28
for k,t in (('G','Glove rocks'),('M','Mitt (heavy) rocks'),('H','Hammer pegs'),('B','Boots only')):
    draw_badge(lx2,ly2,k,True); T(lx2+32,ly2+1,t,F_LEG,(215,220,230)); ly2+=26
T(lx2,ly2,'white ring = blocks a route · grey ring = pocket only',F_SMALL,(165,170,185)); ly2+=30
T(lx2,ly2,'Edges between maps',F_LEGB,(245,245,248)); ly2+=28
for k,t in (('open','walkable'),('swim','swim only'),('special','special / camera edge')):
    RR(lx2,ly2+3,lx2+16,ly2+13,4,fill=EC[k]); T(lx2+32,ly2,t,F_LEG,(215,220,230)); ly2+=22
d.line([s(lx2),s(ly2+8),s(lx2+16),s(ly2+8)],fill=EC['blocked'],width=s(3)); T(lx2+32,ly2,'blocked (cliff, trees, wall)',F_LEG,(215,220,230)); ly2+=34
T(lx2,ly2,'Links',F_LEGB,(245,245,248)); ly2+=28
for t,c,e in (('PAD to 65',PAD,'warp pad to the other world'),('TO 81',SPC,'entrance into a special map'),('TEST',WARN,'test link / warning')):
    tw=d.textlength(t,font=F_PILL)/K; RR(lx2,ly2,lx2+tw+12,ly2+18,9,fill=(18,18,24)); T(lx2+6,ly2+1.5,t,F_PILL,c); T(lx2+tw+22,ly2+1,e,F_LEG,(215,220,230)); ly2+=26
RR(lx2,ly2+2,lx2+26,ly2+18,5,outline=(255,255,255),w=2.5); T(lx2+36,ly2+1,'large 2×2 area',F_LEG,(215,220,230)); ly2+=36
for l in ('Not drawn: water gates (Flippers).','Pad 25 to 65 needs no item and','opens most of the Abyss.','"Code only" overlays are unused by','any map: reclaim candidates (verify).'):
    T(lx2,ly2,l,F_SMALL,(165,170,185)); ly2+=16
img=img.resize((int(img.width/1.25),int(img.height/1.25)),Image.LANCZOS)
img.save(OUT,optimize=True); print(img.size)
