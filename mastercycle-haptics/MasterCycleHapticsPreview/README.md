# Master Cycle Haptics — 사운드 매핑 시험판

**요청한 6상태 완성품이 아니다.** 현재 Test_SE의 기능으로 가능한 사운드 기반 진동을
시험하기 위한 pack이다. Cemu 본체/RPX/원본 게임 파일 변경, build, workflow 실행은 하지 않았다.

## 처음 시험할 항목

Cemu를 다시 실행하고 Graphic packs → Mods → Controller → Master Cycle Haptics에서
**EngineOnly 하나만** 켠다. 기존 Enhanced Sound Experience를 유지한다.
이 폴더 아래의 세 pack은 서로 배타적이다. 동시에 켜지 않는다.

| 항목 | 연결한 소리 | 목적 |
|---|---|---|
| EngineOnly | 아이들 / 주행 / 스로틀 오프, 3개 | 엔진 source detection 및 진동 강도 시험 |
| ActionsOnly | 점프 소리 3변형 / 브레이크 레버 / 브레이크 마찰, 5개 | 점프·브레이크 개별 반응 시험 |
| CombinedDiagnostic | 위 8개 | 덮어쓰기·엔진 복귀 문제를 관찰하는 진단용. 정상 주행 완성판으로 사용하지 않음 |

EngineOnly를 먼저 시험한 뒤 끄고 ActionsOnly로 바꿔 다시 실행한다.
진동이 너무 강하거나 멈추지 않으면 게임을 종료하고 pack을 끈다.
R2 Bow Adaptive Trigger pack 설정은 변경하지 않았다. 여기서는 일반 진동 출력만 사용한다.

## 요청한 상태와 현재 결과

| 요청 | 결과 |
|---|---|
| 아이들 | MotorcycleEngineIdling 실제 loop 확인, BNVIB 생성 |
| 저속 / 중속 / 고속 | 별도 엔진 speed track을 확인하지 못함. 현재는 MotorcycleEngine 주행 공통 루프 하나. 자동 3단계 미구현 |
| 점프 | Motorcycle_EngineJump00/01/02 단발 FWAV 확인. 실제 이륙과의 시간 대응은 실기 확인 필요 |
| 브레이크 | MotorcycleBrakeLever 단발 + Motorcycle_WheelFrictionCmnBrake 루프 확인. 실제 작동 조건은 실기 확인 필요 |

EngineAdd00/01/02는 0.5~0.6초 단발 변형이며 저/중/고속이라는 근거가 없다.
OffThrottle도 저속과 동의어가 아니므로 감속/스로틀 오프용으로만 표시했다.
노면 트랙의 Fast/Slow 표기를 차량 전체 속도 판정으로 확대하지 않았다.

## 실제 변환 방식

로컬 Wii U FWAV의 DSP-ADPCM을 오프라인 디코딩한다. 원본 음량 변화에서 200 Hz 간격의
저역/나머지 대역 RMS envelope를 만들고 완만하게 압축·평활화해 BNVIB low/high amplitude로 저장한다.
200 Hz는 강도 제어점의 갱신율이지 진동 주파수라는 의미가 아니다.
루프 시작은 FWAV의 loop_start를 시간 변환하고 경계의 강도 급변을 완화했다.
단발 끝은 0으로 감쇠한다. 최대 amplitude는 시험용으로 45~90/255 범위로 제한했다.
음원의 pitch를 실시간으로 추적하지 않는다. 클립별 보정이 들어가므로 원본 음량 비율을 그대로 재현하지도 않는다.
배포 파일에는 원본 FWAV/WAV/RPX가 없고 추출한 강도 envelope만 포함한다.

## 현재 바이너리의 필수 제한

기준 commit: 079d1351c3fd8425b35cd1b950aa18dfffb50c0a.

1. EnhancedSoundDualSenseService는 BNVIB의 low/high amplitude를 SetVibration에 전달한다.
   frequency 메타데이터는 읽지만 출력에 사용하지 않는다. PCM audio-haptics 직접 전송이 아니다.
2. s_hapticPlayer는 하나다. 새 PlayBnvib가 기존 클립을 교체한다. 믹싱/우선순위/중단된 loop 복귀 기능이 없다.
3. AX voice는 sampleBase/path/gain/loop가 그대로면 다시 PlayBnvib를 호출하지 않는다.
   따라서 점프·브레이크·SE UI 햅틱이 engine loop를 덮어쓰면, 엔진이 계속 울리는 동안 진동이 복귀하지 않을 수 있다.
4. EngineOnly도 엔진 레이어 중첩이나 다른 SE 햅틱의 영향에서 자유롭지 않다.
5. voice stop에서 해당 playback ID의 loop를 끄지만, 단발은 원래 클립 길이만큼 재생될 수 있다.
6. 소리가 나도 fingerprint 후보가 모호하거나 route가 다른 후보들과 일치하지 않으면 진동이 시작되지 않을 수 있다.

완성된 6상태 경험을 sound_routes.ini만으로 보장할 수 없다.
저/중/고속에는 검증된 별도 상태 신호가 필요하고, 연속 엔진+단발 효과의 안정적인 공존에는
이미 존재하는 다른 제어 경로를 추가로 입증하거나 런타임의 중첩/복귀 기능이 필요하다.
이번 작업에서는 바이너리 변경 금지 조건을 유지하며 이런 기능을 새로 추가하지 않았다.

## 오디오 경로와 설치

기존 SE의 오토바이 route가 spatial_drc/gain 0x8000인 것을 확인했다.
이 pack은 매칭하는 트랙에 같은 값을 포함해 햅틱 route가 기존 오디오 설정을 가리지 않도록 했다.
source와 track은 모두 정확한 이름을 사용한다. 원본 루프 플래그를 확인한 트랙에만 haptic_loop=true다.
최종 매칭은 활성 pack 순서 및 runtime source detection에 의존하므로 실제 로그/실기 확인이 필요하다.
기존 SE의 rules/sound_routes.ini나 활성화 설정은 수정하지 않는다.

## 실기 체크

- [ ] EngineOnly: 공회전 → 출발 → 주행 → 스로틀 오프의 진동 시작/전환.
- [ ] 엔진 정지·하차·오토바이 소멸·로드 후 잔류 진동 여부.
- [ ] EngineOnly: 메뉴/UI 햅틱 후 엔진 진동 복귀 여부.
- [ ] ActionsOnly: 점프 시점 / 브레이크 레버 / 브레이크 마찰 종료.
- [ ] CombinedDiagnostic: 점프·브레이크 후 engine loop가 복귀하는지. 실패를 속도 인식 실패와 구분.
- [ ] 주행 FPS/SE 음향/기존 Bow trigger에 영향 없는지.

독립 테스트 PASS는 파일 형식과 오프라인 변환을 검증한 것이며, 실기 PASS가 아니다.
