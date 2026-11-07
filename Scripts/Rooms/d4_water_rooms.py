#!/usr/bin/env python3
"""Approved dam/spillway layout recipe for frozen native192 D4 authoring input.

This is a private prototype writer. It preserves the original interroom stairs,
keys, chests and doors; only the obsolete one-way lever actor is replaced.
The matching default-off controller consumes the four emitted object streams.
"""
from pathlib import Path
import hashlib, json, sys
sys.dont_write_bytecode=True
import argparse
parser=argparse.ArgumentParser(description='Materialize the approved private D4 low/high room recipe; writes only with --write.')
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--write',action='store_true',required=True)
args=parser.parse_args()
W=Path(__file__).resolve().parents[2]
O=args.output.resolve(); O.mkdir(parents=True,exist_ok=True)
source=args.source.resolve()
sha=lambda b:hashlib.sha256(b).hexdigest()
base=source.read_bytes(); assert sha(base)=='e1478831c8e34208703296a77a15a63ce597b79cc731efcbfadcfee778448f36'
import importlib.util
spec=importlib.util.spec_from_file_location('writer',W/'Scripts/Rooms/sky_d8_room_writer.py');r=importlib.util.module_from_spec(spec);sys.modules['writer']=r;spec.loader.exec_module(r)
inv=r.build_inventory(base)
def enc(a,x,y,n=0):
    assert 0 <= x < 64 and 0 <= y < 64 and 0 <= n < 16
    if a < 0x100: return bytes([x*4+(n>>2), y*4+(n&3), a])
    if a < 0x140: return bytes([0xfc|(x>>4), ((x&15)<<4)|(y>>2), ((y&3)<<6)|(a&63)])
    return r.encode_type3(a,x,y)

def dec(rec):
    if rec[0] >= 0xfc or rec[2] >= 0xf8:
        a,x,y = r.decode_object(rec); return a,x,y,0
    return rec[2], rec[0]>>2, rec[1]>>2, ((rec[0]&3)<<2)|(rec[1]&3)

