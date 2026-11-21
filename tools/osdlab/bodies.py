import os,sys,json,struct; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from osdlab import Script
B={'E137':dict(arr=0x6230de68,start=0x607f6de0,end=0x607f6e55,rect=0x60c952fb,upd=0x60c9588b,order=0x60c95b1b),
   'E144':dict(arr=0x62319a48,start=0x6088a21a,end=0x6088a28f,rect=0x60d52e49,upd=0x60d534c7,order=0x60d53757),
   'E148':dict(arr=0x62353b4c,start=0x6088aa3b,end=0x6088aab0,rect=0x60d54d22,upd=0x60d55352,order=0x60d555e2),
   'E143':dict(arr=0x62b3dfdc,start=0x60b0a7a7,end=0x60b0a81c,rect=0x610ddeda,upd=0x610de50e,order=0x610de79e),
   'E146':dict(arr=0x62b96214,start=0x60b1559d,end=0x60b15612,rect=0x610eaf3f,upd=0x610eb573,order=0x610eb803)}
# E-M5 II and PEN-F: 3 layers x 2 buffers as 16-byte VRAM records {addr, plane, 896, 600};
# buffer 1 of each plane is on screen, so the boxes show without an update call. vinfo = record address.
OLD={'E118':dict(start=0x606f0a01,end=0x606f0a57,rect=0x60baf748,recs=(0x618c56d4,0x618c56f4,0x618c56b4)),
     'E122':dict(start=0x606e25f4,end=0x606e264a,rect=0x60bccf1b,recs=(0x618eb3c0,0x618eb3e0,0x618eb3a0))}
def old_body(m):
    b=OLD[m]; s=Script(f'~/emu/runs/body-{m}',model=m).tok('wait:4000','shot:stock.png').call(b['start'])
    for L,(rec,x,y,c) in enumerate(zip(b['recs'],(100,200,300),(100,150,200),(11,86,5))):
        s.call(b['rect'],{'d0':x,'d1':y,'a1':250,'a0':rec},[200,c,L])
    recs,bad,err=s.call(b['end']).tok('wait:200','shot:draw.png').run()
    print(m,'bad',[(x.get('token'),x.get('error')) for x in bad][:2],err[-200:])
def notation(a): return a-0x10021020
for m in sys.argv[1:]:
    if m in OLD: old_body(m); continue
    b=B[m]
    s=Script(f'~/emu/runs/body-{m}',model=m).tok('wait:4000',f'read:{hex(b["arr"])}:48','shot:stock.png')
    recs,bad,err=s.run()
    arr=None
    for r in recs:
        if r.get('token','').startswith('read:'): arr=struct.unpack('<12I',bytes.fromhex(r['hex']))
    print(m,'bad',[x.get('error') for x in bad][:2], [hex(a) for a in arr] if arr else err[-300:])
    if not arr: continue
    s=Script(f'~/emu/runs/body-{m}',model=m).tok('wait:4000')
    s.call(b['start'])
    for L,(x,y,c) in enumerate(((100,100,11),(200,150,86),(300,200,5))):
        if not arr[L*4]: continue
        s.call(b['rect'],{'d0':x,'d1':y,'a1':250,'a0':arr[L*4]},[200,c,L])
    s.call(b['end']).call(b['upd'],{'d0':0}).tok('wait:300','shot:draw.png',*([] if m in ('E143','E146') else ['read:0x9c000044:12','read:0x9c0001a4:4']))
    recs,bad,err=s.run()
    print(m,'draw bad',[ (x.get('token'),x.get('error')) for x in bad][:2], [r.get('hex') for r in recs if r.get('token','').startswith('read')], err[-200:])
