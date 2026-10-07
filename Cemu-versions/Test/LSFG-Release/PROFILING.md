# LSFG Release 계측 시험본

실행 파일은 `runtime-experiment/Cemu-lsfg-profile.exe`, 제목은 `[LSFG PROFILE]`이다. 기존 `Cemu-lsfg.exe`와 `Cemu-lsfg-perf.exe`는 보존한다. 성능 수정본을 기반으로 CPU/GPU 비용 구분을 추가한 시험본이며, 비동기 생성 완성본이나 성능 개선이 검증된 릴리즈가 아니다.

## 측정 항목

약 2초마다 기존 `[LSFG-PERF]` 로그와 새 `[LSFG-PROFILE]` 로그를 출력한다. `avg/max/n`은 평균 ms / 최대 ms / 유효 샘플 수다. GPU timestamp를 얻지 못하면 `N/A`를 출력한다.

기존 PERF 헤더의 크기는 준비된 LSFG context 크기다. OFF 중 창을 바꾸면 현재 창과 다를 수 있으므로 비교 중에는 창 크기를 고정한다.

| 항목 | 측정 범위와 해석 |
|---|---|
| `real` | 직전 Cemu SwapBuffers 이후부터 다음 FSR 후 LSFG capture 직전까지의 GPU timestamp span. 프레임 사이 CPU 공급 지연 등 GPU timeline 공백도 포함할 수 있어 순수 GPU busy/utilization 수치가 아니다. |
| `input_copy`, `prepass`, `generated`, `output_copy` | LSFG 입력 복사, 준비 pass, 생성 pass, 출력 복사 각각의 GPU timestamp span. GPU 의존성 대기나 단계 겹침이 포함될 수 있으며 단순 합계를 하드웨어 포화율로 해석하지 않는다. 3회 warmup은 이 평균에서 제외한다. |
| `module_batch_avg` | `generate_step()` 전체 CPU wall time. GPU 대기와 CPU 기록/제출 비용이 포함된다. |
| `Cemu_vkQueueSubmit`, `LSFG_vkQueueSubmit` | 실제 host `vkQueueSubmit` 함수 호출에 걸린 CPU 시간. GPU 실행 시간이 아니다. |
| `Cemu_fence_wait_sum` | Cemu command-buffer fence 함수의 CPU 대기 합계. overlay 대기와 중첩되므로 두 값을 다시 더하지 않는다. |
| `LSFG_tail_fence_wait_sum` | 해당 generation API 안의 module tail fence CPU 대기 합계. Cemu는 별도 input-ready fence를 전달하지 않는다. |
| `host_capture_submit_end_to_LSFG_submit` | Cemu 마지막 capture submit 반환부터 module 첫 submit 호출 직전까지의 CPU gap. GPU가 그동안 놀았다는 뜻은 아니다. 초기 reset/warmup 작업의 첫 submit일 수도 있다. |
| `GPU_real_end_to_prepass_begin` | 같은 graphics queue의 real-frame 끝과 LSFG 준비 시작 사이 timestamp span. 입력 capture/transfer·barrier·의존성 등을 포함하므로 GPU idle이라고 부르지 않는다. 역전/해석 불가 샘플은 집계하지 않는다. |
| `queue_mutex_hold` | `N/A(single_render_thread)`. 현재 큐는 단일 렌더 스레드 호출 순서로 직렬화하며 공용 queue mutex는 없다. |

OFF에서는 진단용 timestamp 기록만 추가한다. LSFG 프레임 복사/dispatch/history 작업은 하지 않는다. 16개 query slot을 재사용하며, 완료된 Cemu command buffer의 결과만 읽는다. slot이 꽉 차면 샘플을 생략한다. 프로파일러가 새로운 CPU completion wait를 추가하지 않는다. Timestamp 자체와 기록/조회에는 작은 측정 오버헤드가 있을 수 있으므로 성능 비교본과 구분한다.

Vulkan query는 queued reset이 아직 실행되지 않았을 때 이전 availability를 보일 수 있다. 이 때문에 fence 완료로 해당 제출이 끝났음을 확인한 뒤 읽고, `VK_QUERY_RESULT_WAIT_BIT`는 사용하지 않는다. [Vulkan query 결과 규칙](https://docs.vulkan.org/refpages/latest/refpages/source/vkGetQueryPoolResults.html).

## 사용자가 직접 비교하는 순서

1. 동일한 게임 장면, 렌더 해상도, 창 크기에서 OFF 15초 이상 유지한다.
2. ON으로 바꾸고 warmup 이후 15초 이상 유지한다. 가능하면 다시 OFF로 같은 장면을 비교한다.
3. 원본 FPS 카운터와 로그를 함께 확인한다. 시험 사이 창 크기를 바꾸지 않는다. 종료는 평소 방식으로 한다.

CPU wall 대비 fence 대기가 크고 GPU pass 시간이 작다면 직렬화/앞선 GPU 작업 대기가 우선 조사 대상이다. GPU pass span이 해상도와 함께 크게 증가하면 GPU 비용이 크다는 단서지만 이것만으로 포화가 확정되지는 않는다. 실제 idle/utilization은 GPU timeline profiler로 추가 확인해야 한다. Performance mode/flow scale은 현재 Quality/1.0 고정이며 이 시험본에서 임의로 바꾸지 않았다.

원본 30 FPS 유지와 생성 포함 60회/s present 요청만으로 고른 60 Hz 표시가 검증되지는 않는다. 실제 화면 표시 간격과 화질은 여전히 별도 검증 항목이다. 에이전트가 GPU 실행이나 화면 조작을 하려면 사용자에게 시간을 먼저 요청한다.
