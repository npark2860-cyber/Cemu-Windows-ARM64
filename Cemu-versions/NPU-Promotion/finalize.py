"""Publish the local index only after all four packages have passed verification."""
from datetime import datetime,timezone
import json
from prepare import HERE,VERSIONS,ROLES,sha,write

rows=[];entries=[]
for role in ROLES:
    root=HERE/role
    manifest=json.loads((root/'NPU-BUILD.json').read_text(encoding='utf-8'))
    assert manifest['status']=='LOCAL_BUILD_AND_PACKAGE_VERIFIED'
    graph=(root/'build/build.ninja').read_text(encoding='utf-8')
    assert '-DEMULATOR_HASH='+ROLES[role][0][:7] in graph
    assert sha(root/'source/bin/Cemu_release.exe')==manifest['cemu_sha256']
    for f in manifest['files']:assert sha(root/f['path'])==f['sha256']
    entries.append({'role':role,'base_commit':manifest['base_commit'],
        'manifest':role+'/NPU-BUILD.json','manifest_sha256':sha(root/'NPU-BUILD.json'),
        'source':role+'/source','executable':role+'/'+manifest['executable'],
        'cemu_sha256':manifest['cemu_sha256'],'game_tested':False})
    rows.append('| '+role+' | `'+manifest['base_commit'][:12]+'` | [실행 파일]('+role+'/'+manifest['executable']+') | [소스]('+role+'/source/) |')
index={'created_at':datetime.now(timezone.utc).isoformat(),'status':'FOUR_LOCAL_NPU_PACKAGES_VERIFIED',
       'user_accepted_RC1':True,'four_new_binaries_game_tested':False,
       'agent_executed_gpu_npu_cemu':False,'installed_emulator_replaced':False,
       'remote_pushed':False,'variants':entries,
       'provenance':'User-accepted NPU RC1; unchanged ABI2 module, models, shaders and QNN runtime; role-specific Cemu rebuilds and Korean UI additions.',
       'shared_module_source_inventory_sha256':sha(HERE/'evidence/shared-module-source.json'),
       'localization_evidence_sha256':sha(HERE/'evidence/localization.json')}
