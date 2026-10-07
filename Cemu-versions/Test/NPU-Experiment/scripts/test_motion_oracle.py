import json
import numpy as np
from motion_oracle import SHIFTS,expected_aligned,verify_motion_bytes

passed=[]
def reject(name,action):
    try: action()
    except ValueError: passed.append(name)
    else: raise AssertionError('Accepted bad fixture: '+name)

w=h=96; p=w*h; fixtures=[]
for phase in range(4):
    flow=np.zeros((2,6,6,4),dtype='<i4'); dx,dy=SHIFTS[phase]
    flow[0,:,:,:2]=(dx,dy); flow[1,:,:,:2]=(-dx,-dy); flow[:,:,:,2]=phase!=3
    inputs,valid=expected_aligned(flow,phase,w,h)
    reference=np.full((p,3),128,dtype=np.uint8)
    mean=np.floor((inputs[:,:3].astype(float)+inputs[:,3:].astype(float))/2+0.5).astype(np.uint8)
    rgba=np.column_stack((mean,np.full(p,255,dtype=np.uint8)))
    warp=np.column_stack((inputs[:,:3],valid.astype(np.uint8)*255))
    raw=inputs.tobytes()+reference.tobytes()+rgba.tobytes()+warp.tobytes()+flow.tobytes()
    fixtures.append((raw,reference.tobytes()))
    assert verify_motion_bytes(raw,reference.tobytes(),phase,width=w,height=h)['known_motion_or_cut_match_fraction']==1
    passed.append('accept_'+['static','forward_translation','reverse_translation','scene_cut'][phase])
raw,ref=fixtures[1]
bad=bytearray(raw); bad[123]^=1
reject('reject_corrupt_aligned_input',lambda:verify_motion_bytes(bad,ref,1,width=w,height=h))
reject('reject_wrong_motion_direction',lambda:verify_motion_bytes(raw,ref,2,width=w,height=h))
bad=bytearray(raw); bad[p*6+9]^=1
reject('reject_stale_npu_output',lambda:verify_motion_bytes(bad,ref,1,width=w,height=h))
bad=bytearray(raw); bad[p*9+100]=0
reject('reject_bad_composed_pixel',lambda:verify_motion_bytes(bad,ref,1,width=w,height=h))
bad=bytearray(raw); bad[p*13+3]^=255
reject('reject_wrong_fallback_mask',lambda:verify_motion_bytes(bad,ref,1,width=w,height=h))
raw,ref=fixtures[3]; bad=bytearray(raw); bad[p*9+100]^=8
reject('reject_cut_frame_modification',lambda:verify_motion_bytes(bad,ref,3,width=w,height=h))
reject('reject_truncated_flow',lambda:verify_motion_bytes(raw[:-4],ref,3,width=w,height=h))
print(json.dumps({'status':'OFFLINE_MOTION_ORACLE_TESTS_PASSED','count':len(passed),'tests':passed,'device_executed':False},indent=2))
