"""Preserve the existing Korean catalog and add the new NPU UI messages."""
import gettext,io,json,re,struct
from prepare import HERE,RC,ROLES,sha,write
MESSAGES={
 'NPU frame generation':'NPU 프레임 생성',
 'Starts off each session. Requires Vulkan and SDR output. When enabled, both original and generated frames use the selected processing resolution and are scaled to the window. Adds one frame of latency. Late generated frames are skipped.':'앱을 시작하면 꺼진 상태입니다. Vulkan과 SDR 출력이 필요합니다. 켜면 원본과 생성 프레임을 선택한 해상도로 처리한 뒤 창 크기에 맞춰 표시합니다. 한 프레임의 입력 지연이 추가되며, 늦게 도착한 생성 프레임은 건너뜁니다.',
 'NPU processing':'NPU 처리 해상도',
 '1080p / Standard':'1080p / 기본',
 '720p / Performance':'720p / 성능',
 'Applied on the next game start. 720p reduces GPU and NPU processing, with less image detail. Output follows the current window or fullscreen size.':'다음 게임 실행부터 적용됩니다. 720p는 GPU와 NPU 연산량을 줄이는 대신 화면의 세부 표현이 낮아질 수 있습니다. 출력 크기는 현재 창 또는 전체화면 크기를 따릅니다.',
 'Processing resolution changes apply on the next game start.':'처리 해상도 변경은 다음 게임 실행부터 적용됩니다.',
 'NPU FG initialization failed. Showing original frames; see log.txt.':'NPU 프레임 생성 초기화에 실패했습니다. 원본 프레임을 표시합니다. log.txt를 확인하세요.',
 'NPU FG unavailable: initialization failed. See log.txt. Showing original frames.':'초기화에 실패하여 NPU 프레임 생성을 사용할 수 없습니다. 원본 프레임을 표시합니다. log.txt를 확인하세요.',
 'NPU FG: current output format is unsupported. Showing original frames.':'NPU 프레임 생성이 현재 출력 형식을 지원하지 않습니다. 원본 프레임을 표시합니다.',
 'NPU FG stopped after an error. Showing original frames; see log.txt.':'오류로 NPU 프레임 생성이 중지되었습니다. 원본 프레임을 표시합니다. log.txt를 확인하세요.'}

def read_mo(data):
 magic=struct.unpack_from('<I',data)[0]
 order='<' if magic==0x950412de else '>'
 magic,revision,n,oi,ti,_,_=struct.unpack_from(order+'7I',data)
 assert magic==0x950412de and revision==0
 result={}
 for i in range(n):
  olen,offset=struct.unpack_from(order+'2I',data,oi+i*8);key=data[offset:offset+olen]
  tlen,offset=struct.unpack_from(order+'2I',data,ti+i*8);result[key]=data[offset:offset+tlen]
 return result
def make_mo(entries):
 pairs=sorted(entries.items());n=len(pairs);start=28+16*n
 ids=b'';strings=b'';ot=[];tt=[]
 for k,v in pairs:ot.append((len(k),start+len(ids)));ids+=k+b'\0'
 start+=len(ids)
 for k,v in pairs:tt.append((len(v),start+len(strings)));strings+=v+b'\0'
 return struct.pack('<7I',0x950412de,0,n,28,28+8*n,0,0)+b''.join(struct.pack('<2I',*x) for x in ot+tt)+ids+strings
def catalog(translated):
 header='Content-Type: text/plain; charset=UTF-8\nContent-Transfer-Encoding: 8bit\n'
 if translated:header+='Language: ko\nPlural-Forms: nplurals=1; plural=0;\n'
 result='# NPU frame generation UI. Original Cemu catalog is preserved when packaging.\nmsgid ""\nmsgstr '+json.dumps(header,ensure_ascii=False)+'\n\n'
 for original,value in MESSAGES.items():
  result+='msgid '+json.dumps(original,ensure_ascii=False)+'\nmsgstr '+json.dumps(value if translated else '',ensure_ascii=False)+'\n\n'
 return result
def main():
 base=RC/'runtime/resources/ko/cemu.mo';original=read_mo(base.read_bytes());entries=dict(original)
 assert b'charset=UTF-8' in original[b''] or b'charset=utf-8' in original[b'']
 for key,value in MESSAGES.items():
  assert key.encode() not in original
  entries[key.encode()]=value.encode()
 output=make_mo(entries);parsed=read_mo(output)
 assert all(parsed[k]==v for k,v in original.items())
 translator=gettext.GNUTranslations(io.BytesIO(output))
 for key,value in MESSAGES.items():assert translator.gettext(key)==value
 assert translator.gettext('missing NPU message')=='missing NPU message'
 path=HERE/'shared-runtime/resources/ko/cemu.mo';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(output)
 for role in ROLES:
  src=HERE/role/'source';assert (HERE/role/'evidence/integrated.json').exists()
  ui=(src/'src/gui/wxgui/GeneralSettings2.cpp').read_text(encoding='utf-8')
  path=src/'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanNPU.cpp';code=path.read_text(encoding='utf-8')
  count=0
  for key in MESSAGES:
   if 'LatteOverlay_pushNotification("'+key+'",' in code:
    code=code.replace('LatteOverlay_pushNotification("'+key+'",','LatteOverlay_pushNotification(_tr("'+key+'"),');count+=1
   else:assert '_("'+key+'")' in ui or '_tr("'+key+'")' in code,key
  assert count in [0,4]
  if count:write(path,code)
  write(src/'i18n/npu/npu.pot',catalog(False));write(src/'i18n/npu/ko.po',catalog(True))
  write(src/'i18n/npu/README.md','NPU messages use the existing Cemu `_()` / `_tr()` translation functions. Merge `ko.po` into the existing `cemu` catalog; preserve all existing messages. `npu.pot` is the template for other locales. Untranslated messages fall back to English. The local promotion packages include the merged Korean `resources/ko/cemu.mo`.\n')
 write(HERE/'evidence/localization.json',json.dumps({'locale':'ko','added_messages':len(MESSAGES),'existing_entries_preserved':len(original),'base_catalog_sha256':sha(base),'merged_catalog_sha256':sha(HERE/'shared-runtime/resources/ko/cemu.mo'),'gnu_gettext_lookup_verified':True,'other_languages':'existing translations retained; new messages fall back to English until translated','game_execution':False},indent=2)+'\n')
 print('Korean NPU catalog verified; messages='+str(len(MESSAGES))+', preserved='+str(len(original)))
if __name__=='__main__':main()
