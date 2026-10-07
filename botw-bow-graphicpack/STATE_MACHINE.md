# 최종 Bow-aware pack 설계와 현재 검증 pack의 차이

업데이트: sequence 검증은 사용자 실기 PASS. 이 문서는 당시 설계 이력이다. 구현된 RC1 상태 머신은 `BowAdaptiveTriggerV208/STATE_MACHINE.md` 및 한계는 같은 폴더 README.md가 기준이다.

## 최종 설계 — 아직 구현 완료 아님

상태: WAIT_WORLD, NO_BOW, TRACKING, WAIT_READY, INVALIDATED.

- entry는 command=0과 private state 초기화만 한다. load-complete 신호가 아니다.
- pouch/world 전환 시작은 command=0, loadEpoch 증가, instance/value baseline 무효화로 처리한다.
- world와 player의 준비가 확인된 event에서 장착 snapshot을 얻는다. manager!=0 또는 pouch load return만으로 준비를 확정하지 않는다.
- equipped array는 rebuild 이후에만 신뢰한다. 로드 직후의 배열 공백은 실제 무장 해제와 구분한다. 그 구간에서 장착 flag 목록이나 실제 player 장비 참조를 활용하려면 수명/동기화/호출 시점을 추가 검증한다.
- 장착 instance가 바뀌면 baseline을 갱신하며 SHOT으로 세지 않는다. Bow ID가 같으면 DB lookup 결과는 재사용한다.
- 검증된 Link bow SHOT/READY event만 sequence를 증가시킨다. value setter 호출/값 감소만으로 발사하지 않는다.
- 파손/해제/로드 전환의 off 판정은 pending re-arm보다 우선한다.
- 알려지지 않은 bow ID는 off로 처리한다. 임의 기본 장력을 적용하지 않는다.

## Cache와 identity

`TensionCache = (BowID, normalizedTension, raw16)`

`Observation = (loadEpoch, equipEpoch, playerIdentity, bowActorIdentity, pouchItemIdentity, previousValue, baselineValid)`

같은 이름의 활 두 개를 교체하면 TensionCache는 재사용하고 Observation은 새로 만든다. pointer 단독은 allocator 재사용에 취약하다. loadEpoch/equipEpoch도 검증된 이벤트에서 갱신해야 하며, 현재 값으로 대체하거나 매 frame 갱신해서는 안 된다. 최종 actor identity에 사용할 proc ID/생성 세대는 아직 원본 경로 확인 대상이다.

장력은 Bow ID만의 함수다. arrow attack, arrow count, 내구도는 장력 입력이 아니다. arrow count와 내구도는 event 상관관계 분석에만 활용한다.

## 현재 구현된 검증 pack

`ENTRY → WAIT_POUCH_LOAD → PERIODIC_SEQUENCE_PROBE → HALTED_OFF`

1. entry에서 private state를 초기화한다.
2. pouch load 진입에서 off/재발행 카운터 reset, load return에서 gate를 연다. 이 gate는 pouch 함수 실행 완료만 뜻한다.
3. 이후 Player callback 1,121,241,...,1081번째에 raw16=0x3F04로 sequence를 증가시킨다.
4. callback 1201번째에 command=0으로 하고 halt 상태를 유지한다.
5. 다음 pouch load에서는 다시 off로 시작하고 sequence 숫자는 유지한다.
6. rebuild와 bow value store는 별도 telemetry만 갱신한다. 이 telemetry로 command를 바꾸지 않는다.

이 pack에는 Bow ID resolve나 DB runtime lookup, 실전 SHOT 판정이 없다. 진단용 카운터는 lock-free 원자 event queue가 아니므로 동시 callback이 발생하면 정확한 누적 횟수를 보장하지 않는다. 최종 pack의 event 전달은 game thread/동기화 조건을 추가 확인해야 한다.

## sequence → 장치 전송 검증

기준 Cemu commit: `079d1351c3fd8425b35cd1b950aa18dfffb50c0a`.
Gamepad-Core submodule: `9a16b81604fd711db3c445e8a8108e2b570f6477`.
Windows support submodule: `7a536ee95dcb49755f83767dcdc189bdf76a4fdd`.

1. `UpdateAdaptiveTriggerOutputs`는 full u32 command가 같을 때만 skip한다.
2. `ApplyAdaptiveTriggerBowRaw`가 trigger revision을 증가시킨다.
3. worker는 새 revision을 관찰하면 SetBow22와 UpdateOutput을 호출한다.
4. SetBow22는 바이트를 다시 구성하며 동일 force에 대한 dedup은 없다.
5. OutputDualSense는 동일 trigger payload여도 Write를 호출한다.
6. Windows backend는 유효 handle에서 USB 64-byte WriteFile을 호출한다. 이 경로에도 동일 payload dedup은 없다.

즉 연결/서비스/전송이 정상이고 변경을 소비했다면 **재전송 시도**는 발생한다. 장치 ACK나 물리적 snap reset 완료가 확인되는 것은 아니다. Cemu는 dispatch 전 lastCommand를 갱신하고 worker는 WriteFile 성공을 callback에 반환하지 않으므로 GraphicPack에는 완료 ACK가 없다.

근거: [bridge](https://github.com/npark2860-cyber/Cemu-Windows-ARM64/blob/079d1351c3fd8425b35cd1b950aa18dfffb50c0a/src/Cafe/GraphicPack/GraphicPack2.cpp), [service](https://github.com/npark2860-cyber/Cemu-Windows-ARM64/blob/079d1351c3fd8425b35cd1b950aa18dfffb50c0a/src/Cafe/OS/common/EnhancedSoundDualSenseService.h), [output composer](https://github.com/rafaelvaloto/Dualsense-Multiplatform/blob/9a16b81604fd711db3c445e8a8108e2b570f6477/Source/Private/GImplementations/Utils/GamepadOutput.cpp#L63), [Windows WriteFile](https://github.com/rafaelvaloto/Gamepad-Core-Tests/blob/7a536ee95dcb49755f83767dcdc189bdf76a4fdd/Common/Platform/windows/windows_device_info.cpp#L153).

## sequence-only re-arm이 실패하면

같은 update 안에서 off/arm을 쓰거나, 짧은 임의 pulse를 만드는 대안은 채택하지 않는다. GP command는 GX2SwapScanBuffers 시점의 최신 값으로 샘플링되고 service revision도 최신 request만 보존하므로 중간 off가 사라질 수 있다.

검토 가능한 GraphicPack-only 대안은 실제 game-state에서 SHOT 이후 NOT_READY 구간 동안 off를 유지하고, **별도의 검증된 READY 전환**에서 cached raw를 재발행하는 방식이다. 이는 off가 독립된 전송으로 관찰되는 충분한 시간과 실기 확인이 필요하다. frame N개 대기나 opcode 바이트를 임의로 바꾸는 방식으로 reset 성공을 보장하지 않는다. 현재 bridge에 ACK가 없으므로 독립된 상태 구간조차 관찰/재arm을 보장하지 못한다면 본체를 변경하지 않는 조건에서 해당 장치 동작을 보장할 수 없다고 결론내린다.
