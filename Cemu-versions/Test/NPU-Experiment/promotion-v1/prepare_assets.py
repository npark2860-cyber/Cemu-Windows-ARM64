"""Offline model and SPIR-V preparation. CPU provider only, single thread."""
from pathlib import Path
from copy import deepcopy
import hashlib, json, re, shutil, subprocess, sys
HERE=Path(__file__).resolve().parent
LAB=HERE.parent
sys.path[:0]=[str(LAB/'quant-tools'),str(LAB/'model-tools'),str(LAB/'scripts')]
import numpy as np
import onnx
import onnxruntime as ort
from onnx import numpy_helper
from prepare_int8_experiment import cpu_options
from prepare_resolution_models import set_dims, dims

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(path, content):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists(): assert path.read_bytes()==content, 'Preserve differing asset: '+str(path)
    else: path.write_bytes(content)

def resize(source,h,w,remove_pad):
    m=deepcopy(source)
    del m.graph.value_info[:]
    set_dims(m.graph.input[0],[1,h,w,6])
    # Do not trust the output annotation when checking the inferred result.
    m.graph.output[0].type.tensor_type.shape.ClearField('dim')
    for _ in range(4): m.graph.output[0].type.tensor_type.shape.dim.add()
    changed=[]
    for n in m.graph.node:
        if n.name in ['/Constant_22','/Constant_26']:
            val=h if n.name=='/Constant_22' else w
            n.attribute[0].t.CopyFrom(numpy_helper.from_array(np.array([val],np.int64)))
            changed.append(n.name)
    assert len(changed)==2
    pads=np.array([0,0,0,0,0,0,(-h)%16,(-w)%16],np.int64)
    for init in m.graph.initializer:
        if init.name=='/Cast_1_output_0': init.CopyFrom(numpy_helper.from_array(pads,init.name))
    if remove_pad:
        assert not pads.any(), 'Only a proven identity Pad may be bypassed'
        matches=[n for n in m.graph.node if n.op_type=='Pad']; assert len(matches)==1
        pad=matches[0]; assert pad.name=='/Pad'
        # Preserve the surrounding quantize/dequantize operations and scales.
        before,after=pad.input[0],pad.output[0]
        m.graph.node.remove(pad)
        for n in m.graph.node:
            for i,name in enumerate(n.input):
                if name==after: n.input[i]=before
    m=onnx.shape_inference.infer_shapes(m,strict_mode=True,data_prop=True)
    assert dims(m.graph.output[0])==[1,h,w,3]
    shapes={v.name:dims(v) for v in [*m.graph.input,*m.graph.value_info,*m.graph.output]}
    checked=0
    for n in m.graph.node:
        if n.op_type in ['Conv','ConvTranspose','Add']:
            assert all(isinstance(v,int) and v>0 for v in shapes[n.output[0]]), n.name
            if n.op_type=='Add': assert shapes[n.input[0]]==shapes[n.input[1]], n.name
            checked+=1
    assert checked==53
    original={i.name:i.SerializeToString() for i in source.graph.initializer}
    for init in m.graph.initializer:
        if init.name!='/Cast_1_output_0': assert init.SerializeToString()==original[init.name],init.name
    onnx.checker.check_model(m,full_check=True)
    return m

def main():
    src=LAB/'evidence/io-prep-20260929-072654-165595/anvil-1080p-u8nhwc.onnx'
    assert sha(src)=='8bf0fbfd3be38cf571da5b79a47a83259a9ade9441688fc5defb06bbda0ecd3c'
    original=onnx.load(src)
    small=resize(original,720,1280,True)
    save(HERE/'assets/npu/1080p/anvil-u8nhwc.onnx',src.read_bytes())
    save(HERE/'assets/npu/720p/anvil-u8nhwc.onnx',small.SerializeToString())
    # Exercise the exact QDQ identity-pad transformation on a small zero-pad
    # proxy. This validates removal, not full-resolution game image quality.
    sessions=[ort.InferenceSession(resize(original,32,48,remove).SerializeToString(),cpu_options(),providers=['CPUExecutionProvider']) for remove in [False,True]]
    assert all(s.get_providers()==['CPUExecutionProvider'] for s in sessions)
    rng=np.random.default_rng(20260929)
    checks=[]
    for x in [np.zeros((1,32,48,6),np.uint8),np.full((1,32,48,6),255,np.uint8),rng.integers(0,256,(1,32,48,6),dtype=np.uint8)]:
        outputs=[s.run(None,{'input':x})[0] for s in sessions]
        assert np.array_equal(*outputs), 'Zero-pad removal changed quantized output'
        checks.append({'bitwise_equal':True,'output_shape':list(outputs[0].shape)})
    mappings={1920:1280,1080:720,480:320,270:180,120:80,68:45,119:79,67:44,1036800:460800,518400:230400,2073600:921600}
    assets=[]
    compiler=LAB/'tools/glslang-16.6.0/bin/glslang.exe'
    for profile in ['1080p','720p']:
        for kind in ['generate','pack','compose','downsample','flow']:
            source=LAB/'shaders'/('motion1080-'+kind+'.comp')
            if kind=='flow': source=LAB/'flow-cache-v4/motion1080-flow-cached.comp'
            text=source.read_text()
            if profile=='720p':
                # Match integer tokens only. Never normalize decimal fragments:
                # e.g. int("03") would silently turn a 0.03 threshold into 0.3.
                text=re.sub(r'(?<![\w.])(\d+)(u?)(?![\w.])',
                    lambda m:str(mappings[int(m[1])])+m[2] if int(m[1]) in mappings else m[0],text)
                decimals=r'(?<![\w.])\d+\.\d+(?:[eE][+-]?\d+)?'
                assert re.findall(decimals,text)==re.findall(decimals,source.read_text()), 'Floating-point constants changed: '+kind
            path=HERE/'shader-sources'/profile/('motion1080-'+kind+'.comp')
            save(path,text.encode())
            out=HERE/'assets/npu'/profile/'shaders'/('motion1080-'+kind+'.spv')
            out.parent.mkdir(parents=True,exist_ok=True)
            if out.exists(): raise ValueError('Preserve existing compiled assets')
            subprocess.run([str(compiler),'-V','--target-env','vulkan1.1',str(path),'-o',str(out)],check=True,capture_output=True)
            if profile=='1080p':
                baseline=LAB.parent/'NPU-Release-v4/runtime/shaders'/out.name
                assert sha(out)==sha(baseline), '1080p shader changed: '+kind
            assets.append({'path':str(out.relative_to(HERE)), 'sha256':sha(out)})
    report={'status':'CPU_MODEL_AND_SHADER_CHECKS_PASSED_NOT_DEVICE_TESTED','original_model_sha256':sha(src),
            '720p_model_sha256':sha(HERE/'assets/npu/720p/anvil-u8nhwc.onnx'),
            'weights_and_quantizers_unchanged':True,'720p_zero_pad_removed':True,
            'network_shapes_verified':53,'cpu_proxy_checks':checks,'1080p_model_and_shaders_byte_identical_to_v4':True,
            'assets':assets,'gpu_npu_executed':False,'720p_full_resolution_inference_executed':False,'720p_game_quality_validated':False}
    (HERE/'asset-checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
