"""Offline format, envelope, route, and local fingerprint checks. No Cemu build."""
from pathlib import Path
import struct,json,configparser,hashlib
from build_preview import ROOT,decode_dsp,SELECT

def main():
    # Known DSP frame: zero predictors, signed high nibble first, scale=2.
    raw=bytes([1,0x17,0x8f,0x20,0,0,0,0])
    assert decode_dsp(raw,[0]*16,6)==[2,14,-16,-2,4,0]
    rows=json.loads((ROOT/'selected_audio_evidence.json').read_text())
    byname={r['track']:r for r in rows}
    total=0
    for folder in (ROOT/'MasterCycleHapticsPreview').iterdir():
        if not folder.is_dir():continue
        ini=configparser.ConfigParser(interpolation=None)
        ini.read(folder/'sound_routes.ini')
        assert len(ini.sections())=={'EngineOnly':3,'ActionsOnly':5,'CombinedDiagnostic':8}[folder.name]
        for section in ini:
            if section=='DEFAULT':continue
            r=ini[section];name=r['track'];row=byname[name]
            assert r['source']==row['bars'] and r['mode']=='spatial_drc' and r['gain']=='0x8000'
            assert '*' not in name and '?' not in name
            p=folder/'haptics'/r['haptic'];d=p.read_bytes()
            assert hashlib.sha256(d).hexdigest()==row['haptic_sha256']
            meta,version,rate=struct.unpack_from('<IHH',d)
            assert meta in (4,12) and version==3 and rate==200
            sizepos=8 if meta==4 else 16
            size=struct.unpack_from('<I',d,sizepos)[0];payload=d[sizepos+4:]
            assert size==len(payload) and size>0 and size%4==0
            n=size//4;assert abs(n/rate-row['samples']/row['rate'])<=1/rate+1e-6
            assert r.getboolean('haptic_loop')==row['loop']==(meta==12)
            amps=list(payload[0::4])+list(payload[2::4])
            assert 0<max(amps)<=SELECT[name][1]<=90
            if meta==12:
                start,end=struct.unpack_from('<II',d,8)
                assert 0<=start<end==n
                assert payload[-4]==payload[4*start] and payload[-2]==payload[4*start+2]
            else:assert payload[-4]==payload[-2]==0
            total+=1
    assert total==16
    # Scope must not imply a made-up speed-state mapping.
    assert all(r['logical_state'] not in ('low_speed','mid_speed','high_speed') for r in rows)
    print('PASS: known DSP decode vector; 8 source-derived assets / 16 packaged copies')
    print('PASS: BNVIB v3 headers, exact sizes, loop bounds/seams, zero one-shot tail, amplitude caps')
    print('PASS: exact route names, source mapping, preserved spatial_drc, no invented speed mapping')
    print('NOT TESTED: actual Cemu load/detection, ride event semantics, controller feel, playback recovery')

if __name__=='__main__':main()
