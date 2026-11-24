"""Set MP4 movie, track and last-frame end on the decoded audio's sample clock."""
import struct
from dataclasses import dataclass
from pathlib import Path
U32=struct.Struct('>I');U64=struct.Struct('>Q')
containers={b'moov',b'trak',b'mdia',b'minf',b'stbl',b'edts'}
def get(buf,pos,wide=False):return (U64 if wide else U32).unpack_from(buf,pos)[0]
def setv(buf,pos,n,wide=False):(U64 if wide else U32).pack_into(buf,pos,n)
@dataclass
class Atom:
    kind:bytes
    data:bytearray
    children:list
    def encode(self):
        payload=b''.join(c.encode() for c in self.children) if self.children else self.data
        return struct.pack('>I4s',len(payload)+8,self.kind)+payload
    def child(self,t):
        return next(c for c in self.children if c.kind==t)
def parse(raw):
    p=0;result=[]
    while p<len(raw):
        length,typ=struct.unpack_from('>I4s',raw,p);header=8
        if length==1:length=get(raw,p+8,True);header=16
        if length==0:length=len(raw)-p
        if not(header<=length<=len(raw)-p):raise ValueError('Invalid MP4 box size')
        sub=raw[p+header:p+length]
        result.append(Atom(typ,bytearray() if typ in containers else bytearray(sub),parse(sub) if typ in containers else []))
        p+=length
    return result
def clocks(atom):
    v=atom.data[0];idx=20 if v else 12
    return get(atom.data,idx),idx+4,bool(v)
def duration(atom,total):
    _,idx,wide=clocks(atom);setv(atom.data,idx,total,wide)
def finish(src,dst,samples,rate,fps):
    top=parse(Path(src).read_bytes());movie=next(b for b in top if b.kind==b'moov')
    old=len(movie.encode());mh=movie.child(b'mvhd')
    movie_tick=clocks(mh)[0];end=round(samples*movie_tick/rate);duration(mh,end)
    assert next(i for i,a in enumerate(top) if a.kind==b'moov') < next(i for i,a in enumerate(top) if a.kind==b'mdat')
    for track in [c for c in movie.children if c.kind==b'trak']:
        md=track.child(b'mdia');tk=track.child(b'tkhd')
        setv(tk.data,28 if tk.data[0] else 20,end,bool(tk.data[0]))
        ed=track.child(b'edts').child(b'elst')
        if get(ed.data,4)!=1:raise ValueError('Expected a single media edit')
        setv(ed.data,8,end,bool(ed.data[0]))
        if md.child(b'hdlr').data[8:12]!=b'vide':continue
        head=md.child(b'mdhd');scale=clocks(head)[0];ticks=round(samples*scale/rate)
        tab=md.child(b'minf').child(b'stbl');n=get(tab.child(b'stsz').data,8)
        step=scale//fps;last=ticks-(n-1)*step
        if not(0<last<2*step) or scale%fps:raise ValueError('Video clock cannot represent target')
        duration(head,ticks)
        if n == 1:
            tab.child(b'stts').data = bytearray(struct.pack('>4I', 0, 1, 1, last))
        else:
            tab.child(b'stts').data = bytearray(struct.pack('>6I', 0, 2, n-1, step, 1, last))
    delta=len(movie.encode())-old
    if delta:
        for tr in [c for c in movie.children if c.kind==b'trak']:
            tab=tr.child(b'mdia').child(b'minf').child(b'stbl')
            off=next(c for c in tab.children if c.kind in {b'stco',b'co64'});wide=off.kind==b'co64'
            for i in range(get(off.data,4)):
                p=8+i*(8 if wide else 4);setv(off.data,p,get(off.data,p,wide)+delta,wide)
    tmp=Path(dst).with_suffix('.part');tmp.write_bytes(b''.join(b.encode() for b in top));tmp.replace(dst)
