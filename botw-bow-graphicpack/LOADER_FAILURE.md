# 2026-09-20 실기 로그: 패치 파일명 오류

실행 로그: Cemu 079d135, BOTW JP v208, module checksum 0x6267bfd0.
10:45:41.357에 BowRawConstantValidation_ pack의 `Line 5: Invalid syntax` 발생.
해당 줄은 rules.txt의 description이 아니라 patches.txt의 `.origin = codecave`이다.
오류 출력 함수가 pack 식별을 위해 rules.txt 경로를 표시한다.
SequenceRearmValidation은 이 실행의 활성 pack 목록에 없다.

원인: 079d135의 GraphicPack2Patches.cpp LoadPatchFiles/LoadCemuPatches는
`patch_*.asm`을 modern parser로 읽고, 그런 파일이 없으면 `patches.txt`를
legacy Cemuhook parser로 읽는다. legacy parser는 `.origin`을 허용하지 않는다.
따라서 raw command 등록 이전에 실패했다. 이 결과는 하드웨어 re-arm 실패의 증거가 아니다.

근거:
https://github.com/npark2860-cyber/Cemu-Windows-ARM64/blob/079d1351c3fd8425b35cd1b950aa18dfffb50c0a/src/Cafe/GraphicPack/GraphicPack2Patches.cpp#L69
https://github.com/npark2860-cyber/Cemu-Windows-ARM64/blob/079d1351c3fd8425b35cd1b950aa18dfffb50c0a/src/Cafe/GraphicPack/GraphicPack2PatchesParser.cpp

수정: sequence pack을 patch_bow_sequence.asm으로, 설치된 constant pack을
patch_bow_constant.asm으로 이름 변경. PPC 코드와 command 값은 변경하지 않는다.
생성기, 독립 테스트 입력, ZIP도 동일한 이름으로 수정한다.
독립 PPC 테스트는 Cemu의 파일 선택을 실행하지 않으므로 종전 PASS가 로더 PASS를 의미하지 않았다.

다음 실행: constant pack은 끄고 sequence pack만 켠다.
로그에 `Applying patch group 'BotwBowSequenceProbeV208'`가 있어야 한다.
이후에도 출력이 없으면 load gate/Player callback 실행 여부부터 확인한다.
물리적 re-arm과 최종 Bow 자동 감지는 아직 미검증이며 Cemu 본체는 변경하지 않는다.
