# LSFG 성능 비교용 수정

목표: 원본 30 FPS 이상 유지, 생성 포함 60 FPS 출력 및 고른 출력 간격. 기존 약 40 원본 FPS가 약 20으로 떨어져 생성 포함 약 40이 되는 결과는 성능 성공으로 인정하지 않는다.

## 변경

- 게임 렌더 스레드의 추가 half-period sleep 제거.
- Cemu capture를 제출한 뒤의 CPU fence wait 제거. 같은 그래픽 큐에서 모듈 입력 barrier와 최종 fence가 선행 capture와 소비를 정렬한다. Host 이미지 수명은 최종 완료까지 유지한다.
- 정상 생성에서 input copy → compute → output copy를 같은 큐에 제출하고 최종 tail fence만 CPU에서 기다린다. 원래는 각 단계마다 CPU fence wait가 있었다. Input/output copy command buffer를 분리하여 아직 실행 중인 command buffer를 다시 기록하지 않는다.
- 정상 토글, 3회 incremental warmup, 크기 변경 시 자원 재생성, 오류/timeout 시 자원 보존 계약은 유지한다. Overlay draw data 재사용에 필요한 완료 대기는 유지했다.
- GPU shader 계산, 정밀도, 출력 해상도는 바꾸지 않았다. GPU 자체 처리 비용이 사라지는 수정은 아니다.

현재는 **동기식 비교 빌드**다. CPU에서 의도적으로 쉬는 비용을 제거했지만 생성/원본 present가 연달아 몰릴 수 있다. 이는 간격 로그로 판정해야 하며 평균 present 요청이 60회/s라는 이유만으로 부드러운 60 Hz 출력 성공으로 보고하지 않는다. 실패하면 render/present 생산·소비를 분리하는 후속 설계가 필요하다.

## 로그

`[LSFG-PERF]`가 약 2초마다 출력된다. OFF/ON 모두 기록한다.

- `source_present_fps`: 원본으로 분류된 성공 present 요청/s. 기존 게임 FPS 카운터와 함께 본다.
- `generated_present_fps`: 생성으로 분류된 성공 present 요청/s.
- `accepted_present_fps`: Vulkan이 성공 또는 suboptimal로 받은 전체 present 요청/s. 실제 화면 scanout 계측값은 아니다.
- `module_batch_avg`: 생성 API의 CPU wall time 평균. 새로 제거한 capture 대기의 일부가 이 최종 대기에 포함될 수 있어 이전 버전의 단독 생성 약 11ms와 직접 비교하지 않는다.
- `capture_submit_sum`, `present_host_sum`, `overlay_wait_sum`: 해당 구간의 CPU wall time 합계. 서로 정의가 다르므로 GPU kernel 시간으로 해석하지 않는다. `intentional_sleep=0`.
- Present return gap의 평균/최대, 4ms 미만 및 33ms 초과 개수. 연속 두 출력이 몰리거나 긴 빈 구간이 있는지 찾는 지표다. 실제 display cadence는 별도 확인이 필요하다.

## 수동 비교

에이전트가 실행하거나 입력을 조작하지 않는다. 사용자가 같은 게임 장면·창 크기·렌더 해상도에서 OFF를 15초 이상 유지하고, ON을 켜 warmup 뒤 15초 이상 유지한다. 창 크기는 그 사이 바꾸지 않는다. 기존 카운터가 ON에서도 30 이상인지 먼저 확인한다. 출력 빈도와 간격은 로그로 함께 판정한다.

기존 `Cemu-lsfg.exe`는 보존한다. 새 파일은 별도 `Cemu-lsfg-perf.exe`로 제공하며 제목은 `[LSFG PERF]`이다. GPU 검증 전 네 유지 버전에 반영하지 않는다.
