# DualSense Experience — UI + Sheikah + Master Cycle (TEST)

사용자가 제공한 `BOTW_DualSenseExperience_UI_Sheikah_v3.zip`의 **63개 route와 UI 햅틱 3개를 보존**하고 오토바이 route 8개/햅틱 8개를 추가한 통합팩입니다. 기존 UI gain, 무기·발소리·패러세일·듀얼센스 사운드 설정은 유지합니다. 총 71개 route / BNVIB 파일 11개입니다.

## 설치

1. [공통 voice 햅틱 기능](../../../docs/GENERIC_VOICE_HAPTICS.md)이 포함된 새 Test_SE 바이너리가 필요합니다. 기존 바이너리는 새 옵션을 무시합니다.
2. 이 폴더를 Cemu GraphicPacks 폴더 아래에 복사합니다.
3. Cemu의 Enhanced Sound Experience **전역 설정**은 켭니다. GraphicPack에서는 이 통합팩을 켭니다. 기본값은 비활성입니다.
4. 중복되는 기존 `Enhanced Sound Experience` **GraphicPack**, `UI + Sheikah v3`, `Master Cycle` EngineOnly/ActionsOnly/CombinedDiagnostic 팩은 끕니다. 별도 Bow Adaptive Trigger 팩은 이 통합팩에 포함되지 않습니다.
5. 타이틀을 다시 시작합니다. 이 작업은 사용자 Cemu 설치/활성화 설정을 자동 변경하지 않습니다.

## 동작과 범위

- 기존 UI/Sheikah 햅틱은 기존 gain을 유지합니다. UI에 거리 감쇠를 추가하지 않았습니다.
- 오토바이만 `haptic_follow_tv=true`로 게임의 TV 믹스와 voice envelope를 따릅니다. `spatial_drc`는 기존처럼 사운드 출력을 담당합니다.
- 오토바이: 아이들, 엔진, 스로틀 해제, 점프 3종, 브레이크 레버, 제동 마찰입니다. 저속/중속/고속의 정확한 상태 구분은 아직 없습니다. 스로틀 해제는 저속과 같지 않습니다.
- 정확한 오토바이 track 8개를 기존 source별 `track=*`보다 앞에 두었습니다. 나머지 오토바이/지형 사운드는 기존 wildcard route를 사용합니다.
- 공통 런타임은 동시에 재생되는 효과를 유지하며 채널별 최대 진폭으로 합성합니다. UI 효과 종료가 엔진 루프 자체를 삭제하지 않습니다. 강한 엔진이 약한 UI 효과를 가릴 수는 있습니다.
- 기존 UI 단발 효과는 AX 갱신을 기다리지 않고 즉시 시작하며 원래 패턴 길이대로 재생됩니다. 루프와 음량 추종을 켠 효과만 source voice 종료를 따릅니다.
- 오토바이 BNVIB는 기존 미리보기에서 생성한 진폭 패턴입니다. 원본 BARS/FWAV 오디오는 포함하지 않습니다. 현재 백엔드는 주파수 메타데이터를 오디오 햅틱으로 출력하지 않습니다.

## 검증 상태

자동 검증: 원본 63개 설정/순서, UI 파일 SHA-256 보존, 71개 route, 11개 유효 BNVIB, 정확한 오토바이 rule 우선순위를 확인합니다. `upstream-v3-provenance.json`에 입력 ZIP 해시와 원본 설정을 기록했습니다. `UPSTREAM_README_KO.txt`는 원본 설명 보존본이며 새 바이너리 요구 사항은 이 README가 기준입니다.

**새 바이너리 실기 검증은 아직 진행하지 않았습니다.** 아이들 거리/복귀, 물에 빠져 소멸, 브레이크/점프 후 엔진, UI·시커스톤 gain, 로드·일시정지·USB 재연결을 확인해야 합니다. 게임이 소멸한 물체의 AX 사운드를 비제로 음량으로 유지하면 이 팩만으로 물체 소멸을 판정할 수 없습니다.

## 무진동 회귀 수정

406ecf7 테스트에서 무진동이 보고되었습니다. 최초 통합 런타임의 UI 단발 효과 수명 변경과 첫 AX 갱신 전 샘플 소모를 수정했습니다. 새 수정 바이너리로 재검증해야 하며, 전체 무진동 원인을 확정한 것은 아닙니다. 기존 오토바이 미리보기 3종을 함께 켜면 통합팩을 덮어쓰므로 반드시 끄세요.
