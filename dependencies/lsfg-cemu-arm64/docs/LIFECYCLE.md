# Cemu Release 실험의 자원 및 history 수명

2026-09-29. 이 문서는 원본 패키지의 지연 초기화 및 매 reset context 재생성 설명을 대체한다. C ABI v1의 기존 구조체 크기와 기존 generate 호출 방식은 유지했다. 추가 API를 쓰려면 이 소스에서 빌드한 라이브러리가 필요하다.

## 상태와 출력

1. Vulkan 장치 생성 후 `create` → `prepare`: DLL 검증, 셰이더와 pipeline 준비. 출력 크기를 알면 `create_context` → `prepare_context`: GPU 자원과 layout 준비. OFF 상태에서 수행한다. 초기 layout 전환과 black image clear는 submit하지만 frame generation compute dispatch는 하지 않는다.
2. READY/OFF: Cemu의 기존 FSR/오버레이/present 경로를 사용한다. 매 프레임 LSFG capture, dispatch, history 갱신 또는 추가 GPU 대기 없음. 할당한 메모리는 유지한다.
3. ON: CPU에서 enabled를 바꾸고 실제 프레임 쌍을 확보한다. `generate_step` 첫 호출이 내부 history 이미지를 0으로 지우고 양쪽 입력을 현재 프레임으로 채운다. 이후 연속된 원본 프레임마다 한 번씩 총 3회의 warmup을 수행한다.
4. 세 warmup 호출 모두 `WARMING`을 반환하고 host output은 쓰지 않는다. Host는 해당 원본을 기존 경로로 출력한다. 다음 호출부터 `OK`와 생성 결과를 반환한다. `WARMING`도 프레임 ID를 소비하므로 다음 previous ID는 직전 current ID여야 한다.
5. OFF 전환은 다음 프레임 경계에서 반영한다. 이미 제출된 GPU 작업을 취소하거나 그 자원을 즉시 해제하지 않는다. 정상 토글의 다음 ON은 동일 context, images, descriptors, pipelines와 timeline semaphore를 재사용한다. Timeline 값 및 input parity는 되감지 않는다.

현재 API는 유한 fence 대기로 GPU 작업을 완료한 뒤 반환하는 **동기 방식**이다. 워밍업을 세 번 한꺼번에 수행하는 지연은 분산했지만 각 원본 프레임에는 한 번의 warmup 비용이 추가된다. 비동기 워커나 무중단 프레임 속도를 보장하지 않는다. 생성 프레임과 원본의 출력 간격 조절은 Cemu 어댑터가 담당하며 실제 성능/지연은 GPU 실행 검증 대상이다.

## Reset과 자원 재생성의 구분

- `reset_history`: CPU flag만 설정한다. 다음 ON 호출에서 소유한 중간 이미지만 clear하고 입력을 다시 채운다. 외부 host 이미지는 clear하지 않는다.
- `prepare_context`: 건강한 기존 자원이 있으면 history가 무효여도 그대로 반환한다. 이 API는 history를 warmup하거나 프레임을 소비하지 않는다.
- 크기/출력 형식 변경: Cemu의 기존 이미지 사용 완료 및 module drain/destroy 성공 후 해당 context와 host images를 다시 만든다. Module pipeline은 유지한다.
- 같은 크기의 swapchain 재생성 또는 acquire 실패 후 재개: host가 history reset을 요청한다.
- 제출 오류/timeout: poisoned 상태로 자원을 보관한다. 완료되지 않은 자원을 재사용하지 않는다. 성공적인 drain 후 명시적인 reset은 다음 사용 때 context 재생성을 허용한다. Device loss는 모듈 재시도로 복구하지 않는다.
- 종료: 호스트의 이미지 소비 및 module 작업 완료를 확인하고 context, module 순서로 해제한다.

`get_resource_stats`는 `context_builds`와 `history_clears` 누계를 별도 구조체로 제공한다. 실제 토글 시험에서 크기 변경이 없으면 context_builds가 증가하지 않고 history_clears만 증가해야 한다. 새로운 상태/API의 null, DLL 실패, OFF 우회, finite readiness wait, device-loss 계약은 GPU 없는 C/C++ 테스트에서 확인한다. 자원 재사용, warmup 이미지 품질, 실제 출력과 프레임 간격은 GPU 시험으로 확인해야 한다.

기존 `generate`는 한 호출에서 세 번 warmup하는 동작을 유지한다. 같은 history 구간에서 `generate`와 `generate_step`을 섞지 않는다. Cemu 시험 어댑터는 `generate_step`만 사용한다.