write(HERE/'NPU-PROMOTION.json',json.dumps(index,ensure_ascii=False,indent=2)+'\n')
readme='''# Cemu ARM64 — NPU 기능 정식 통합본

2026-09-29. 사용자가 NPU RC1의 게임 테스트를 마친 뒤 보고한 성공을 기준으로, 네 버전에 NPU 전용 기능을 통합했다. 각 버전의 Windows ARM64 빌드와 파일 검증이 완료됐다. **새로 빌드한 네 실행 파일 자체의 게임 테스트는 아직 하지 않았다.** 원본 기준 소스·배포물과 RC1은 보존했다.

| 버전 | 기준 커밋 | 실행 파일 | 소스 |
|---|---|---|---|
'''+ '\n'.join(rows)+'''

EXE만 따로 옮기지 말고 각 `runtime` 폴더 전체를 사용한다. 창 제목에 버전과 `NPU`가 표시된다. Release+SE는 사용자가 최종이라고 지정한 SE_Test/PR #5의 `9c0b899` 기능 코드를 기준으로 한다. Diagnostics는 ARM64 진단 UI를 유지한다. Diagnostics+SE는 별도로 확정한 Cue Capture V2 기준을 유지하며, Release+SE의 최신 일반 햅틱 기능과 동일한 소스라는 뜻은 아니다. SE 정책/햅틱 자료는 각 소스의 `enhanced_sound_policies`와 기존 버전의 배포물에 보존돼 있다.

## 사용

일반 설정의 그래픽 탭에서 **NPU 프레임 생성**을 켠다. 세션 시작 시 기본 OFF이며, OFF는 원본 표시다. Vulkan/SDR 출력이 필요하다. NPU 모듈과 자원은 미리 준비하고, ON 전환 시 이력을 초기화한다. 늦은 생성 프레임은 건너뛴다. 표시 FPS는 실제로 제출한 원본과 생성 프레임을 합산하므로 항상 고정 2배는 아니다.

- **1080p / 기본**, **720p / 성능** 중 선택한다. 해상도 변경은 다음 게임 실행부터 적용된다.
- 초기 코드 기본값은 1080p다. 이 로컬 패키지의 설정은 사용자가 마지막으로 테스트한 RC1의 720p 선택을 복사했다.
- ON 동안 원본·생성 이미지 모두 선택한 처리 해상도를 거쳐 현재 창/전체화면 크기로 출력된다. 기존 LSFG의 75% 설정과 다른 선택지다.
- 기존 GPU LSFG 기능은 포함하지 않는다. `Lossless.dll`은 필요 없다.
- 일반 설정의 언어 선택을 따른다. 기존 한국어 823개 항목을 보존하고 NPU 메뉴·설명·알림 11개를 추가했다. 다른 언어의 기존 번역은 보존했고 새 NPU 문구는 아직 영어로 표시된다. 번역 원본은 각 소스의 `i18n/npu`다.

각 runtime의 portable 설정·컨트롤러·그래픽 팩·셰이더 캐시는 독립 복사본이다. MLC 경로는 기존 저장 데이터 경로를 가리킨다. 저장 데이터를 복사하거나 수정하지 않았다. 이 폴더는 기존 실험 폴더의 MLC와 드라이버 저장소를 참조하므로, 다른 PC로 옮길 때에는 그 경로와 QNN 환경을 다시 설정해야 한다.

## 검증 범위

`verify-packages.ps1`는 실행 파일·DLL·모델·셰이더·언어 파일과 변경 소스의 SHA-256, 준비 당시 드라이버를 확인한다. Cemu나 GPU/NPU 검증 도구를 실행하지 않는다. 사용 후 바뀌는 portable 설정·캐시는 고정 파일 검증에서 제외한다.

모든 실행 파일은 ARM64이고, 각 기준 커밋·버전별 창 제목·NPU 빌드 옵션을 확인했다. 릴리즈 두 종류는 진단 코드 제외를 확인했다. 진단 버전은 소스·오브젝트·라이브러리·EXE의 진단 UI 마커를 확인했고, 진단+SE는 V2 CSV 기록 코드와 스키마를 확인했다. NPU 모듈·두 해상도 모델·SPIR-V·ORT/QNN 라이브러리는 사용자가 통과시킨 RC1과 바이트가 같다. RC1의 기존 CPU 검사 536개 결과는 그대로 적용되는 변경 없는 모듈/계약의 과거 검증 기록이다.

`evidence/user-acceptance.json`과 게임 로그에는 사용자 RC1 확인 기록이 있다. 마지막 720p 로그의 1440p 출력 안정 구간은 원본 약 35.0FPS, 생성 약 34.6FPS, accepted present 약 69.6FPS였다. 이는 동일 장면 A/B 성능 측정이나 실제 디스플레이 scanout 검증을 뜻하지 않는다.

## 소스와 재현 기록

각 `source`는 해당 기준 커밋 및 재귀 서브모듈을 복사한 별도 Git 저장소다. 기준 소스를 덮어쓰지 않고 `codex/npu-*` 브랜치에 CI 전처리·NPU 공통 변경·버전 제목·번역 변경을 적용했다. 아직 원격에 push하지 않았다. 변경 파일 목록/해시와 추적 파일 패치는 `evidence/source-files.json`, `evidence/source.patch`에 있고 새 파일도 source에 보존돼 있다.

`build.ps1 -Variant <버전> -Pass <새 이름>`으로 기존 로그를 보존하면서 다시 빌드한다. Q:가 다른 작업에 사용 중이면 중단한다. Release는 같은 Q: 경로와 도구 체인을 사용한 RC1 빌드 캐시를 재사용하되 동일 바이트의 입력만 기존 시각을 유지했다. 나머지는 각각 별도 빌드 디렉터리에서 시작했다. `shared-module-source`는 RC1 모듈·셰이더 소스 원본 복사본이며, 그 안의 과거 빌드 스크립트는 원래 실험 폴더의 상대 경로를 그대로 기록한다.

`NPU-PROMOTION.json`이 네 패키지의 색인이고 각 폴더의 `NPU-BUILD.json`이 고정 파일 manifest다. 원래 네 기준 버전의 정체성은 상위 `catalog.json`과 `Verify-Versions.ps1`로 별도 확인한다.
'''
write(HERE/'README.md',readme)
catalog_readme=VERSIONS/'README.md';text=catalog_readme.read_text(encoding='utf-8')
notice='**NPU 통합본:** 사용자 RC1 검증 후 만든 네 버전의 소스·실행 파일은 [NPU-Promotion](NPU-Promotion/README.md)에 있다. 아래 목록은 보존한 기존 기준 배포물이며, 새 NPU 빌드의 색인은 `NPU-Promotion/NPU-PROMOTION.json`이다.\n\n'
if notice not in text:write(catalog_readme,text.replace('\n\n','\n\n'+notice,1))
experiment=VERSIONS/'Test/NPU-Experiment/README.md';text=experiment.read_text(encoding='utf-8')
notice='## 후속 상태 — 사용자 RC1 통과 및 네 버전 통합\n\n사용자가 “테스트 다 해봤고 아주 잘 된 것 같아”라고 보고했다. RC1의 마지막 720p 게임 로그와 확인 기록을 `../../NPU-Promotion/evidence`에 보존했다. 네 버전의 로컬 NPU 통합 빌드와 파일 검증은 완료됐으며 [실행 파일·소스 목록](../../NPU-Promotion/README.md)에 정리했다. 새 네 실행 파일 자체의 게임 실행은 하지 않았다. 아래 RC1 준비 단계의 “미검증” 표시는 당시 기록이다.\n\n'
if notice not in text:write(experiment,text.replace('\n\n','\n\n'+notice,1))
print('Four local NPU packages indexed; historical baselines and RC1 preserved.')
