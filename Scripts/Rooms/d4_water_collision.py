#!/usr/bin/env python3
"""Private D4 collision recipe; no ROM writes, preserves object/door cells."""
from pathlib import Path
import json,struct
import argparse
import sky_d8_room_writer as r
parser=argparse.ArgumentParser(description='Generate private paired water collision runs from native object footprints and rendered object bookkeeping.')
parser.add_argument('--tile-reports',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
O=args.tile_reports.resolve();W=Path(__file__).resolve().parents[2]
args.output.mkdir(parents=True,exist_ok=True)
def dec(rec):
 if rec[0]>=0xfc or rec[2]>=0xf8:
  a,x,y=r.decode_object(rec);return a,x,y,0
 return rec[2],rec[0]>>2,rec[1]>>2,((rec[0]&3)<<2)|(rec[1]&3)
audit=[]
for room in [0x25,0x37]:
 raw=(W/f'Data/Rooms/d4_water/{room:02x}-high.bin').read_bytes()
 high=r.parse_object_stream(raw,0,len(raw)).lists
 water=set()
 for rec in high[1]:
  a,x,y,n=dec(rec)
  if a in (0xc9,0xe7):
   for yy in range(y,y+4*((n&3)+1)):
    for xx in range(x,x+4*((n>>2)+1)):
     assert xx<64 and yy<64;water.add(yy*64+xx)
 for state in ['low','high']:
  d=json.loads((O/f'room-{room:02x}-{state}.tiles.json').read_text());attrs=d['attributes'];sources=d['attribute_sources'];changes={}
  for cell in water:
   # Object/door bookkeeping owns special cells; never flatten their attributes.
   if sources[4096+cell]==0:changes[4096+cell]=8 if state=='high' else 0
  if state=='low':
   # Native133 adds a deep-water approach even after the visual pool drains.
   for cell in range(4096):
    if sources[cell]==4 and attrs[cell]==8:changes[cell]=0
  if room==0x37 and state=='high':
   for yy in range(32,35):
    for xx in range(34,42):
     changes[yy*64+xx]=0;changes[4096+yy*64+xx]=1
  # Paused native220 failure02 proves25 C9/E7 tiles resolve to02.
  # Editor replay labels that native custom type08; retain the native preimage.
  first=min(changes);native_first=2 if room==0x25 and state=='high' else attrs[first];assert native_first!=changes[first], (room,state,'sentinel already native value')
  runs=[]
  for offset,value in sorted(changes.items()):
   if runs and offset==runs[-1][0]+runs[-1][1] and value==runs[-1][2] and runs[-1][1]<255:runs[-1][1]+=1
   else:runs.append([offset,1,value])
  raw=b''.join(struct.pack('<HBB',*run)for run in runs)+b'\xff\xff'
  (args.output/f'{room:02x}-{state}-collision.bin').write_bytes(raw)
  audit.append(dict(room=room,state=state,cells=len(changes),runs=len(runs),bytes=len(raw),sentinel=[first,native_first,changes[first]],specialCellsExcluded=sum(sources[4096+c]!=0 for c in water)))
(args.output/'COLLISION_RECEIPT.json').write_text(json.dumps(audit,indent=2)+'\n');print(json.dumps(audit,indent=2))
