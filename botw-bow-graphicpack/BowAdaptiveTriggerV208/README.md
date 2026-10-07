# BOTW Bow Adaptive Trigger v208 — RC1

Bow ID별 장력, instance별 상태, 게임 release 이벤트에 따른 sequence 재발행을 구현한 GraphicPack이다.
Cemu 본체 변경/빌드가 필요 없다. 대상은 Wii U BOTW v208, module checksum **6267BFD0**다.

## 설치와 실행

1. 이 폴더를 Cemu graphicPacks 아래에 넣고 Cemu를 다시 실행한다.
2. Constant Raw Validation, Sequence re-arm validation 등 다른 R2 raw-trigger pack을 **모두 끈다**.
3. `BOTW Bow Adaptive Trigger v208 - event driven RC1`만 켠다. 기존 PASS한 SE와 DualSense 연결 설정을 유지한다.
4. 세이브를 로드한다. 정상 적용 로그는 `Applying patch group 'BotwBowAdaptiveTriggerV208'`다.
5. 활을 바꿔 장력이 달라지는지, 같은 활로 반복 발사한 뒤 다시 R2 장력이 생기는지 확인한다.

패치 이름은 **patch_bow.asm**이다. patches.txt로 바꾸면 구형 파서가 선택되어 작동하지 않는다.
이 pack은 120회 주기나 10회 제한 없이 게임 이벤트로 동작한다. R2 입력을 polling하지 않는다.
이상 동작이 있으면 이 pack을 끄고 Cemu를 재시작한다. 게임 저장 데이터는 수정하지 않는다.

## 구현 내용

- entry는 off/초기화만 수행한다. pouch load가 끝난 후, 실제 Player callback에서 유효한 bow handle이 확인되어야 arm한다.
- 실제 Player bow slot을 사용한다. pouch equipped array가 로드 중 비워지는 문제에 의존하지 않는다.
- `(player pointer, player proc ID, load epoch)`와 `(bow pointer, bow proc ID, equipment epoch)`를 분리한다.
- 같은 instance에서는 이름 해석과 DB 조회를 하지 않는다. 다른 instance라도 Bow ID가 같으면 cached raw를 재사용한다.
- 원본 release 계열 세 경로가 끝날 때 현재 bow actor에 해당하는 이벤트만 수집한다. 다음 Player callback에서 동일 cached raw에 새 sequence를 붙인다.
- 같은 callback 사이에 모인 release들은 한 번의 재발행으로 합친다. projectile 개수에 따라 장력을 반복 변경하지 않는다.
- 내구도 양수 감소는 발사로 취급하지 않는다. actor→pouch sync의 값이 0 이하일 때는 파손/off가 우선한다.
- bow detach, bow/player 삭제 요청, pouch load 진입에서는 off 및 baseline 무효화한다.
- unknown Bow ID, 잘못된 handle generation, 비활성/삭제 actor는 off다. 짧은 off pulse에 의존하지 않는다.

## 장력 DB

동봉 bow_db.csv의 normalized tension 26개는 원본 입력을 보존한다. 화살 공격력/종류/수량은 장력 입력이 아니다.

`q = clamp(1 + floor((7*T + 50)/100), 1, 8)`

`raw16 = (((q-1) | ((q-1)<<3))<<8) | 0x04`

이는 GraphicPack의 변환 정책이며 BOTW 원본 공식이나 물리적 선형 장력 모델이 아니다.
8단계 양자화 때문에 서로 다른 normalized 값이 같은 raw 장력을 가질 수 있다.
예: 001→1B04, 002→2404, 033→3604. 기존 최대 장력 테스트의 3F04보다 낮을 수 있다.
CSV의 proposed/calibration 열은 체감 보정 미완료를 의미한다. runtime 표는 CSV에서 생성한다.

## 검증 범위

**실기 PASS:** 기존 sequence 검증 pack의 로드와 동일 raw 값 sequence-only re-arm. 사용자 확인 2026-09-20.

**RC1 독립 테스트 PASS:** 원본 hook word/CRC, 생성 PPC 실행, 모든 GPR/LR/CR/CTR/XER 보존,
초기 로드, 26개 DB, 같은 ID 다른 instance, 포인터 재사용, 내구도 감소 비발사 처리,
arrow 제외, release 묶기, 파손 우선, 해제/삭제/로드 off, sequence wrap.

**RC1 실기 미검증:** 새 세 release 경로와 실제 발사의 대응 및 전체 특수 활/멀티샷 커버리지,
로드 화면 시작부터 off까지의 정확한 시점, 사용자 모드 조합, multicore 동시 실행, 장력 체감 보정.
따라서 기존 sequence PASS를 새 pack의 전체 게임플레이 PASS로 확대 해석하지 않는다.
아래 CHECKLIST.md를 마치기 전에는 실기 최종 승인 버전으로 표시하지 않는다.

## 한계

- 세계 전환 전체를 감지하는 검증된 공통 시작점은 아직 없다. off는 pouch load 진입/actor 삭제 요청/장비 해제에서 수행한다.
  전환 화면이 그보다 먼저 시작하면 기존 장력이 잠시 남을 수 있다. 임의 frame 주소나 타이머로 이를 숨기지 않았다.
- 특수 발사, 실패한 projectile 생성, 다른 모드가 release 함수 자체를 건너뛰는 경우의 동작은 확인 대상이다.
- 읽기 전용 handle snapshot은 generation을 재확인하지만 BOTW 객체 수명의 잠금을 새로 획득하지 않는다.
  GraphicPack 전용 lock은 private state만 직렬화하며 게임 객체의 수명을 보장하는 lock이 아니다.
- bridge는 마지막 command를 샘플링하므로 한 화면 갱신 사이의 여러 명령은 합쳐질 수 있다. 전송 ACK는 없다.

원본 명령/caller/ABI는 HOOKS.md, 상태 및 진단 변수는 STATE_MACHINE.md를 참조한다.
