# 실기 검증 체크리스트

업데이트: 아래 sequence-only 단계는 사용자 실기 PASS로 완료했다. 다음 검증은 `BowAdaptiveTriggerV208/CHECKLIST.md`의 RC1 게임플레이 항목이다. 구 validation pack은 RC1과 동시에 켜지 않는다.

## 지금 실행할 단계: sequence-only re-arm

상수 `0x00013F04`가 강한 장력을 출력한다는 PASS는 이미 인정한다. 아래는 그 시험의 반복이 아니라 같은 장력이 재발행될 때 snap 이후 다시 동작하는지 확인하는 시험이다.

1. `SequenceRearmValidation` 폴더만 Cemu의 `graphicPacks` 아래에 복사한다. 패치 파일명은 반드시 `patch_bow_sequence.asm`이다. `patches.txt`는 구형 파서를 선택하므로 사용할 수 없다.
2. 기존 다른 R2 `.adaptiveTriggerRaw` pack은 끄고 이 validation pack 하나만 켠다. SE와 USB 연결은 기존 PASS 설정을 유지한다.
3. 게임을 시작하고 세이브를 로드한다. Cemu log에서 BOTW module checksum `0x6267BFD0`, `Applying patch group 'BotwBowSequenceProbeV208'` 및 pack 문법/적용 오류가 없는지 확인한다. Activate graphic pack만으로 패치 적용 성공을 판단하지 않는다.
4. 조작 가능한 곳에서 R2를 당겨 snap을 지난 뒤, 유지한 경우와 충분히 놓았다가 다시 당기는 경우를 구분해 관찰한다. 실제 발사 후 다음 화살에서도 장력이 다시 생기는지 기록한다.
5. 이 pack은 **발사와 무관하게** 120 Player callback마다 상위 sequence만 바꾼다. 하위 16비트는 항상 0x3F04이며 중간 off pulse는 없다. callback이 매 frame 한 번이면 60fps 약 2초/30fps 약 4초지만, 해당 빈도 자체는 아직 확인 대상이다. 고정된 실시간 주기로 간주하지 않는다.
6. 총 10회 발행한 뒤 callback 1201에서 off가 된다. 이 마지막 off는 시험 종료 신호이며 re-arm 메커니즘이 아니다. 중간에 메뉴/일시정지로 callback이 멈추면 종료까지의 실제 시간이 늘어날 수 있다.
7. 결과를 `재-arm 성공 / 최초 장력만 있음 / 출력 없음 / pack 로드 오류`로 기록하고, R2를 유지했는지 놓았다가 다시 당겼는지도 기록한다. 실패 시 처음부터 bridge 전체가 실패했다고 단정하지 않는다.

시험 중 강한 고정 장력은 의도된 검증값이다. 강도가 바뀌는 26종 Bow DB는 아직 연결되지 않았다. 테스트 종료 후 validation pack을 끈다. Cemu에서 실제 코드가 실행됐는지 불명확하면 아래 telemetry를 확인하는 것이 먼저다.

## GraphicPack private telemetry

`BowProbeState` 심볼 기준의 big-endian u32 값이다. 실제 codecave 주소는 pack 로딩에 따라 달라지므로 임의 고정 주소를 사용하지 않는다. 디버거에서 로드된 patch의 `BowProbeState` 실제 주소를 확인할 수 있을 때 읽는다. 값을 변경할 필요는 없다.

| offset | 의미 |
|---|---|
| +00 | 마지막 command: 00013F04, 00023F04, ..., 000A3F04, 종료 시 0 |
| +04 | probe 중 Player callback 횟수; 종료 시 1201 |
| +08 | sequence, load 때도 유지 |
| +0C | 발행 누적 횟수 |
| +10 | 다음 발행까지 남은 callback 수 |
| +14 | pouch load 실행 중 flag |
| +18 | 종료 latch |
| +1C | rebuild 완료 hook 횟수 |
| +20 | type=Bow인 value store 횟수; 발사 횟수가 아님 |
| +24 | 마지막 bow PouchItem 주소 |
| +28 / +2C | 마지막 bow value의 old/new |
| +30 | pouch load 진입 횟수 |
| +34 | 마지막 manager |
| +38 | 마지막 value store의 PouchItemType |

## 다음 단계: event/instance 검증

- [ ] 새 실행 + 이미 활을 장착한 세이브: 메뉴를 열지 않아도 최초 인식.
- [ ] 같은 프로세스에서 세이브 재로드: off와 epoch 변경, 이전 포인터 무효화.
- [ ] 타이틀/로딩 전환 시작 즉시 off: pouch load 진입보다 빠른 전환 event가 필요한지 확인.
- [ ] 일반 메뉴와 퀵 메뉴의 활 교체 모두 감지.
- [ ] 같은 Bow ID의 다른 instance로 교체: 장력 DB cache hit, value baseline reset, SHOT 증가 없음.
- [ ] 취소한 조준, 화살 종류 변경, 화살 획득/드롭은 SHOT 아님.
- [ ] 실제 발사와 value sync/arrow consumption/ready event의 순서를 대조.
- [ ] multi-shot은 projectile 개수만큼 재발행하지 않음.
- [ ] 소비/내구도 변경이 없는 특수 상황과 Infinite Arrows/Durability pack의 영향 확인.
- [ ] 마지막 내구도 발사 후 파손은 off 우선, pending re-arm 취소.
- [ ] 활 해제는 off, 다시 장착하면 새 instance baseline.
- [ ] FPS++ 사용/미사용, 30/60fps에서 같은 동작.
- [ ] BNVIB, SE route, 다른 컨트롤러 효과와 충돌 없음.
- [ ] 26개 DB의 원본 normalized 값 보존 및 체감 강도 보정.

동적 제품 단계는 위 결과가 확보되기 전에 완료로 표시하지 않는다.
