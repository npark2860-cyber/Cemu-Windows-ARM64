# 검증용 pack — 최종 Bow 자동 장력 pack 아님

이 폴더만 Cemu graphicPacks 아래에 복사하고 pack을 수동으로 켠다. 다른 R2 raw-trigger pack은 끈다. 기존 PASS한 SE/USB 설정을 유지한다.

세이브 로드 후 Player callback 120회마다 같은 raw 0x3F04에 새 sequence를 붙여 재발행한다. 10회 발행 후 callback 1201에서 off로 끝난다. callback 횟수는 실제 frame/시간과 동일하다고 가정하지 않는다. 메뉴/일시정지에서는 진행이 멈출 수 있다.

R2 snap 후 놓았다가 다음 화살을 쏠 때 장력이 다시 생기는지 관찰한다. R2를 유지한 상태에서의 동작도 별도로 기록한다. 중간 off pulse는 없다. 종료 off 이후에는 pack을 끈다.

기대 command: 0x00013F04 → 0x00023F04 → ... → 0x000A3F04 → 0.

보고할 결과: 재-arm 성공 / 최초 장력만 있음 / 출력 없음 / pack 로드 오류. 출력 없음은 callback 적용 실패와 hardware re-arm 실패를 구분해야 한다.

원본 RPX 검증 및 독립 PPC 에뮬레이션 테스트를 통과했다. Cemu에서의 실제 pack 로드와 하드웨어 re-arm은 아직 실기 미검증이다. Bow ID 감지, DB runtime lookup, 실제 SHOT 감지 기능은 이 검증 pack에 없다. 자세한 hook 근거와 최종 설계는 상위 폴더의 HOOK_EVIDENCE.md, STATE_MACHINE.md, VALIDATION.md에 있다.
