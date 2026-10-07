"""Independent CPU ground truth for translation/cut fixtures, plus GPU consumption checks."""
import hashlib
import numpy as np

SHIFTS=((0,0),(8,4),(-12,8),(0,0))
def require(ok,message):
    if not ok: raise ValueError(message)
def sha(data): return hashlib.sha256(data).hexdigest()

def scene(x,y,seed):
    bx=(x//4).astype(np.uint32); by=(y//4).astype(np.uint32)
    h=bx*np.uint32(1664525)+by*np.uint32(1013904223)+np.uint32((seed*2246822519)&0xffffffff)
    h^=h>>np.uint32(16); h*=np.uint32(2246822519); h^=h>>np.uint32(13)
    return np.stack((h&255,(h>>8)&255,(h>>16)&255),axis=-1).astype(np.uint8)

def expected_aligned(flow,phase,width,height):
    gx=(width+15)//16; gy=(height+15)//16
    y,x=np.indices((height,width),dtype=np.int32); x=x.ravel(); y=y.ravel()
    f=flow[0,y//16,x//16]; qx=x+f[:,0]; qy=y+f[:,1]
    r=flow[1,np.clip(qy//16,0,gy-1),np.clip(qx//16,0,gx-1)]
    valid=(qx>=0)&(qy>=0)&(qx<width)&(qy<height)&(f[:,2]==1)&(r[:,2]==1)&np.all(f[:,:2]+r[:,:2]==0,axis=1)
    ax=x-f[:,0]//2; ay=y-f[:,1]//2; bx=x+f[:,0]//2; by=y+f[:,1]//2
    valid&=(ax>=0)&(ay>=0)&(bx>=0)&(by>=0)&(ax<width)&(ay<height)&(bx<width)&(by<height)
    dx,dy=SHIFTS[phase]; seed=97 if phase==3 else 11
    current=scene(x-dx,y-dy,seed)
    a=np.where(valid[:,None],scene(ax,ay,11),current)
    b=np.where(valid[:,None],scene(bx-dx,by-dy,seed),current)
    return np.concatenate((a,b),axis=1),valid

def verify_motion_bytes(data,reference,phase,scale=0.00330072408542037,width=1920,height=1080):
    require(phase in range(4),'Unexpected phase')
    p=width*height; gx=(width+15)//16; gy=(height+15)//16; flow_bytes=gx*gy*16
    require(len(data)==p*17+flow_bytes*2,'Unexpected diagnostic length')
    require(len(reference)==p*3,'Unexpected reference size')
    raw=np.frombuffer(data,dtype=np.uint8)
    inputs=raw[:p*6].reshape(p,6); output=raw[p*6:p*9].reshape(p,3)
    composed=raw[p*9:p*13].reshape(p,4); warped=raw[p*13:p*17].reshape(p,4)
    flow=np.frombuffer(data,offset=p*17,dtype='<i4').reshape(2,gy,gx,4)
    require(np.all(np.abs(flow[:,:,:,:2])<=16) and np.all(flow[:,:,:,:2]%4==0),'Invalid motion range/grid')
    require(np.all((flow[:,:,:,2]==0)|(flow[:,:,:,2]==1)) and np.all(flow[:,:,:,3]>=0),'Invalid motion confidence/cost')
    core=flow[:,2:-2,2:-2]
    require(core.size>0,'Fixture too small for an interior motion oracle')
    if phase==3:
        motion_fraction=float(np.mean(core[:,:,:,2]==0))
        require(motion_fraction>=0.995,'Scene cut was not rejected')
    else:
        dx,dy=SHIFTS[phase]
        expected=np.array([[dx,dy],[-dx,-dy]],dtype=np.int32)[:,None,None,:]
        motion_fraction=float(np.mean(np.all(core[:,:,:,:2]==expected,axis=3)&(core[:,:,:,2]==1)))
        require(motion_fraction>=0.995,'Known translation motion mismatch')
    expected,valid=expected_aligned(flow,phase,width,height)
    require(np.array_equal(inputs,expected),'Midpoint warp/NHWC input differs from independent scene oracle')
    require(np.array_equal(warped[:,:3],inputs[:,:3]) and np.array_equal(warped[:,3],valid.astype(np.uint8)*255),'Warp/mask image mismatch')
    require(output.tobytes()==reference,'Shared NPU output differs from ordinary-memory reference')
    mean=(expected[:,:3].astype(float)+expected[:,3:].astype(float))/2
    delta=(output.astype(float)-128)*scale*255*valid[:,None]
    oracle=np.floor(np.clip(mean+delta,0,255)+0.5).astype(np.int16)
    error=np.abs(composed[:,:3].astype(np.int16)-oracle)
    require(int(error.max())<=1 and np.all(composed[:,3]==255),'GPU residual compose mismatch')
    # A cut must preserve the current frame exactly, rather than blending the scenes.
    if phase==3: require(np.array_equal(composed[:,:3],expected[:,3:]),'Scene-cut output changed the current frame')
    return {'phase':phase,'known_motion_or_cut_match_fraction':motion_fraction,'valid_warp_fraction':float(valid.mean()),
            'input_sha256':sha(inputs.tobytes()),'output_sha256':sha(reference),'composed_sha256':sha(composed.tobytes()),
            'diagnostic_sha256':sha(data),'max_compose_error':int(error.max())}
