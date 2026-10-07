# RC1 hook 근거 — 원본 명령 검증과 이벤트 실기 검증의 구분

RPX SHA256: ba58da5b95ce929e005d058ceb08b9b2788d1ab2bbc8a6c189bbadca0bb34d30

Cemu moduleMatches: 6267BFD0. Test_SE branch build/test-se-once는 이번 작업 시작 시에도
079d1351c3fd8425b35cd1b950aa18dfffb50c0a였다. Cemu 소스와 RPX는 수정하지 않았다.

| hook | 원본 word / instruction | 원본 경로와 사용 register |
|---|---|---|
| 02D67D28 | 80010014 / lwz r0,0x14(r1) | Player callback 02D67CF4 공통 epilogue. r31=player. 02D67D10의 mr r31,r3로 확인 |
| 02EB4518 | 7C0802A6 / mflr r0 | PauseMenuDataMgr::loadFromGameData 진입. r3=manager |
| 02EB4E80 | 4E800020 / blr | 같은 load 함수 return. world 전체 load-complete라는 의미가 아님 |
| 0252826C | 83A1001C / lwz r29,0x1C(r1) | 02527F98의 release 경로 끝. r29=component, [r29]=bow actor 후보. 바로 앞 02528268에서 0252680C 호출 |
| 0252852C | 83A1001C / lwz r29,0x1C(r1) | 02528288의 release 경로 끝. r29=component. 앞 02528528에서 0252680C 호출 |
| 02528684 | 8001006C / lwz r0,0x6C(r1) | 02528548의 release 경로 끝. r30=component. 앞 02528680에서 0252680C 호출 |
| 024A29C4 | 3C601047 / lis r3,0x1047 | actor→pouch sync 024A2928, setter 호출 직전. r30=actor, r31=mapped PouchItemType, r4=value. Bow type=1, 0 이하만 off 판단 |
| 0378A374 | 7C0802A6 / mflr r0 | BaseProc::deleteLater 진입. r3=proc. 현재 player/bow에 대해서만 상태를 무효화 |
| 02D6F0CC | 7C0802A6 / mflr r0 | Player 장비 detach helper. r3=player, r4=equipment slot. Bow slot=2만 처리 |

세 release 위치의 직전 code는 각각 rodata 100D6CC8 / 100D6CD0 / 100D6CD8의
UTF-8 `発射`를 SafeString으로 전달한다. 같은 경로는 02527AC4를 통해
Release1/2/3/5 및 ChemicalShootIce/Ancient 문자열이 있는 release 처리로 이어지고,
02528238 / 025284AC / 0252865C에서 화살 소비 helper 02527EA4를 호출한다.
helper의 02527F74는 실제 pouch 화살 소비 02EB6624를 호출한다.
0252A9FC는 02527F98, 0252AA40은 02528288로 이어진다.
다만 이 정적 경로는 projectile 성공 및 모든 발사 모드의 실기 커버리지 증명은 아니다.
RC1은 component owner가 현재 player bow actor와 pointer/생성 ID까지 일치해야 이벤트를 받는다.
enemy bow나 이전 instance의 이벤트는 받지 않는다.

## 원본 장비 getter와 동일한 handle 필드 선택

- 02D58A8C GetEquippedBow(player)는 02D8D0E4에서 slot=2를 얻는다.
- player vtable+314 호출 → 033BCCD8(equipMgr,slot).
- Player vtable의 해당 entry 101E6310은 02D799B0.
- 02D799B0의 두 명령은 `386307CC addi r3,r3,0x7CC; 4E800020 blr`.
- 033BCCF0/F4가 slot*16을 더한다. 따라서 bow ProcLink는 player+7EC.
- 0378DE50은 ProcLink+0의 link data, +4의 proc ID, +8의 flag를 사용한다.
- 0378D8DC는 link+3C의 ID를 검사하고 link+40의 actor를 반환한다.
- 0378D938/93C/940은 actor를 link+40, actor+50의 생성 ID를 link+3C에 저장한다.
- 033BCD60~68은 actor lifecycle byte +54가 1인지 검사한다.

RC1은 game getter 함수를 추가 호출하지 않고 위 slot의 읽기 전용 snapshot을 사용한다.
player vtable+314가 02D799B0인지도 확인한다. 같은 pointer라도 proc ID가 바뀌면 새 instance다.
handle ID를 다시 읽어 불일치하면 off로 처리한다. RTTI getter와 actor pinning 전체를 복제한 것은 아니다.

## 조사했지만 runtime에 쓰지 않은 후보

02EBF690 rebuild는 완료 후 equipped array를 얻을 수 있지만 로드 후 caller 02EB4E84가 배열을 다시 비운다.
02EB67F4 setter는 generic 값 동기화이며 발사 전용 이벤트가 아니다.
따라서 초기 감지는 실제 Player slot, 파손 판단은 actor가 살아 있는 024A2928의 caller 측을 사용했다.
화살 수량 감소 자체도 발사 판정으로 사용하지 않는다.

## ABI와 동기화

각 hook은 b로 진입한다. 0x60-byte stack frame에 r0/r3-r12, CR/LR/CTR을 저장한다.
r1은 복구하고 원본 명령을 한 번 실행한 뒤 원래 다음 명령으로 복귀한다.
r2/r13-r31와 XER/FPR은 helper에서 변경하지 않는다. 단, 원본 lwz r29 자체의 효과는 그대로 유지한다.
GP helper의 bl은 저장한 LR을 복구한다. 게임/OS 호출, heap, float 연산은 없다.

private state는 lwarx/stwcx. lock으로 직렬화한다. lock 안에서 외부 함수를 호출하지 않는다.
unlock의 PPC sync(7C0004AC)는 Cemu assembler에 SYNC mnemonic이 없어 `.uint`로 기재한다.
멀티코어 scheduling/실제 경합 성능은 실기 검증 대상이다. private lock이 BOTW 객체 수명까지 잠그지는 않는다.

설치된 GraphicPack 주소 검색에서 기존 SequenceRearmValidation과 세 주소가 겹친다.
반드시 기존 validation pack을 끈다. 검색 결과 외의 간접/동적 패치 충돌 부재는 보장하지 않는다.
031FA97C / 031FA888 / 031FA984는 사용하지 않는다.

## 외부 의미 교차검증

- [Wii U v208 symbols](https://github.com/BladesawStudios/wiixlaunch-botw/blob/1bdab2d1978efb2bab1d296b7d2a8c408b94aa0a/data/symbols-wiiu-v208.csv)
- [Player tick + equipped bow getter 사용례](https://github.com/BladesawStudios/wiixlaunch-botw/blob/1bdab2d1978efb2bab1d296b7d2a8c408b94aa0a/include/wiixlaunch/botw/game/player.hpp)
- [Actor 이름/생성 ID/lifecycle](https://github.com/BladesawStudios/wiixlaunch-botw/blob/1bdab2d1978efb2bab1d296b7d2a8c408b94aa0a/include/wiixlaunch/botw/game/actor.hpp)

주소와 원본 word는 링크의 명칭만 믿은 것이 아니라 사용자 제공 RPX에서 직접 대조했다.
