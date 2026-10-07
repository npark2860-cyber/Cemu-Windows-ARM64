"""Offline FWAV DSP-ADPCM amplitude envelopes -> BNVIB. Never writes game files."""
from pathlib import Path
import struct, math, json, argparse, hashlib, csv
from inspect_audio import tracks

ROOT=Path(__file__).parent
RATE=200
SELECT={
 'MotorcycleEngineIdling':('idle',45,0.30),
 'MotorcycleEngine':('driving_unsplit',75,0.40),
 'MotorcycleEngineOffThrottle':('coasting_not_low_speed',55,0.30),
 'Motorcycle_EngineJump00':('jump',85,0.55),
 'Motorcycle_EngineJump01':('jump',85,0.55),
 'Motorcycle_EngineJump02':('jump',85,0.55),
 'MotorcycleBrakeLever':('brake_lever',90,0.65),
 'Motorcycle_WheelFrictionCmnBrake':('brake_friction',65,0.45),
}

def decode_dsp(raw,coef,count,h1=0,h2=0):
    out=[]
    for base in range(0,len(raw),8):
        frame=raw[base:base+8]
        assert len(frame)==8
        pred,shift=frame[0]>>4,frame[0]&15
        assert pred<8
        a,b=coef[2*pred:2*pred+2]
        for j in range(14):
            n=(frame[1+j//2]>>(4 if j%2==0 else 0))&15
            if n>=8:n-=16
            v=max(-32768,min(32767,((n*(1<<shift)*2048)+1024+a*h1+b*h2)>>11))
            out.append(v);h2,h1=h1,v
            if len(out)==count:return out
    raise ValueError('truncated DSP samples')

def decode(row,d):
    assert row['codec']==2 and row['channels']==1
    e=row['endian'];ci=row['channel_info'][0]
    u=lambda a:struct.unpack_from(e+'I',d,a)[0]
    coefpos=ci+u(ci+12)
    coef=struct.unpack_from(e+'16h',d,coefpos)
    h1,h2=struct.unpack_from(e+'hh',d,coefpos+34)
    # Existing assets should begin without ADPCM history, matching vgmstream.
    assert h1==h2==0,(row['track'],h1,h2)
    pos=row['data']+8+u(ci+4)
    size=((row['samples']+13)//14)*8
    assert pos+size<=row['data']+u(row['data']+4)
    return decode_dsp(d[pos:pos+size],coef,row['samples'],h1,h2)

def envelope(pcm,sr,peak,high_ratio,loop_start=None):
    # 200 Hz amplitude control points, not 200 Hz vibration carrier.
    # 180 Hz low-pass separates two amplitude envelopes. No audio is emitted.
    alpha=1-math.exp(-2*math.pi*180/sr)
    low=0.; low_sq=[]; high_sq=[]
    for v in pcm:
        low+=alpha*(v-low)
        low_sq.append(low*low);high_sq.append((v-low)**2)
    n=math.ceil(len(pcm)*RATE/sr);env=[]
    for j in range(n):
        a=j*sr//RATE;b=min(len(pcm),(j+1)*sr//RATE)
        env.append((math.sqrt(sum(low_sq[a:b])/(b-a)),math.sqrt(sum(high_sq[a:b])/(b-a))))
    # Per-clip shaping for a conservative first tactile audition, not loudness matching.
    scale=max(max(x) for x in env) or 1
    frames=[];pl=ph=0.
    for i,(l,h) in enumerate(env):
        l=peak*math.sqrt(l/scale);h=peak*high_ratio*math.sqrt(h/scale)
        pl+= (0.65 if l>pl else 0.20)*(l-pl)
        ph+= (0.65 if h>ph else 0.20)*(h-ph)
        fade=min(1,(i+1)/4)
        if loop_start is None:fade*=min(1,(n-1-i)/6)
        frames.append([round(pl*fade),96,round(ph*fade),139])
    if loop_start is not None:
        start=min(n-2,max(0,round(loop_start*RATE/sr)))
        # Match the endpoint to the loop entry to limit amplitude discontinuity.
        for k in range(min(6,n-start)):
            t=(k+1)/min(6,n-start);idx=n-min(6,n-start)+k
            for ch in (0,2):frames[idx][ch]=round(frames[idx][ch]*(1-t)+frames[start][ch]*t)
    else:start=None
    body=bytes(v for f in frames for v in f)
    header=struct.pack('<IHH',12 if start is not None else 4,3,RATE)
    if start is not None:header+=struct.pack('<II',start,n)
    return header+struct.pack('<I',len(body))+body

def main():
    ap=argparse.ArgumentParser();ap.add_argument('sound_root',type=Path);args=ap.parse_args()
    assets={}; inventory=[]
    for f in sorted(args.sound_root.glob('*GameROMMotorcycle*.bars')):
        d=f.read_bytes()
        for row in tracks(f):
            if row['track'] not in SELECT:continue
            state,peak,ratio=SELECT[row['track']]
            pcm=decode(row,d)
            clip=envelope(pcm,row['rate'],peak,ratio,row['loop_start'] if row['loop'] else None)
            assets[row['track']]=clip
            inventory.append(dict(row,logical_state=state,pcm_peak=max(abs(x) for x in pcm),haptic_sha256=hashlib.sha256(clip).hexdigest(),source_sha256=hashlib.sha256(d).hexdigest()))
    assert len(assets)==len(SELECT)
    out=ROOT/'MasterCycleHapticsPreview';out.mkdir(exist_ok=True)
    for profile in ('EngineOnly','ActionsOnly','CombinedDiagnostic'):
        folder=out/profile;(folder/'haptics').mkdir(parents=True,exist_ok=True)
        engine={'idle','driving_unsplit','coasting_not_low_speed'}
        selected=[r for r in inventory if profile=='CombinedDiagnostic' or ((r['logical_state'] in engine)==(profile=='EngineOnly'))]
        routes=[]
        for row in selected:
            name=row['track'];(folder/'haptics'/f'{name}.bnvib').write_bytes(assets[name])
            # Preserve the existing SE motorcycle speaker routing on matched tracks.
            routes.append(f'''[Route.{name}]
source = {row['bars']}
track = {name}
mode = spatial_drc
gain = 0x8000
haptic = {name}.bnvib
haptic_gain = 1.0
haptic_loop = {str(row['loop']).lower()}
''')
        (folder/'sound_routes.ini').write_text('\n'.join(routes),encoding='utf-8')
        (folder/'rules.txt').write_text(f'''[Definition]
titleIds = 00050000101C9300,00050000101C9400,00050000101C9500
name = Master Cycle Haptics - {profile} - PREVIEW
path = "The Legend of Zelda: Breath of the Wild/Mods/Controller/Master Cycle Haptics/{profile}"
description = "Validation preview. Enable only ONE Master Cycle profile. No automatic low/mid/high speed detection. Single-player haptic interruption applies; see README. Requires existing Enhanced Sound Experience."
version = 8
default = false
''',encoding='utf-8')
    (ROOT/'selected_audio_evidence.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
    (out/'mapping.csv').write_text('track,state,source,loop,seconds\n'+'\n'.join(f"{r['track']},{r['logical_state']},{r['bars']},{r['loop']},{r['seconds']}" for r in inventory)+'\n',encoding='utf-8')
    print(f'Built {len(assets)} audio-derived BNVIB assets in 3 mutually exclusive diagnostic profiles.')
    print('LOW/MID/HIGH speed split unavailable; combined looping behavior is NOT a completed solution.')

if __name__=='__main__':main()
