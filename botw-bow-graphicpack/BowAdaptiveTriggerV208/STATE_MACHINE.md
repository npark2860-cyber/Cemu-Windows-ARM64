# RC1 상태 머신과 진단값

ENTRY → WAIT_POUCH_LOAD → WAIT_VALID_PLAYER_BOW → TRACKING

- ENTRY: command=0, cache/identity/baseline 초기화. load-complete 취급 금지.
- LOAD_BEGIN: off, epoch 증가, pending release 폐기, 기존 player/bow observation 무효화.
- LOAD_END: pouch-loading gate만 해제. 유효 player/actor 확인 전에는 출력하지 않는다.
- VALID_NEW_INSTANCE: 엄격한 Weapon_Bow_NNN 이름 확인. 같은 Bow ID는 raw 재사용,
  다른 ID는 73-word direct table 1회 조회. instance epoch 증가, value baseline reset, sequence++.
- STABLE_INSTANCE: ID/name/DB 재검색 없음. release가 없으면 command도 쓰지 않는다.
- RELEASE: 현재 actor pointer+proc ID가 일치할 때 pending counter 증가.
  다음 Player callback에서 handle을 재검사하고 pending을 합쳐 cached raw를 sequence++로 발행.
- VALUE_SYNC: baseline 진단값만 갱신. 양수 감소는 RELEASE 아님. 0 이하는 해당 생성 ID를 차단하고 off.
- DETACH/DELETE/INVALID: off 및 baseline 폐기. 삭제 actor는 pointer+생성 ID를 기록해 늦은 callback 재-arm 차단.

장력 cache(BowID, normalized, raw)는 instance observation과 분리되어 off/교체 뒤에도 보존된다.
같은 ID의 다른 활을 교체한 경우 emit reason=2(장착), release count는 증가하지 않는다.
원본 이름은 instance가 바뀌었을 때만 읽으며 엄격히 14문자+NUL인 ID만 받는다.

## BowState: big-endian u32, codecave 시작

| offset | 값 |
|---|---|
| 00 / 04 | command / 16-bit sequence |
| 08 / 0C | pouch-loading gate / load-player epoch |
| 10 / 14 | player pointer / proc ID |
| 18 / 1C | bow pointer / proc ID |
| 20 / 24 | cached numeric Bow ID / cached raw16 |
| 28 / 2C | last synced bow value / baseline valid |
| 30 / 34 | equip observation epoch / Player callback count |
| 38 / 3C | command publish count / accepted release count |
| 40 / 44 | DB lookups / same-ID new-instance cache hits |
| 48 / 4C | nonzero→off count / pouch load count |
| 50 | reason: 1 invalid/off, 2 new equip, 3 release publish; control hooks may retain last tick reason |
| 54 / 58 | blocked bow pointer / proc ID |
| 5C / 68 | blocked player pointer / proc ID |
| 60 / 64 | accepted bow value syncs / mismatching release count |
| 6C | cached original normalized tension |
| 70 / 74 | release producer counter / consumed counter |
| 78 / 7C | reserved / private lock |

주소는 고정하지 않는다. 적용 로그의 이 pack codecave 시작 주소가 BowState다.
다른 pack 활성화 순서에 따라 달라진다. Cemu debugger에서 읽을 때 활용한다.
release 수는 실제 발사 수와 비교할 진단값이며 검증 전에는 둘이 같다고 가정하지 않는다.
