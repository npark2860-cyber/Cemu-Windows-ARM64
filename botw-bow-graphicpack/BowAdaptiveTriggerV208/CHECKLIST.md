# RC1 실기 승인 체크리스트

기존 상수/sequence transport 테스트는 PASS. 다시 반복하지 않고 실제 Bow-aware 동작을 검증한다.

- [ ] 적용 로그에 BotwBowAdaptiveTriggerV208가 있고 syntax/assembler 오류가 없다.
- [ ] 다른 R2 raw-trigger/SequenceRearmValidation pack은 모두 꺼져 있다.
- [ ] 이미 활을 장착한 세이브: 메뉴를 열지 않아도 최초 장력.
- [ ] 활 없는 세이브: off. 활 장착 후 자동 arm.
- [ ] 일반 메뉴/퀵 메뉴로 다른 Bow ID 교체: DB에 따른 장력. 메뉴 닫기 후 실제 world 장비를 기준으로 확인.
- [ ] 같은 Bow ID의 다른 instance 교체: 장력 cache 재사용, release count 증가 없음.
- [ ] 일반 발사 후 R2를 놓고 다음 화살: cached tension 재-arm. 여러 번 연속 반복.
- [ ] R2를 계속 당기는 경우와 놓는 경우를 구분하여 결과 기록.
- [ ] 조준 취소, 화살 종류 변경, 화살 획득/드롭: release count 증가 없음.
- [ ] 멀티샷/속사/고대 화살/얼음 화살/특수 활: 실제 발사와 release count, publish count 비교.
- [ ] 적의 활 발사와 기존에 버린 활: 내 R2에 재발행 없음.
- [ ] 마지막 내구도 발사 후 파손: off가 우선하고 잔류 장력 없음.
- [ ] 해제/드롭 후 off, 다른 활 재장착 후 arm.
- [ ] 세이브 재로드, 사망/재시작, 사당/맵 전환, 타이틀 복귀: off 시점 및 재진입 초기화.
- [ ] 전환 화면 시작과 실제 off 사이에 지연이 있다면 구체적인 전환 종류를 기록. 공통 전환 hook은 아직 미확정.
- [ ] FPS++ 30/60fps 및 SE/BNVIB 동시 사용에서 프레임·오디오·입력 이상 없음.
- [ ] Infinite Arrows/Durability 사용 시 원본 release 경로 유지 여부 확인.
- [ ] 26종 raw 값의 체감 강도 보정. 낮은 장력을 출력 실패로 오인하지 않음.

보고할 최소 항목: 최초 감지 / 다른 활 교체 / 같은-ID 교체 / 반복 발사 / 파손 / 재로드.
문제가 있으면 log.txt와 사용한 활 ID, 이벤트 순서를 함께 남긴다.
off 전환 누락 또는 release false positive가 있으면 완료로 판정하지 않는다.
