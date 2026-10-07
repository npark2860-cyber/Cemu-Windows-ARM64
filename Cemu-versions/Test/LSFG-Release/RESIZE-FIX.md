# LSFG 창 전환 수명 수정 시험본

**후속 사용자 실행 결과: F11 반복 전환 통과.** 2026-09-29 사용자가 “F11연타해도 멀쩡해”라고 보고했다. 보존한 `evidence/user-manual-20260929-0624-resize-log.txt`에서06:12:59~06:24:44 사이 재생성 시작24/완료24, overlay replay 생략3회와 각각 다음 warmup 및 생성 재개를 확인했다. 해당 Vulkan/LSFG fatal 오류0, 생성18,845회 및 renderer shutdown 기록. 이 실행의 preset은Quality100이며 프로세스 exit code는 미수집이다. 이번 반복 전환 회귀 시험의 통과 근거이며 FPS UI/모든 프리셋/고른 scanout 또는 이전 종료의 정확한 원인까지 입증한 결과는 아니다. 아래는 수정 시점의 분석과 검증 절차다.

사용자가 TUNE의 프리셋은 유지해 달라고 했고, 전체화면에서 창 모드로 돌아갈 때 종료됐다고 보고했다. 2026-09-29 05:53:47 로그 마지막은 `failed to submit command buffer. Error -3`이다. Vulkan의 `VK_ERROR_INITIALIZATION_FAILED`이며 `VK_ERROR_DEVICE_LOST`(-4)로 해석하지 않는다. Windows Application 1000/1001의 직전 2시간 조회에서 대응하는 Cemu 항목은 발견하지 못했다. 실제 프로세스 종료 코드는 수집하지 않았다.

증거: `evidence/user-manual-20260929-0553-tune-crash-log.txt`, SHA256 `91af3f419da08969a88ee3fe4945eb46d05321a64eda1ae759cfa8db6f529169`.

## 확인한 코드 결함과 수정

LSFG는 생성 화면을 present한 뒤 다음 swapchain 이미지를 acquire하고 원본 화면을 복원한다. 그 사이 창 크기가 바뀌면 `RecreateSwapchain()`이 ImGui Vulkan 자원을 종료하고 재생성한다. Cemu의 실제 ImGui backend인 `src/imgui/imgui_impl_vulkan.cpp`의 `DestroyDeviceObjects()`는 글꼴 이미지와 view를 파기한다. 이전 ImDrawData의 TextureId는 그 글꼴 이미지에 연결된 descriptor를 참조한다. 새 ImGui 글꼴 업로드는 다음 `ImguiBegin()`에서 이루어진다.

기존 코드는 `VkSwapchainKHR` 값이 달라졌을 때만 예전 ImDrawData 재사용을 건너뛰었다. 파기 후 같은 핸들 값이 재할당될 수 있어 자원 수명 판정으로 충분하지 않다. 이 경우 폐기된 글꼴 자원을 간접 참조하는 명령을 제출할 수 있다. **이 결함은 코드에서 확인했지만 이번 사용자 종료가 이 경로였다는 런타임 증거는 아직 없다.** 기존 로그에 재생성/overlay replay 구간 표식이 없었다.

- main swapchain의 자원 세대 번호를 추가한다. GPU 작업을 drain한 후, ImGui 자원을 파기하기 전에 증가시킨다. 핸들 값과 크기가 같아도 증가한다.
- 재생성 시 LSFG 이전 프레임 유효성 및 생성 대기를 취소하고 다음 capture에 history reset을 예약한다. 복원에 필요한 host 이미지와 current 인덱스는 유지한다. 크기가 달라 host 이미지 교체가 필요하면 기존 `lsfgEnsureContext()`가 Cemu 명령 완료를 확인한 후 교체한다.
- 생성 present 전후의 세대가 다르면 원본 화면은 새 swapchain에 복원하되 이전 overlay draw list는 재사용하지 않는다. 다음 일반 프레임에서 새 글꼴 자원으로 overlay를 그리며 LSFG는 다시 warmup한다.
- 재생성 시작/완료 및 overlay 재사용 생략을 `[LSFG-SURFACE]`로 기록한다. 다음 실행에서 종료 시점을 구분하기 위한 표시다.
- Quality/full, Performance/full, Performance/75% 프리셋과 기본값은 유지한다. 모듈 계산, 2X 비율 및 출력 해상도는 변경하지 않는다.

## 생성 프레임을 포함한 FPS 표시

사용자의 추가 요청에 따라 주 화면 overlay와 창 제목의 FPS에는 LSFG 원본+생성 프레임을 포함한다. 기존 `[LSFG-PERF]`의 약2초 측정 창에서 성공 또는 SUBOPTIMAL로 받아들여진 main-window present 수를 시간으로 나눈 값을 그대로 사용한다. 예: `FPS: 60.00 (LSFG 2X)` / `Native: 30.00 FPS`. 원본 FPS는 기존 Cemu game frameCounter로 계산하며 게임 타이밍·draws/frame 계산은 바꾸지 않는다.

생성 warmup은 원본 present만 세고, 실패한 present는 세지 않는다. OFF/실패/미지원 API와 GamePad 창은 기존 원본 FPS를 표시한다. ON/크기/프리셋 전환으로 측정을 새로 시작하면 첫 완전한 약2초 구간이 생길 때까지 원본 FPS를 표시한다. 전환 시 짧은 구간의 강제 로그 flush는 UI 값으로 게시하지 않는다. 창 제목은 기존 약1초 갱신 주기를 유지한다.

이는 출력 요청 처리 빈도이며 화면의 실제 scanout 빈도나 고른 출력 간격을 증명하지 않는다. 기존 cadence 문제는 별도 검증 대상이다. FPS getter와 UI 문자열 생성은 기존 렌더 스레드에서 실행되며 wx에는 완성된 제목 문자열을 전달한다.

## 검증과 전달

시험 파일은 `runtime-experiment/Cemu-lsfg-resize.exe`, 창 제목은 `[LSFG RESIZE]`로 구분한다. 이전 TUNE 등 시험 파일은 보존한다. 빌드/CPU 검사 결과와 해시는 `evidence/resize-build-manifest.json`에 기록한다. 기존 모듈의 CPU 계약 검사는 실제 Vulkan swapchain/ImGui 수명을 실행하지 않으므로 창 전환 해결의 증거로 간주하지 않는다.

에이전트는 Cemu/GPU 실행이나 화면 입력을 하지 않았다. 에이전트가 실행하려면 먼저 사용자에게 사용 시간을 요청하고 승인을 기다려야 한다. 사용자는 원하는 시간에 직접 시험할 수 있다. 수동 확인 순서는 LSFG OFF에서 창↔전체화면, ON에서 창↔전체화면, 창 크기 변경, OFF→프리셋 변경→ON이다. 문제를 보고한 Performance/75%부터 같은 게임 장면에서 확인하고, 각 전환 뒤 원본 화면과 overlay가 돌아오며 LSFG가 다시 생성하는지 확인한다. 재발하면 재실행 전에 `portable/log.txt`를 보존한다.

실제 GPU 재검증이 끝나기 전에는 강종 해결로 확정하거나 네 유지 버전에 이식하지 않는다.
