# Wii U v208 hook 근거

## 원본 식별

사용자 제공 `U-King.rpx`를 읽기 전용으로 분석했다.

- SHA256: `ba58da5b95ce929e005d058ceb08b9b2788d1ab2bbc8a6c189bbadca0bb34d30`
- Cemu moduleMatches: `0x6267BFD0`
- CRC 계산은 Cemu `RPLLoader_BeginCemuhookCRC`의 section 메타데이터 및 압축 해제된 payload 순서를 따랐다. little-endian host scalar 직렬화와 NOBITS의 원래 size도 반영했다.
- `.text`: `0x02000020`, 길이 `0x2347C0C`.
- RPX 압축 section의 size prefix와 zlib 해제 길이 일치를 확인했다.
- Capstone은 Espresso paired-single 명령의 의미를 보증하지 않으므로 opcode 4는 `.long`으로 남긴다. 선택한 hook word와 복원 instruction은 전부 표준 PPC 정수 명령이다.

## 검증 pack에서 사용하는 5개 위치

| 주소 | 원본 word | 원본 instruction | 위치와 register 근거 |
|---|---|---|---|
| `0x02D67D28` | `80010014` | `lwz r0,0x14(r1)` | Player callback `0x02D67CF4`의 공통 epilogue. 진입 `r3=player`가 `0x02D67D10`에서 r31에 저장된다. hook은 player를 역참조하지 않는다. |
| `0x02EB4518` | `7C0802A6` | `mflr r0` | pouch loadFromGameData 진입. `0x02EB4540`에서 r3를 r23에 보관하고 manager+0x10을 lock한다. |
| `0x02EB4E80` | `4E800020` | `blr` | 위 load 함수의 정리 후 return. world/player/장착 준비 완료로 해석하지 않는다. |
| `0x02EBF740` | `80010014` | `lwz r0,0x14(r1)` | equipped array rebuild의 `0x02EBF73C: bl 0x030BB69C` unlock 다음. |
| `0x02EB6874` | `93A90010` | `stw r29,0x10(r9)` | setter가 equipped item을 찾은 후 실제 value 저장. r9=item, r29=new value, r30=PouchItemType, r28=manager. 기존 pouch lock 안이다. |

각 patch는 `b`로 codecave에 들어가며 LR을 바꾸지 않는다. wrapper는 수정하는 r0/r3-r7와 CR을 저장/복원한다. r2/r8-r31, LR/CTR/XER/FPR은 helper에서 변경하지 않는다. 원본 word의 동작을 한 번 수행한 다음 원래 다음 instruction으로 복귀한다. return hook은 원래 `blr`를 실행한다. stack frame은 0x30 bytes이며 heap, OS 호출, FP 연산을 사용하지 않는다. value hook은 기존 게임 store 외에는 GraphicPack 전용 상태에만 기록한다.

## 직접 caller 확인

`0x02EBF690` rebuild의 직접 branch/call 참조는 다음 둘이다. indirect caller가 없다는 주장은 하지 않는다.

- `0x03048658: 4BE77039 = bl 0x02EBF690`
- `0x03048B08: 4BE76B89 = bl 0x02EBF690`

rebuild는 manager+0x3812C의 네 항목을 비우고 type<4 및 equipped byte가 있는 pouch item을 채운다. Bow는 type 1이다. 이 함수만으로 로드 직후 자동 감지를 보장할 수 없다.

`0x02EB67F4` setter의 직접 caller:

- `0x024A29D0: 48A13E25 = bl 0x02EB67F4`
- 직전 `0x024A29C4: 3C601047 = lis r3,0x1047`
- `0x024A29C8: 80639978 = lwz r3,-0x6688(r3)` — manager singleton
- `0x024A29CC: 7FE5FB78 = mr r5,r31` — type
- 함수 진입 인자 r3=manager, r4=value, r5=type가 각각 r28/r29/r30으로 보관되는 것을 확인했다.

`0x024A2928` actor→pouch sync의 직접 caller:

- `0x024A36AC: 4BFFF27D`
- `0x024AC920: 4BFF6009`
- `0x024B14D0: 4BFF1459`

이 함수는 actor vtable+0x4EC 조건과 +0x2BC getter를 거쳐 값을 동기화한다. 위 세 caller 모두를 실제 발사로 판정할 근거는 없으므로 재발행 신호로 쓰지 않는다.

`0x02EB4518` load의 직접 caller:

- `0x02EB4E9C: 4BFFF67D`
- `0x02EB9E4C: 4BFFA6CD`

특히 `0x02EB4E84` caller는 load가 돌아온 뒤 `0x02EB4F90`부터 manager+0x3812C 배열을 다시 zero한다. 따라서 load return에서 배열을 한 번 읽고 초기화를 끝내는 설계는 잘못될 수 있다.

Player callback `0x02D67CF4`는 직접 call 참조가 없으며 `.rodata 0x101E62A0`에 함수 포인터가 있다. 외부 Wii U RE의 PlayerTickHook과 주소가 일치한다. 원본의 간접 dispatch 함수와 실제 호출 횟수는 런타임 확인 대상이다. 이를 임의로 60Hz frame callback이라고 명명하지 않는다.

## 발사 경로 조사 결과와 남은 작업

화살 소비 `0x02EB6624`의 원본 감산은 `0x02EB6758: 7C180050 = subf r0,r24,r0`이다. 직접 caller는 `0x02527F74`와 `0x02702BA4`다. 전자의 wrapper `0x02527EA4`는 `0x02528238`, `0x025284AC`, `0x0252865C`에서 호출된다. 후자는 다른 actor 경로다. 이 차이는 소비 함수 전체를 hook하여 모든 호출을 Link의 SHOT으로 세면 안 된다는 근거다. **이 주소들은 검증 pack에서 패치하지 않는다.**

다음 단계는 실제 Link 소유 bow actor/instance, 발사 시점, multi-shot, 소비 없는 활/모드, 장착·로드 경로와 대조하는 것이다. source상 함수 호출과 실기 발사 상관관계는 별도 검증 항목이다.

## FPS++ 비교

upstream `cemu-project/cemu_graphic_packs` commit `cca9f12535a48e73e7e48c3d03cfcffdc466f337`의 FPS++ ASM 10개에서 선택한 5개 주소에 대한 직접 주소 일치는 없었다. `0x031FA97C`는 FPS++가 사용하며 이 pack은 사용하지 않는다. `0x031FA888`, `0x031FA984`도 사용하지 않는다. 사용자 설치 pack 전체의 충돌 부재까지 검증한 것은 아니다.

외부 의미 교차검증: [Wii U v208 RE](https://github.com/BladesawStudios/wiixlaunch-botw/blob/1bdab2d1978efb2bab1d296b7d2a8c408b94aa0a/data/symbols-wiiu-v208.csv), [Player callback 사용례](https://github.com/BladesawStudios/wiixlaunch-botw/blob/1bdab2d1978efb2bab1d296b7d2a8c408b94aa0a/include/wiixlaunch/botw/game/player.hpp#L141).
