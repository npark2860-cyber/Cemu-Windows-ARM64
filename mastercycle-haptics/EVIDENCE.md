# 조사 근거와 범위

CSV 76개 명칭을 실제 BARS AMTA metadata와 대조했다. 전체 검사 파일은 audio_inventory.json,
선택한 8개 소리의 원본 checksum/loop/sample 정보는 selected_audio_evidence.json에 있다.
이전 단순 문자열 검색의 미확인 MotorcycleWheelieStartEngine/Wind는 실제 AMTA 이름에
밑줄이 있는 Motorcycle_WheelieStartEngine/Wind로 확인된다. 이번 요청 범위에는 넣지 않았다.

원본 BARS: Wii U JP v208 update content/Sound/Resource.
GameROMMotorcycle: 40 entries, D_GameROMMotorcycle: 36 entries, D_GameROMMotorcycle_Mt: 20 entries.
Mt의 20개는 Mt_... 노면 이름이고 CSV의 Motorcycle cue와 직접 같지 않다.
이름과 loop metadata의 존재가 게임플레이 실행 조건을 검증하는 것은 아니다.

주행 MotorcycleEngine 3.21초 loop, MotorcycleEngineIdling 2.91초 loop,
MotorcycleEngineOffThrottle 4.96초 loop. 이 셋을 저/중/고속으로 재해석하지 않았다.

## 고정 Cemu 소스

- [BNVIB parser/player](https://github.com/npark2860-cyber/Cemu-Windows-ARM64/blob/079d1351c3fd8425b35cd1b950aa18dfffb50c0a/src/Cafe/OS/common/EnhancedHapticEngine.h)
- [PlayBnvib 및 단일 플레이어, amplitude-only 출력](https://github.com/npark2860-cyber/Cemu-Windows-ARM64/blob/079d1351c3fd8425b35cd1b950aa18dfffb50c0a/src/Cafe/OS/common/EnhancedSoundDualSenseService.h#L138)
- [AXApplyEnhancedSoundRoute의 재생/정지/중복 억제](https://github.com/npark2860-cyber/Cemu-Windows-ARM64/blob/079d1351c3fd8425b35cd1b950aa18dfffb50c0a/src/Cafe/OS/libs/snd_core/ax_voice.cpp#L728)
- [sound_routes.ini 로더](https://github.com/npark2860-cyber/Cemu-Windows-ARM64/blob/079d1351c3fd8425b35cd1b950aa18dfffb50c0a/src/Cafe/GraphicPack/GraphicPack2.cpp#L1008)
- [BARS/AMTA/FWAV catalog layout](https://github.com/npark2860-cyber/Cemu-Windows-ARM64/blob/079d1351c3fd8425b35cd1b950aa18dfffb50c0a/src/Cafe/OS/common/BotWSoundFingerprintCatalog.h)

FWAV ADPCM coefficient offset과 DSP 복원 연산은 vgmstream 원본 구현과 교차 확인했다.
[FWAV layout](https://github.com/vgmstream/vgmstream/blob/master/src/meta/bfwav.c),
[DSP decoder](https://github.com/vgmstream/vgmstream/blob/master/src/coding/ngc_dsp_decoder.c).

테스트: python test_preview.py. Cemu build/run이나 하드웨어 테스트를 대신하지 않는다.
저/중/고속 3분할, 실제 pitch/음량 동적 추적, 엔진 loop 자동 복귀는 이 결과물에 없다.
