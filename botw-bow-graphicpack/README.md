# BOTW v208 Bow Adaptive Trigger — 검증 준비 자료

상태: **sequence-only 실기 PASS; Bow 자동 감지/DB/cache/release/off를 연결한 RC1 구현 완료, RC1 게임플레이 실기 승인 대기**. Cemu 본체를 수정하지 않는다.

현재 설치 대상은 `BowAdaptiveTriggerV208`다. 이 폴더의 README.md, HOOKS.md, STATE_MACHINE.md, CHECKLIST.md가 RC1의 최신 설명이다. 기존 SequenceRearmValidation과 함께 활성화하면 안 된다.

작업 기준은 확인 시점의 Test_SE `build/test-se-once` HEAD `079d1351c3fd8425b35cd1b950aa18dfffb50c0a`다. 상수 `0x00013F04`의 장력 출력은 사용자 실기 PASS를 재사용한다. 상수 테스트를 다시 요구하지 않는다.

## 준비한 자료

- `bow_db.csv`: 사용자가 제공한 26종 normalized tension을 그대로 보존하고, 별도 열에 미검증 raw 변환 제안을 기록했다.
- `HOOK_EVIDENCE.md`: hook 근거와 부족한 원본 instruction/caller 검증.
- `STATE_MACHINE.md`: instance와 장력 cache 분리, 로드 및 re-arm 정책.
- `VALIDATION.md`: 상수 PASS 다음 단계의 실기 검증 체크리스트.
- `SequenceRearmValidation/rules.txt`, `SequenceRearmValidation/patch_bow_sequence.asm`: 원본 RPX로 확인한 hook만 사용하는 검증 pack. Bow ID별 자동 장력 제품으로 오인하지 않는다.
- `inspect_rpx.py`: RPX를 읽기만 하는 분석 도구.
- `test_rearm_pack.py`: 실제 생성된 PPC 코드의 독립 조립/에뮬레이션 테스트.

## 완성을 위해 필요한 입력

1. 원본 RPX는 확보했다. SHA256 `ba58da5b95ce929e005d058ceb08b9b2788d1ab2bbc8a6c189bbadca0bb34d30`, 직접 계산한 Cemu moduleMatches `0x6267BFD0`다.
2. sequence-only 실기 결과는 2026-09-20 사용자 PASS. 같은 시각 log에서 Cemu 079d135, module 6267BFD0 및 BotwBowSequenceProbeV208 적용 성공을 확인했다.
3. RC1의 새 release 경로와 실제 발사의 대응, 특수 활/모드/세계 전환 시점은 실기 확인 대상이다. 내구도 감소를 SHOT으로 사용하지 않는다.

이 상위 폴더 전체, 분석 도구, 원본 RPX는 설치/배포 대상이 아니다. 이전 SequenceRearmValidation은 이력 보존용이며 120회 주기/10회 제한이 있다. 새로운 BowAdaptiveTriggerV208에는 주기적 재발행이나 횟수 제한이 없다.

독립 테스트: `test_bow_pack.py`는 RC1의 실제 생성 PPC와 9개 원본 hook word, getter/handle 근거, 26개 DB, cache/instance 분리, 파손 우선과 레지스터 보존을 확인한다. 구 검증 pack의 실제 로드/re-arm은 PASS이고 RC1은 새 실기 승인이 필요하다. 본체 빌드를 수행하지 않았다.

## Raw 변환 제안 — 체감 보정 전

normalized tension T를 0..100으로 해석하는 정책을 제안한다. 이는 BOTW 원본 공식이 아니라 이 GraphicPack의 설계 선택이다.

- T=0 또는 알 수 없는 Bow ID: off.
- T>0: `q = clamp(1 + floor((7*T + 50)/100), 1, 8)`.
- draw strength=q, snap strength=q.
- `forcePair = (q-1) | ((q-1)<<3)`.
- StartZone raw byte=0x04.
- `raw16 = (forcePair<<8) | 0x04`.
- `command = (sequence<<16) | raw16`.

이 정책은 프로토콜의 8단계 강도로 양자화하므로 일부 Bow ID가 같은 raw 값이 된다. 원래 normalized tension은 CSV에 그대로 남는다. 물리적 장력이 T에 선형이라는 주장은 하지 않는다. Arrow attack, arrow 종류, 현재 내구도는 장력 공식에 사용하지 않는다.

고정 Gamepad-Core는 Bow22의 zone 상위 바이트를 0x01로 설정한다. 따라서 raw StartZone 0x04는 zone mask 0x0104, 즉 위치 2와 8에 대응한다. PASS한 forcePair 0x3F는 draw=8, snap=8이다. CSV의 보정 전 값은 PASS한 한 값으로 모두 실기 검증됐다고 간주하지 않는다.

프로토콜 근거: [dualsensectl command_trigger_bow](https://github.com/nowrep/dualsensectl/blob/d3ae2fa272e1bf9a5c08a0ded3f374b40f7c73ac/main.c), [고정 Gamepad-Core Bow22](https://github.com/rafaelvaloto/Dualsense-Multiplatform/blob/9a16b81604fd711db3c445e8a8108e2b570f6477/Source/Public/GImplementations/Utils/GamepadTrigger.h).