def rectangle_frame(x0,y0,x1,y1):
    out = [enc(0x108,x0,y0),enc(0x10A,x1,y0),enc(0x109,x0,y1),enc(0x10B,x1,y1)]
    # BothBG native walls between fixed four-tile corner objects.
    for a,y in [(3,y0),(4,y1)]:
        x=x0+4; remaining=x1-x
        while remaining:
            count=min(16,remaining//2); assert count>0
            out.append(enc(a,x,y,count-1)); x+=count*2; remaining-=count*2
    height=y1-y0-4
    if height:
        assert height%2==0
        out += [enc(0x63,x0,y0+4,height//2-1), enc(0x64,x1,y0+4,height//2-1)]
    return out

def dam(state):
    old=inv.objects[0x25]
    # Keep the lower retaining ledge and every stair record in its original slot.
    primary=[]
    for rec in old.lists[0]:
        a,x,y,n=dec(rec)
        if (a,x,y,n) in [(0x69,29,24,15),(0x8A,21,7,13),(0x8A,50,14,6)]: continue
        if a==0x11F and (x,y)==(24,8):
            rec=enc(a,41,51)  # Native star-switch art for proposed maintenance latch.
        primary.append(rec)
    # Upper settling basin fits between the protected stair gallery and lower ledge.
    primary += [enc(0xC5,12,28,13), enc(0xC5,28,28,13), enc(0xC5,44,28,1)]
    primary += rectangle_frame(9,25,49,35)
    primary += [enc(0xFED,22,35),enc(0xFED,38,35)]
    primary += [enc(0x133,29,25)]  # Pool access only; no room destination.
    overlay=[]
    if state=='high':
        # Native D9 reveals include the retaining face; C9 surface is inset.
        overlay += [enc(0xD9,x,y,14) for y in [25,27] for x in [9,25,37]]
        overlay += [enc(0xC9,10,26,14),enc(0xC9,26,26,14),enc(0xC9,40,26,10)]
        overlay += list(old.lists[1])
    else:
        overlay += [enc(0xDB,10,26,14),enc(0xDB,26,26,14),enc(0xDB,40,26,10)]
        # Preserve the lower floor pattern; draining is not a blue color overlay.
        overlay += [enc(0xDB,6,44,15),enc(0xDB,22,44,15),enc(0xDB,38,44,15),enc(0xDB,54,44,3)]
    return [primary,overlay,list(old.lists[2])]

def spillway(state):
    old=inv.objects[0x37]
    # All native walls, pots, chest and water-entry stairs retain exact records.
    primary=list(old.lists[0])
    # Native lever art on the existing dry west landing; gameplay is still proposed.
    primary += [enc(0x124,13,20)]
    if state=='high':
        primary += [enc(0xFEC,34,32),enc(0xFEC,38,32)]
    overlay=[]
    for rec in old.lists[1]:
        a,x,y,n=dec(rec)
        permanent_north = False
        if state=='high' or permanent_north or a not in (0xC9,0xD9):
            overlay.append(rec)
        elif a==0xC9:
            overlay.append(enc(0xDB,x,y,n))
    return [primary,overlay,list(old.lists[2])]

out=bytearray(base);tail=max(s.end for s in inv.objects if r.OBJECT_ALLOC_REGION[0]<=s.pc<r.OBJECT_ALLOC_REGION[1]);plans=[];audit=[]
data_dir=O/'streams';data_dir.mkdir(parents=True,exist_ok=True)
for room,maker in [(0x25,dam),(0x37,spillway)]:
 old=inv.objects[room]
 for state in ['low','high']:
  lists=maker(state);stream,dooroff=r.encode_object_stream(old.header,lists,old.doors)
  (data_dir/f'{room:02x}-{state}.bin').write_bytes(stream)
  oldstairs=[rec for ls in old.lists for rec in ls if dec(rec)[0]in(0x133,0x135,0x138,0x139)]
  stairs=[rec for ls in lists for rec in ls if dec(rec)[0]in(0x133,0x135,0x138,0x139)]
  if room==0x25:stairs.remove(enc(0x133,29,25))
  assert stairs==oldstairs
  assert [rec for ls in lists for rec in ls if dec(rec)[0] in (0xF99,0xFB1)]==[rec for ls in old.lists for rec in ls if dec(rec)[0] in (0xF99,0xFB1)]
  if state=='low': assert not any(dec(rec)[0] in (0xC9,0xD9)for rec in lists[1])
  edits=[]
  def edit(pc,after):
   before=base[pc:pc+len(after)];assert len(before)==len(after);edits.append(dict(pc=pc,before=list(before),after=list(after)))
  assert tail+len(stream)<r.OBJECT_ALLOC_REGION[1] and not any(base[tail:tail+len(stream)])
  edit(tail,stream);edit(r.OBJECT_TABLE_PC+room*3,r.encode_long(tail,inv.obj_ptr[room]));edit(r.DOOR_TABLE_PC+room*3,r.encode_long(tail+dooroff,inv.door_ptr[room]))
  if room==0x25:
   edit(inv.header_pc[room]+4,bytes([0 if state=='low' else 3]))
   edit(inv.header_pc[room]+5,b'\x00') # obsolete irreversible WaterOff tag
  plans.append(dict(room=room,output=f'room-{room:02x}-{state}.png',memory_edits=edits))
  if state=='low':
   for e in edits:out[e['pc']:e['pc']+len(e['after'])]=bytes(e['after'])
   tail+=len(stream)
  audit.append(dict(room=room,state=state,streamBytes=len(stream),sha256=sha(stream),stairsExact=True,chestsExact=True,doorsExact=True))
# Replace only the obsolete native water-lever actor; its object art remains.
a,z=inv.spr_span[0x25];assert list(inv.spr_span).count((a,z))==1
assert base[a:z]==bytes.fromhex('00 06 07 21 05 13 39 ff')
out[a:a+5]=bytes.fromhex('00 05 13 39 ff')
ni=r.build_inventory(bytes(out))
for room in range(296):
 b=r.logical_room(base,inv,room);a=r.logical_room(bytes(out),ni,room)
 if room not in [0x25,0x37]:assert a==b,room
 for key in ['sprites','pots']:
  if room==0x25 and key=='sprites':continue
  assert a[key]==b[key]
assert out[r.CHEST_TABLE_PC:r.CHEST_TABLE_PC+r.CHEST_CAPACITY]==base[r.CHEST_TABLE_PC:r.CHEST_TABLE_PC+r.CHEST_CAPACITY]
assert out[0x128090:0x130000]==base[0x128090:0x130000]
private=O/'d4-water-low-editable.sfc';assert not private.exists(), 'Use a fresh output directory';private.write_bytes(out)
(O/'PREVIEWS.json').write_text(json.dumps(dict(previews=plans),indent=2)+'\n')
(O/'LAYOUT_RECEIPT.json').write_text(json.dumps(dict(base=str(source),baseSha256=sha(base),private=str(private),privateSha256=sha(out),tail=hex(tail),states=audit,other294RoomsExact=True,other295SpriteStreamsExact=True,all296PotsExact=True,obsoleteRoom25LeverRemoved=True,allChestDataExact=True,customCollisionExact=True),indent=2)+'\n')
print(json.dumps({'private':str(private),'sha256':sha(out),'tail':hex(tail),'states':audit},indent=2))
