# LSFG 작업 상태

## 2026-09-29 실제 NPU 세 단계 실행 성공 / FP16 속도 미달 — 최신

- async 시간질문에 사용자 “지금 진행해”로 명시승인.06:44:09~06:44:47에 NPU단독3단계실행. UI/Cemu/GPU런치없음. 종료후컴퓨터사용가능하다고알렸으므로추가NPU/GPU시험은새시간승인받을것. 현재진행중프로세스없음.
- `Test/NPU-Experiment/evidence/first-htp-results.json`에요약. 원본run: `htp-smokequantized-20260929-064409-810`, `htp-smokefp16-20260929-064424-693`, `htp-anvil-20260929-064439-619`. 각run.json/statusHTP_EXECUTION_VERIFIED/exit0. QnnHtp명시+CPUfallback금지+ORTkernel provider모두QNN. 작은모델각24kernel(1first+3warm+20측정), ANVIL14kernel(1+3+10). 실제QNNdriver c_interface및QNNacceleratorUS/cycles profile도보존.
- 작은UINT8Conv32×32산술oracle 최대오차0.5 PASS,FP16floatI/O최대0.00041355 PASS. 두작은모델평균9.888/10.451ms는상세profiling/호출비용포함이며작은kernel순수NPU시간으로사용하지말것.
- 원본ANVIL1080p_FP32모델을FP16HTP경로로실행성공. shape/pad/crop정리를ORT가해결했고CPUfallback없음. 합성입력출력유한값확인만;보간화질검증아님.10회Run평균128.937ms,p95131.046,min127.984,max131.046;세션생성4310.109ms,첫추론181.793ms,입력준비19.609ms.49,766,400byte입력/24,883,200byte출력. balanced전력/상세profiling.
- ANVILQNNprofile첫4개제외10측정: Accelerator(excludingwait)평균97.081ms,Accelerator97.562ms,QNNaccelerator119.272ms,RPC119.816ms,QNNexecute123.433ms. 중첩구간이므로더하지않는다. layout/형식변환포함될수있고CNN순수MAC시간아님. NPU내부만으로도33.3ms생성예산을넘으므로로그/호스트호출만줄여해결될상태아님. GPU↔NPU전송/실제Cemu동시부하/cadence는아직미측정.
- 다음후보는대표게임프레임기반INT8양자화,모델경량화및입출력/정렬비용절감. 현재FP16을Cemu에붙이거나NPU를프레임생성성공으로홍보하지않는다. 기존GPU기준본과네유지버전미변경. 사용자평가대로현재GPU기준본은보존하고NPU는독립실험유지. 준비시점manifest의device_executed=false는당시상태이며이실행증거로갱신됨.

## 2026-09-29 NPU 독립 실험 준비 완료 — 사용자 실행 시간 승인 대기

- 사용자: 현재 상태도 정식 승격해도 충분하지만 NPU에 도전하고 싶다고 요청. 현재 GPU RESIZE를 승격 가능한 기준본으로 보존하고 `Test/NPU-Experiment`에 독립 probe를 만들었다. 네 버전 변경/승격은 이번 턴에 하지 않았다. Cemu 소스·바이너리 변경 없음; resize manifest의 소스파일/EXE hash 일치 확인 및 manifest 복사.
- Windows ARM64/X1E80100, DriverStore qcnspmcdm8380의 V73 stub/FastRPC 파일 발견. CIM 조회는 sandbox 접근 거부였으며 registry/파일 존재만 확인했다. 장치 동작 증거는 아직 없다.
- Microsoft.ML.OnnxRuntime.QNN1.24.4 공식 NuGet96,584,324bytes 다운로드, SHA e4d6eabb9e503d4f3c78494fc9400f02509b2ee315d9f707644a174ece8da17f. 포함 QAIRT2.42.0.251225135753_193295. WindowsARM64부분/헤더/고지만 실험폴더에 추출; systemSDK/driver/PATH변경없음. runtime에서QnnCpu/GpuDLL 제외. 원본 ANVIL model3,441,349bytes hash65e871…(기존검토와일치), 라이선스보존. Downloads JSON 있음.
- 도구 `Test/NPU-Experiment/runtime/npu-probe.exe` ARM64 SHA59517848f33dfbe26a9fe0f5208c41a227471949d2f7981c0f867bcb992602d9. build-probe.cmd MSVCARM64; 최종빌드exit0/warning없음. 모든runtimePE가ARM64인지확인. manifest `evidence/probe-build-manifest.json`.
- QnnHtp명시, CPUfallback금지, I/OquantizationCPUoffload0,FP16활성,balanced전력,상세QNN/ORTprofile. 작은UINT8QDQ및FP32Conv의산술oracle검사,ANVIL합성입력유한값검사. 1first+3warmup+지정횟수Run. 평균p50p95walltime/첫추론/입력준비/세션생성/출력tensor/exitcode기록. GPUtransfer/게임운동추정/화질/실제Cemu성능미측정. Async/CemuNPUbackend아직미구현.
- `scripts/prepare_models.py` ONNX체커3모델PASS(추론없음), `test-profile-gate.ps1` CPU합성profile7검사PASS, PSsyntaxPASS. `run-probe.ps1` 기본preflight는hash검사만하고device실행안함. 실제실행은 `-Run -Stage SmokeQuantized`,성공시SmokeFp16,성공시Anvil(-Iterations10). NPU성공판정은ORTprofileQNN커널존재/다른provider없음/누락provider없음과Htp설정/fallback금지를함께확인.
- **NPU/GPU/Cemu 실행을 아직 하지 않았다.** async질문으로 약2~3분 NPU단독검증 시간승인 요청(작은QDQ→FP16→ANVIL,화면조작/Cemu실행없음). 사용자 답변이 오기 전 Run 금지. 강제종료/watchdog없음. 실제세션준비가길면진행상황보고.
- Python번들 `C:/Users/angel/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`는x64 3.12.14. 초기pip--target의 `python-tools`는이동된하위폴더ACL때문에sandbox에서읽기거부. 권한변경/삭제하지않고,동일공식wheel을다운로드해기본sandbox에서 `model-tools`로풀어사용했다. onnx1.20.1/numpy2.5.3/protobuf7.36.2/ml_dtypes0.6.0/typing_extensions4.16.0;외부runtime수정없음. 원본ANVIL입력고정출력symbolic이라ORTshape/상수정리및HTP지원실행검증필요. 참고 README에단계/제약/출처정리.

## 2026-09-29 사용자 F11 반복 전환 시험 통과 — 최신

- 사용자 보고: “F11연타해도 멀쩡해”. 에이전트는 실행/입력 없이 현재 로그를 읽고 `Test/LSFG-Release/evidence/user-manual-20260929-0624-resize-log.txt`와 분석 JSON에 보존했다. 로그 SHA256 `7fdd34f2fdd01ba91a709c5767bf2577db2307abe9fc5bc1418d69599c8d8d0c`. 현재 RESIZE EXE 해시 ced1fa7b… 일치 확인.
- 실행 로그06:12:59~06:24:44, main swapchain 재생성 시작24/완료24, old overlay replay 생략3회. 세 보호 경로 각각 다음 warmup 및 생성 재개 로그 확인(06:19:26,06:19:35,06:24:43). Vulkan fatal submit/LSFG failed 기록0. 마지막 Shutdown captured18894/generated18845 및 Resources context_builds23/history_clears15 확인. 프로세스 exit code는 미수집이므로 renderer shutdown만 확인된 상태다.
- **이번 사용자 실행 범위에서 F11 반복 전환 회귀 시험 통과로 기록한다.** 모든 context preset은Quality100이었다. Performance100/75별 반복 전환, FPS 표시의 시각적 확인, 실제scanout/cadence와 동일장면 성능 A/B를 이 로그로 검증한 것으로 확대하지 않는다. 이전 TUNE 종료가 정확히 핸들 재사용 때문이었다는 직접 증명도 아니다.
- 프리셋과 현재 RESIZE 소스/바이너리 변경 없음. 네 유지 버전 반영은 종합 검증 조건에 따라 계속 보류. 에이전트 실행에는 사전 시간 승인 필요.

## 2026-09-29 RESIZE + 생성 포함 FPS 시험본 완료 — 최신

- 사용자는 프리셋 유지에 동의했고 TUNE에서 전체화면→창 모드 전환 시 종료를 보고했다. 이후 NPU 기대감을 표시했고, FPS 표시도 생성 프레임을 포함하도록 요청했다. NPU 작업으로 창 전환 수정을 대체하지 않았다.
- 사용자 로그 `Test/LSFG-Release/evidence/user-manual-20260929-0553-tune-crash-log.txt` 보존(SHA256 `91af3f419da08969a88ee3fe4945eb46d05321a64eda1ae759cfa8db6f529169`). 마지막05:53:47 `failed to submit command buffer. Error -3` = VK_ERROR_INITIALIZATION_FAILED. DeviceLost(-4) 아님. 직전2시간 Application1000/1001 조회에서 대응 Cemu 기록 없음. 프로세스 exit code 미수집. Performance75 1440p 실행 기록이며 정상 종료 검증으로 간주하지 않는다.
- 확인한 코드 결함: 생성 present 뒤 acquire에서 swapchain/ImGui가 재생성되면 이전 draw data의 font descriptor가 이미 파기된 image/view를 참조할 수 있다. 기존 raw VkSwapchainKHR 값 비교는 핸들 값 재사용을 감지하지 못한다. **이번 강종의 실제 원인이라는 재현 증거는 아직 없으며 의심 경로 수정이다.**
- main swapchain generation을 ImGui 파기 전 증가시키고 모든 main 재생성에 history reset을 예약한다. 원본 host 이미지와 current index는 복원까지 보존한다. 생성 present 전후 세대가 다르면 원본 복원 후 old overlay replay를 생략한다. 다음 capture에서 기존 drain/자원 교체와 warmup 경로를 따른다. `[LSFG-SURFACE]` 재생성 시작/완료/overlay 생략 로그 추가.
- 주 화면 overlay/창 제목은 accepted real+generated presents의 약2초 집계 FPS를 표시하고 기존 Native FPS를 병기한다. 정상2X면 원본30+생성30→표시60. 실패 present 제외, partial forced flush 게시 안 함. ON/resize/preset 첫 완전한 측정 창 전에는 원본 표시. OFF/실패/미지원 API/GamePad는 기존 원본 FPS 유지. game frameCounter와 게임 타이밍은 변경하지 않는다. 실제 scanout/고른 cadence 증거가 아니다.
- 최신 EXE `Test/LSFG-Release/runtime-experiment/Cemu-lsfg-resize.exe`, 제목 `[LSFG RESIZE]`, ARM64 29,761,536 bytes, SHA256 `ced1fa7b1291dd29fec78188165651634e6e8a9a07025afc2904e35b63737504`. PDB `evidence/resize-build-symbols/Cemu_release.pdb` SHA256 `5391acc0b89bbb50a1ddde219a15946597ad326926486d098a2bacf5a67cc7f5`. Manifest `resize-build-manifest.json` 및 runtime `LSFG-RESIZE-BUILD.json`. 기존 TEST/PERF/PROFILE/TUNE 네 시험 EXE 해시 보존 확인.
- 최종 `resize-fps-build.log` exit0, `resize-fps-cpu-tests.log` 2suites/109checks/0failures/GPUsubmissions0, `resize-fps-diff-check.log` PASS. 기존 CPU 모듈 계약 검사는 swapchain/ImGui/UI를 실행하지 않는다. 최초 resize-only build도 통과했으나 전달 파일은 FPS까지 포함한 최종 빌드이다. 진행 중 프로세스 없음.
- **실제 Cemu/GPU/UI 실행은 하지 않았고 강종 해결·FPS UI 실측은 사용자 재시험 대기.** 에이전트 실행에는 사전 시간 승인 필요. 네 유지 버전은 계속 미적용. Quality100/Performance100/Performance75 및 시작OFF/기본Performance100 유지. 자세한 근거와 시험 순서는 `Test/LSFG-Release/RESIZE-FIX.md`.

## 2026-09-29 TUNE 계산량 비교본 전달 준비 완료 — 최신

- 사용자 “조금 더 당길 수 있어?”에 따라 기존 backend Performance 셰이더와 flow scale 선택을 연결했다. 사용자가 “2개 사이에1개가100%?”라고 질문해 **2X는 삽입 배수,100%/75%는 내부 운동 추정 해상도**라고 설명했고 이해했다. UI도 `Full motion resolution` / `75% motion resolution`로 명확히 변경했다.
- 새 EXE `Test/LSFG-Release/runtime-experiment/Cemu-lsfg-tune.exe`, 제목 `[LSFG TUNE]`, ARM64 29,757,952 bytes, SHA256 `5461c3586c93d79620befa25e5d627ca93dc2b16c7b9a6e4a8fb2fac06036b15`. 기존 TEST(e2f789…), PERF(d58032…), PROFILE(6312fd…) 세 EXE를 해시 확인 후 보존. PDB는 `evidence/tune-build-symbols/Cemu_release.pdb`, manifest `evidence/tune-build-manifest.json` 및 runtime `LSFG-TUNE-BUILD.json`.
- 순정 Release c5205cc 기반. Config의 session-only lsfg_preset 기본1=Performance100, lsfg_enabled 기본OFF. Graphics의LSFG processing:0 Quality/full(기존),1 Performance/full(기본),2 Performance/75%. 변경은OFF에서만 UI 허용, 다음ON에서 이전Cemu 작업 완료확인→context교체→3회warmup. 같은모드단순토글은기존자원재사용. 앱 재실행하면Performance/full기본값으로 돌아간다. 저장된원본설정/네유지버전에적용안함.
- 모듈 ABI1기존구조불변, additive `LsfgCemuContextTuning` 및 `lsfg_cemu_set_context_tuning` 추가. 준비전CPU전용,준비된GPU자원있으면BUSY; 잘못된bool/scale/layout/minextent거부. 원래호출자기본은Quality100유지. Backend `flow` 인수는역수이므로100.0/percent전달. 출력은전체해상도유지. 아주작은창75%내부축128미만이면adapter100%로보정하여로그. 모드/크기전환시계측구간분리,로그preset/effectiveflow추가.
- `tune-build.log` exit0, 최종 `tune-build-verified.log` no work to do exit0. CPU CTest2 suites/109checks/0fail/GPUsubmissions0 PASS(`tune-cpu-tests.log`);diffcheckPASS. 초기에빌드진행중돌린CPU로그94개는이전바이너리결과였고최종109개결과로덮어써확인했다. 진행중빌드없음.
- **TUNE 실제GPU/화질/성능 미검증.** PROFILE 사용자실행결과를새Performance모드검증으로간주하지말것. 에이전트는Cemu/GPU실행이나UI조작안함. 사용자직접시험선호;에이전트실행에는사전시간승인필수. 새옵션은계산량/화질tradeoff이며비동기생성이나고른presentpacing완성본아님. 네유지버전적용계속보류. 자세한사용방법 `Test/LSFG-Release/TUNING.md`.

## 사용자 PROFILE 직접 시험: 크게 개선됐다는 피드백 및 계측 확인 — 최신

- 사용자가 “오 많이 좋아졌어”라고 보고했다. 에이전트는 실행/UI 조작 없이 `runtime-experiment/portable/log.txt`를 읽고 보존했다. **실제 로그 위치는 portable/log.txt**이며 runtime 루트가 아니다.
- 증거 `Test/LSFG-Release/evidence/user-manual-20260929-0528-profile-log.txt`, 분석 JSON `user-manual-20260929-0528-profile-analysis.json`. Init c5205cc, X1-85, timestamp48bits/52.083332ns. 05:22:42 startup OFF, 05:22:51 ON, 05:28:28 renderer shutdown. Captured9834/generated9818/dispatches983000/resets4/context_builds4/history_clears4. 실제 process exit code 미수집. 이전 GPU 미실행 기록은 이 사용자 실행으로 갱신됨.
- Warmup0/1.8~2.2초/유효 GPU query ON 창만 집계. **1429x992** 25창/50.52초: 원본 가중평균41.34(장면/초기 구간 섞임), 중앙37.60, 최소31.98. 마지막 두 온전한 창은 원본31.98/32.59, 생성 포함63.95/65.18 present requests/s. **2560x1440** 138창/278.56초: 원본 가중평균26.773, 생성 포함53.545 requests/s, 중앙26.96, 범위21.90~35.11, 30 이상은6창. 장면이 같지 않으므로 해상도만의 FPS 차이 또는 기존 버전 대비 정확한 개선율로 해석하지 말 것. OFF는 초기 로딩뿐이라 동일 장면 A/B 없음.
- GPU spans 가중평균: 작은 창 prepass1.538ms/generated3.078ms/input0.053/output0.054; 1440p prepass3.662/generated7.363/input0.164/output0.158. Module CPU wall 각각5.950/13.917ms, tail fence CPUwait5.650/13.647ms per sample. CPUwait와GPUspan은 중첩되는 비용이며 더하지 않는다. 실질적인 LSFG GPU 계산 비용이 크지만 GPU 전체 포화율을 입증한 값은 아니다.
- 실제 Cemu QueueSubmit CPUavg 약0.047/0.041ms, host submitgap0.055/0.052ms, GPU realend→prepassspan0.160/0.457ms. 큰 host submit 공백/queue mutex 점유가 주원인이라는 증거 없음. 같은 렌더 스레드의 최종 fence대기는 여전히 존재.
- Present 반환 간격4ms 미만이 1440p 구간7459회로 원본/생성 요청이 두 장씩 몰리는 패턴. 실제 scanout 측정이 아니므로 고른60Hz 달성으로 간주하지 않는다. CPU 렌더 thread에 sleep을 되넣지 않는 별도 pacing 설계가 후속 과제.
- 작은 창에서 사용자 체감 개선과30원본FPS 이상 구간 확인. 1440p 30FPS 지속 방어와 cadence/화질 검증은 남아 있어 네 유지 버전 적용은 계속 보류. 기존 바이너리는 보존. NPU는 미구현·미실행 후보이며 이번 개선은 GPU 경로 수정 결과이다.

## 2026-09-29 CPU/GPU 계측 빌드 완료 및 NPU 자료 검토 — 최신 상태

- 최신 시험 EXE: `Test/LSFG-Release/runtime-experiment/Cemu-lsfg-profile.exe`, 제목 `[LSFG PROFILE]`, ARM64 29,748,224 bytes, SHA256 `6312fdb0700b592fac02ca58e348334e1c0f85943707f7f384af75507a2180d7`. 기존 TEST(e2f789…)와 PERF(d58032…) EXE는 해시 확인 후 보존했다.
- 빌드 `evidence/profile-build-verified.log` exit0, CPU CTest 2 suites / 94 checks / 0 failures / GPU submissions0 PASS (`profile-cpu-tests.log`), diff check PASS. PDB `evidence/profile-build-symbols/Cemu_release.pdb`, manifest `evidence/profile-build-manifest.json` 및 runtime `LSFG-PROFILE-BUILD.json`. 최종 빌드와 테스트는 모두 종료됨.
- 추가 계측: Cemu real-frame GPU span, LSFG input/prepass/generated/output GPU spans, 실제 Cemu/module QueueSubmit CPU 시간, Cemu/module tail-fence CPU 대기, host capture-submit 반환→module 첫 submit gap, GPU real 끝→prepass 시작 span. GPU는 완료된 query만 읽고 profiling을 위한 completion wait는 추가하지 않는다. 실패/부분 기록 batch의 module query는 읽지 않는다. Warmup GPU는 정상 생성 평균에서 제외. unavailable은 N/A.
- **공용 queue mutex 없음**, 같은 renderer thread 호출 순서로 직렬화. `queue_mutex_hold=N/A(single_render_thread)`. 생성 마지막 CPU fence wait와 overlay 재사용 대기는 남아 있다. 비동기 backend 완성본 아님.
- **GPU real span은 순수 busy 시간 아님.** 프레임 공급 지연이나 timeline 공백 포함 가능. CPU/GPU submit 경계 span도 copy/dependency 포함하므로 실제 GPU idle이라고 부르지 않는다. accepted present 빈도/return gap은 scanout 계측 아님. 자세한 항목 정의는 `Test/LSFG-Release/PROFILING.md`.
- 사용자 최신 steering은 NPU 활용 검토. 제공 자료 `54pkp/lsfg-npu`, `54pkp/hexscale`, `NihilDigit/anvil`을 확인했다. `NPU-REVIEW.md`와 `evidence/npu-reference`에 소스·commit 기록. hexscale 실제 graphExecute 및 오프라인 midpoint 코드는 있으나 Windows x64 QNN CPU 검증/ARM64 Linux 빌드를 Windows ARM64 NPU 성공으로 오해하지 말 것. 게임 motion vector와 자동 삽입 present 미완성, 동기 GPU-host-daemon-host-GPU 복사. ANVIL은 decoder MV 전제, Cemu에 별도 motion 공급 필요. 최신 LSFG DLL shader를 QNN 모델로 바로 변경할 수 있는 구현 없음.
- 이번 작업에서 Cemu/GPU/NPU 실행 및 화면/입력 조작 없음. SDK/외부 runtime 설치 없음. 사용자가 직접 같은 장면·창 크기로 OFF15초/ON15초 비교할 수 있는 파일만 준비했다. 에이전트의 실행 시험에는 사전 시간 승인이 계속 필요하다. 성능 개선/30→60 성공은 아직 미검증이며 네 유지 버전 적용 보류.

## Queue 직렬화 및 계측 감사 — 사용자 질문에 대한 확인

- 사용자 요청 지표: Cemu real-frame GPU 시간, LSFG pre-pass GPU 시간, 생성 pass GPU 시간, generate CPU wall time, queue mutex hold, GPU completion wait, vkQueueSubmit CPU 호출 시간, real submit→LSFG submit 사이 idle.
- **현재 공용 queue mutex 자체가 없다.** Cemu VulkanRenderer.cpp의 vkQueueSubmit(2276) 및 vkQueuePresentKHR(3090), module의 command_buffer.cpp QueueSubmit(243), lsfg_cemu.cpp tail-fence QueueSubmit(349)는 직접 호출이다. 검색된 shader compilation/pipeline cache mutex는 queue mutex가 아니다. 렌더 스레드의 동기 호출 순서로 직렬화한다.
- VulkanRenderer.cpp 778/779에서 graphics 및 present 모두 graphicsFamily의 queue index0를 받는다. LSFG CreateInfo도 m_graphicsQueue를 전달한다. 같은 VkQueue를 공유한다. 현재 generate_step 직접 호출과 내부 finite WaitForFences가 렌더 스레드의 다음 작업을 막는다. mutex 장기 점유가 입증된 원인이 아니다.
- 계측 현황: generate_step CPU wall은 module_batch_avg로 기록. queue mutex hold는 0ms가 아니라 해당 없음. real/pre-pass/generated GPU timestamps 미구현. module completion wait 별도 시간 미구현(overlay_wait_sum은 별개). QueueSubmit 단독 호출 시간 미구현. submit 간 CPU gap 및 GPU idle 미구현. 이전 약11ms는 generate CPU wall time이며 독립 GPU timestamp 측정값이 아니다.
- 후속 비동기화 시 context/API 상태 직렬화와 VkQueue 외부 동기화를 구분해야 한다. 같은 VkQueue의 모든 실제 host queue 호출을 같은 lock으로 보호하고 GPU 완료 wait/워밍업/출력 타이머는 queue lock 밖에 둔다. GPU 간 의존성은 semaphore/barrier, slot 재사용은 완료 확인으로 관리한다. submit 간 CPU 공백만으로 GPU idle이라고 단정하지 말 것.
- 이번 감사에서 실행/화면 조작/성능 재시험은 없고 소스 변경도 없다. d58032… performance EXE가 최신이며 아직 사용자 실행 결과를 확인하지 않았다.

## 성능 비교 빌드 전달 준비 완료 — 최우선

- 사용자 목표를 **원본 30 FPS 이상 유지 → 생성 포함 60 FPS 및 고른 출력 간격**으로 확정했다. 사용자 직접 시험을 선호한다. 에이전트는 이번에도 앱 실행/GPU 테스트/UI 조작을 하지 않았다.
- 새 실행 파일 `Test/LSFG-Release/runtime-experiment/Cemu-lsfg-perf.exe`, 제목 `[LSFG PERF]`, ARM64 29,735,936 bytes, SHA256 `d58032bae08df5ee4ef3de14e0caf018aa4ebee8a0b010884261483ed1623146`. 기존 Cemu-lsfg.exe(e2f789…)와 기존 PDB는 해시 확인 후 그대로 보존.
- source의 최신 내용은 performance revision이다. 렌더 스레드에서 half-period sleep 제거. Cemu capture Submit 뒤 CPU fence 대기 제거(같은 queue의 입력 barrier와 최종 module fence가 동기화). module CopyInputs/Schedule/Output 정상 경로를 최종 fence 1회로 묶고 input/output command buffer를 별도로 만들어 pending command buffer 재기록을 방지했다. warmup 단계는 각각 마지막 fence로 완료를 확인한다. pendingGenerations 집계는 성공 drain 때만 반영.
- 안정성에 필요한 자원 수명/오류 drain/overlay 재사용 대기는 남겼다. 아직 **동기식 비교 빌드**다. sleep 제거로 두 present가 몰릴 수 있으므로 평균 60회/s만 보고 고른 60 Hz 출력이라고 말하지 않는다. GPU 계산 비용 자체는 그대로다.
- `[LSFG-PERF]` 로그: OFF/ON source/generated/accepted present requests/s, rejected count, module batch CPU 평균, capture submit/present host/overlay wait 합계, present 반환 간격 평균/최대 및 4ms 미만·33ms 초과 수. 실제 display scanout 계측은 아니다. 새 module batch 시간에는 이전 capture GPU 대기가 포함될 수 있어 구버전의 약 11ms와 직접 비교하지 말 것.
- 빌드 session58635 exit0. CPU CTest 2 suites / 90 checks / 0 failures / GPU submissions0 PASS, diff whitespace PASS. 로그 `evidence/lsfg-build-performance.log`, `lsfg-performance-cpu-tests.log`. `evidence/performance-build-manifest.json` 및 runtime의 LSFG-PERF-BUILD.json; PDB `evidence/performance-build-symbols/Cemu_release.pdb`. GPU/성능 개선은 **아직 미검증**.
- 사용자가 같은 장면·출력 크기에서 OFF15초→ON15초 유지하면 로그와 원본 카운터를 비교할 수 있다. 상세 `PERFORMANCE-REVISION.md`. run-lsfg-scenario.ps1도 새 파일명을 허용하지만 **에이전트 실행 전 시간 승인 필수**.
- 현재 진행 중 빌드/테스트 없음. 네 유지 버전은 계속 미적용. 테스트 결과가 아직 없으므로 성능 문제 해결 완료로 보고하지 말 것.

## 성능 회귀 지적 — 다음 작업의 우선순위

- 사용자가 패치 전 약 40 FPS, LSFG 사용 후 원본 카운터 약 20 FPS라고 보고했다. 기존 카운터가 원본만 세는 것은 맞지만 이것만 설명하면 실제 성능 하락을 놓친다. 원본 20 + 생성 20은 원본 40에 대한 성능 개선 성공이 아니다. 정확히 같은 장면/해상도/설정의 A/B 측정은 아직 없지만 사용자 회귀 보고를 해결해야 한다.
- 코드에서 LSFG capture 뒤 WaitCommandBufferFinished, 모듈 입력 복사/생성/출력 각각의 동기 tail fence 대기, 생성 present 후 추가 WaitCommandBufferFinished, 그리고 **동일 렌더 스레드에서 native period/2 sleep_until**을 확인했다. 다음 원본 프레임 렌더를 이 모든 단계가 지연시킨다. 설정의 VSync는 0이었다.
- 로그의 2560x1440 생성 API 시간 약 11.3ms는 사실. 기존 40 FPS를 25ms/frame으로 가정하고 추가 sleep 약 12.5ms를 더하면 약 48.8ms/frame ≈20.5 FPS로 내려갈 수 있다는 설명은 추정치이며, 실제 sleep/fence별 비용은 아직 계측하지 않았다. 표시만 2배 하는 변경으로 해결하지 말 것.
- 이번 확인에서는 코드/실행 파일을 변경하지 않았고 Cemu 실행·UI 조작도 하지 않았다. 다음 구현 우선순위는 렌더 스레드 직렬 대기와 출력 pacing을 분리/개선하고 비용을 계측하는 것. GPU 자체의 생성 비용은 남으므로 async로 옮기기만 하면 원본 40을 보장한다고 약속하지 말 것. 현재 상태는 생성 동작 확인, 성능 성공 아님. 네 유지 버전 반영 보류.

## 사용자 직접 실행 결과 — 이전의 GPU 미실행 기록보다 우선

- 사용자가 Cemu-lsfg.exe를 직접 시험했고 “잘 되는데 FPS 카운터가 1/2”라고 보고했다. 에이전트는 화면/입력 조작 없이 로그와 소스만 읽었다. 증거 `Test/LSFG-Release/evidence/user-manual-20260929-0335.json` 및 동명 로그.
- e2f789… 시험 EXE에서 startup 51 shaders/51 pipelines/generated=0, ON 뒤 3회 WARMING, generated=10,352 및 renderer shutdown 확인. 1280x720→1429x992→2560x1440→1429x992 자원 준비, 1440p FSR EASU+RCAS 활성. 1440p 생성 로그 약 11.2~11.9ms. Process exit code는 계측하지 않음.
- 카운터 원인 확인: LatteRenderTarget.cpp의 게임 frameCounter를 LattePerformanceMonitor.cpp가 FPS로 계산하고 Overlay 및 window title에 전달한다. LSFG 추가 SwapBuffer(true)는 이 frameCounter를 증가시키지 않는다. 보간 전 20 FPS이면 이 구조의 목표는 생성 포함 약 40회/s present이며, 실제 present/display 빈도는 아직 계측하지 않았다. FPS를 임의로 2배 하는 수정은 하지 않았다.
- 동일 크기 OFF→ON 반복 자원 재사용, 성공 present 빈도/cadence, full-frame 화질은 미검증. 네 유지 버전 이식은 아직 보류. 에이전트의 후속 실제 테스트는 여전히 사전 시간 승인 필요.

## 2026-09-29 자원/history 분리 구현 완료 — 최우선 상태

- 사용자가 제안한 시작 준비 → OFF 원본 → ON history warmup → 2X 설계를 시험 소스에 구현하고 빌드했다. **실제 GPU/Cemu 테스트는 아직 실행하지 않았으며 시간을 먼저 요청해야 한다.** 사용자의 컴퓨터 점유 승인 없이 실행/화면/입력 조작하지 않는다. 이번 진행 승인은 코드 준비에 사용했다.
- authoritative source는 `Test/LSFG-Release/source`. `module-work`와 `integration`은 최초 제작용 과거 초안이며 다시 복사하거나 `integrate-lsfg-release.py`를 재실행하지 말 것.
- 링크 실패 해결: CMake에서 LSFG와 CPU test targets를 Cemu와 같은 static CRT로 빌드. `build-lsfg-release.cmd` 성공, 로그 `evidence/lsfg-build-final.log`. 현재 빌드/실행 프로세스 없음.
- 시험 EXE `Test/LSFG-Release/runtime-experiment/Cemu-lsfg.exe`, ARM64, 29,731,328 bytes, SHA256 `e2f7899842c93c0bbee13ad9c23581b9f3a74595e80270725784bc8ae6d7ffa2`. 동일 폴더 PDB `Cemu_release.pdb`와 `LSFG-TEST-BUILD.json`; 증거 사본 `evidence/lifecycle-build-manifest.json`. 창 제목 `[LSFG TEST]`로 구분.
- `prepare`/`prepare_context` 사전 준비 후 정상 reset은 중간 이미지만 clear하고 자원·pipeline·monotonic timeline·parity를 유지한다. 실패로 poisoned된 context만 drain/reset 뒤 재생성. 별도 `generate_step` API는 첫 3회에 각 1회 warmup 후 WARMING을 반환하며 host output을 쓰지 않는다. 원본을 정상 present하고 다음 프레임부터 생성 결과 사용. 각 GPU 호출은 여전히 동기 fence 대기여서 성능은 미검증.
- resource counter 별도 API 추가(context_builds/history_clears). 건강한 토글 후 context_builds가 늘지 않는지 실제 시험 필요. acquire 실패/같은 크기 swapchain 재생성 때도 history reset 요청. 크기/표면 형식 변화는 context 재생성. 오류로 OFF되면 UI 체크 상태도 갱신.
- CPU 전용 CTest 2개 suite PASS, failure_contracts 90 checks / 0 failures / GPU submissions 0. 로그 `evidence/lsfg-cpu-contract-tests.log`. 실제 자원 재사용·GPU 화질·성능 검증이 아니다.
- 네 유지 버전의 소스/배포물/서브모듈 동일성 검증 모두 PASS: `evidence/baselines-after-lifecycle-build.log`. 유지 네 버전에는 LSFG를 반영하지 않았다.
- 다음 작업은 `Test/LSFG-Release/RUNTIME-TEST-PLAN.md`의 1차 OFF/ON/토글/정상 종료 시험(약 10~15분). **먼저 사용자 시간 승인**. `run-lsfg-scenario.ps1`의 unique scenario 이름과 Cemu-lsfg.exe 사용. 이전 stock/FSR crash 결과는 아래 기록을 보존. GPU 성공/화질 판정 전 네 버전 이식 금지.

## 2026-09-29 최신 재개 기록 — 아래 과거 기록보다 우선

- **사용자 지시: 테스트할 때 먼저 요청할 것. 사용자가 컴퓨터를 함께 사용한다. Cemu 실행, GPU 실행 시험, 화면 전환, 키보드·마우스 조작은 시간을 먼저 요청하고 명시적인 답을 받은 뒤 시작한다. 이전의 일반적인 테스트 승인을 앞으로의 데스크톱 점유 승인으로 간주하지 않는다.** 현재 실행 중 Cemu 프로세스 없음. 마지막 빌드도 종료됨. 새 테스트는 시작하지 않았다.
- 공식 Release 원본 설정의 야외 화면 83.91초 / 정상 종료 확인은 그대로 유효하다. 공식 Release의 변경 설정 시험 `official-fsr`는 실제로 18.09초 뒤 0xC0000005로 종료됐다. Windows WER도 같은 EXE, offset 0x1255b1c를 기록한다. LSFG 없는 바이너리이며 FSR 활성 로그 전 종료여서 FSR 자체가 원인이라고 확정할 수 없다. 강제 종료 없음.
- LSFG 없는 로컬 재빌드는 `rebuilt-original-settings`에서 야숨 타이틀 메뉴를 232.29초 유지하고 Alt+F4로 정상 종료했다. 플레이 검증은 아니다. experiment 설정을 원래 1920x1080 렌더 및 창 설정으로 복원했고 private MLC 경로만 유지했다.
- 테스트 복사본 controller0.xml에 키보드 보조 입력을 추가했다. Enter=A, Backspace=B, 방향키=D-pad, WASD=왼쪽 스틱. 원본은 미수정, 백업은 evidence/controller0-before-keyboard.xml. 다음 실제 게임 진입은 사용자 시간 승인 후 진행.
- LSFG 코드는 독립 source에 적용됐다. 시작 prepare/prepare_context, 기본 OFF, FSR 뒤 캡처, 생성/원본 프레임 출력, 토글 및 수명 관리 초안이다. 최종 source의 VulkanLSFG.cpp가 integration 초안보다 최신이며 resize/vsync 재생성 시 ImGui draw data 재사용 방지 가드가 추가됐다. integrate-lsfg-release.py는 재실행하지 말 것(비멱등).
- LSFG ON 빌드 session71523은 종료됐고 **링크 실패**다. Cemu는 MT_StaticRelease, 새 lsfg_cemu_arm64.lib는 MD_DynamicRelease여서 LNK2038/LNK1319 발생. 모듈 CMake 런타임 설정을 호스트의 static CRT와 맞춰 수정해야 한다. evidence/lsfg-build.log 참고. 아직 LSFG EXE 실행 검증 없음.
- build-lsfg-release.cmd에는 CEMU_ENABLE_LSFG=ON, LSFG_CEMU_BUILD_TESTS=ON, /Z7, /DEBUG:FULL /OPT:REF /OPT:ICF가 이미 추가됐다. Q:는 실행별 재매핑. Clang20 + MSVC14.51 헤더, 기존 vcpkg cache는 읽기 전용 재사용. 현재 재시작한 빌드/테스트 프로세스 없음.
- 후속 코드 점검: acquire 실패/동일 크기 swapchain 재생성으로 previousValid=false가 될 때 모듈 history reset도 필요할 수 있다. 실패 시 UI 체크 상태 동기화와 명확한 LSFG TEST 창 제목도 추가 검토. 모듈 기존 CTest를 실행하고 바이너리/심볼 및 해시를 별도로 보관한 후 사용자에게 실제 테스트 시간을 요청할 것.
- 유지 네 버전에는 적용하지 않았다. 원본 모듈의 동일 프레임 입력 경계 5픽셀 RGB 최대 오차 8도 미해결이므로 단순 생성 카운터만으로 전체 성공을 선언하지 말 것.

## 최신 확정 사항 (이 아래의 과거 경위보다 우선)

### 2026-09-29 작업 중단 시점

- 최초 LSFG 테스트 기준은 **순정 Release, SE 제외**. 새 작업은 `Test/LSFG-Release`에만 격리했다. 네 기준 소스/배포 파일은 그대로다.
- `runtime-stock/Cemu.exe`는 설치된 순정 d2d77e…와 동일. BOTW JP v208 야외 실제 플레이 화면을 확인하고 83.91초 후 Alt+F4 정상 종료(exit 0). 강제 종료 없음. 원본 EXE/설정/세이브 82개 해시 변화 0. 증거 `evidence/stock-observation.md`, `stock-run.json`, `stock-original-preservation.json`. 짧은 실행·렌더링·종료 확인이며 장시간 안정성 검증은 아니다.
- `Test/LSFG-Release/source`는 c5205cc 기반 로컬 `codex/lsfg-release` 클론. 공식 CI의 pre-e834, PS DEFAULT_VAL, FSR, branding 전처리 적용 완료. `evidence/official-release-preprocessing.patch` 참고. 기준 저장소와 Git 객체를 공유하므로 기준 저장소를 삭제하지 말 것.
- LSFG 적용 전 로컬 재빌드 성공: `runtime-experiment/Cemu-rebuilt-stock.exe`, SHA256 dde2a914eab3bca24c57fa73e447bf0cfb72c259819e4312fe717166dc9556cb. 이 재빌드의 실행 검증은 아직 안 했다. Clang20 + MSVC14.51 헤더 + MSVC 링커 + 기존 vcpkg static 캐시. MSVC14.52 헤더의 Clang22 요구 오류는 14.51 선택으로 해결. __udivti3 링크 오류는 compiler-rt builtins 경로 명시로 해결. `build-lsfg-release.cmd`와 빌드 로그 참고. Q: 별칭은 각 실행 세션에서 만든다.
- 원본 ZIP ABI v1을 `module-work`에 복사하고 OFF 상태 prepare/prepare_context API를 추가했다. `integration/VulkanLSFG.cpp`는 FSR/일반 출력 직후 캡처, 생성, ImGui 재사용, 생성/원본 출력 간격의 첫 구현이다. `integrate-lsfg-release.py`로 위 독립 source에 적용했다. **LSFG 변경은 아직 컴파일/런타임 검증 전**. 빌드 시 CEMU_ENABLE_LSFG=ON 필요(현재 cmd에는 미추가). 체크박스는 세션 기본 OFF, DLL 경로만 저장. 원본 모듈의 알려진 경계 픽셀 오차도 미해결.
- `runtime-experiment`는 복사 설정에서 BOTW 렌더 960x540, 창 1050x740, UpscaleFilter=4로 FSR 비교 조건을 만들었다. 설정/세이브/캐시는 독립 복사본이고 `mlc01/usr/title`만 원본 콘텐츠 junction(읽기용)이다. 재귀 복사/삭제에서 junction을 따라가지 말 것.
- `run-lsfg-scenario.ps1 -Name official-fsr -Executable Cemu-official.exe`: PID19940, exec session98544, 마지막 기록 RUNNING. 강제 종료 타이머 없음. 순정 d359c53/테스트 MLC 로그 확인. SE용 BowAdaptiveTrigger pack 미지원 assembler 명령으로 해당 pack 적용 거부 로그가 있음. FSR 활성/화면은 아직 확인하지 못했다.
- **물리 Escape로 사용자가 Computer Use를 중지했다. 도구의 이번 턴 추가 UI 조작 금지에 따라 중단했으며 다른 경로로 앱을 종료하지 않았다.** 다음 지시 후 재개할 때 실행 중 Cemu와 session98544 상태부터 확인할 것.
- 컴퓨터 조작은 `mcp__node_repl__js`의 `@oai/sky`. SKILL/guidance/confirmations/API 읽음, sky 초기화됨. 마지막 호출이 Escape 중지 응답이므로 이전 window/state 객체는 다시 조회해야 한다.

### 이전 기록 (상충 시 위 내용 우선)

- 이후 사용자가 `기존 SE는 폐기 해야해`라고 지시했다. `discard-old-se.ps1`을 실행해 설치 폴더 `Cemu_se.exe`와 정리 폴더의 동일 old EXE/ZIP 세 파일을 휴지통으로 이동했다. 삭제 전 SHA-256 일치를 검증했고 최종 `Cemu_se_test.exe`의 해시가 그대로임을 확인했다. 기록: `evidence/discarded-old-se.json`. 이전 SE는 다시 내려받거나 기준으로 사용하지 말 것.

- 사용자 실제 설치 폴더: `C:/Emulators/Cemu_arm64`.
- `Cemu.exe` = Release run 34314391691, SHA256 d2d77ee6961d9f834740ae450653a9f9235da27f43f3b82ed35ca7b2acc56abb.
- `Cemu_se.exe` = 이전 SE run 35399518440, SHA256 17231aa75f907d3804b27ee40762e9940c70443f33ca807157b80790fcb4d496.
- `Cemu-Diagnostics.exe` = Diagnostics run 34314435136, SHA256 5845e2b2a52bc777a3a03290ec3795f867947f7adfa2d9ac3caef6cf6dc7c6ba.
- **사용자가 `SE_Test가 최종`이라고 명시했다.** `Cemu_se_test.exe` = PR5 코드(9c0b899)를 빌드한 run 35507685980(e851c83), SHA256 e8791dbea63e85111c1b9a4feab98f31ca469b1802caf379aa5120cffa2dc9c8. 이를 네 버전 중 Release+SE의 최종 기준으로 사용한다. Draft/open PR 상태는 별도 사실로 보존하되 사용자 최종본 지정을 무시하지 않는다.
- `select-final-se.ps1`로 새 로컬 정리 폴더를 조정했다. `Release+SE/source`는 현재 PR5 HEAD9c0b899, `Release+SE/binaries/run-35507685980`은 최종 SE. 이전 원격 Release+SE 소스240b는 `Release+SE/history/source-240b52c853f3`로 보존. 이전 SE 배포와 Test 스냅샷도 보존.
- catalog.roles는 현재 정확히 네 개. Test는 고정 기준이 아님. `historical_snapshots`에 이전 Test/SE 기록이 있다.
- 최신 `Verify-Versions.ps1` 4개 PASS. 작업 중 다운로드/clone/검증 세션 없음. 설치 폴더 원본 파일은 모두 읽기만 했다.
- 기준 정리와 최신성 조사는 완료. 새 LSFG 구현/빌드/실게임 테스트는 아직 시작하지 않았다.
- 다음에 UI 테스트를 시작하면 computer-use 스킬 사용을 사용자에게 알릴 것. SKILL, guidance, confirmations는 이미 읽었다. node_repl 도구는 `mcp__node_repl__js`로 발견했으나 sky 초기화는 아직 안 했다. API 참조는 읽기 필요.

## 사용자 목표

- ARM64 LSFG 모듈을 Cemu에 통합한다.
- 렌더러 시작 때 준비하고, 체크박스 OFF는 원본 패스스루, ON은 프레임 생성.
- FSR 후처리 이후에 적용한다. FSX는 FSR의 오타라고 사용자 확인.
- 실제 테스트에 성공하면 릴리즈, 릴리즈+SE, 진단, 진단+SE의 네 기준 버전에 LSFG 변경만 통합한다.
- Test는 일시적인 실험 역할이다.
- 사용자 정정: 최신 SE 작업은 로컬 파일이 아니라 GitHub PR #5다. 경로 질문은 해결됐다.
- 이후 변경이 있는지 확인하고 혼란을 줄여 달라고 했다. 최신 SE 소스/빌드/런타임 검증을 구분하여 README 상단에 정리 중이다.

## 완료한 작업

- 네 기준 소스와 참고용 Test 소스, 재귀 서브모듈을 각 `source/`에 받았다.
- 각 역할의 최근 성공한 CI 배포물을 `archives/` 및 `binaries/run-번호/`에 받았다.
- GitHub ZIP digest, 추출 파일 SHA-256, PE ARM64, 브랜치/HEAD/remote/서브모듈 상태 확인.
- `Verify-Versions.ps1`에서 5개 모두 PASS. Git for Windows의 POSIX helper 경로 문제를 피하기 위해 서브모듈 커밋은 네이티브 git 명령으로 재귀 확인한다.
- 이전 소스, 빌드, 설정, 저장 데이터는 수정하거나 삭제하지 않았다.
- 새 게임 실행, LSFG 구현, 네 기준 버전 코드 통합은 아직 하지 않았다.

## 정확성 관련 발견

- 기존 `../Cemu-release`는 이름과 달리 실제 `Release+SE` 브랜치이며 최신 원격 HEAD와 같다.
- `../source-review`는 `codex/lsfg-cemu-renderer`, HEAD `c5205ccbc8ffe41129fbe921b5420a79ff283216`이며 미커밋 LSFG 변경이 있다.
- 기존 LSFG 실험 EXE `../source-review/bin/Cemu_release.exe`: SHA-256 `f2f4009f4ea75923e642375a9ae25a10c0a50a56c6734e25d1bc8ea748be0cf5`.
- 공식 Release CI는 소스에 pre-e834 호환성, PS DEFAULT_VAL, FSR1 EASU/RCAS, branding 패치를 빌드 전에 적용한다. 현재 source-review에는 FSR 구현이 확인되지 않았으므로, 공식 빌드 구성 재현 여부를 먼저 조사해야 한다. 이 사실만으로 이전 강종 원인을 확정할 수 없다.
- 원격 Release+SE 최신 소스와 최근 성공한 build/release-se-once CI 실행 파일에는 코드 차이가 있다. 최신 로컬본으로 대체하지 말 것. CI 이름과 artifact 이름은 stock Release와 같으므로 branch/run/commit으로 식별한다.
- 과거 Lossless Scaling 작업의 `build/layer-stage3-cemu-attempt1.execution.json`은 새 Release 배포 EXE와 같은 SHA-256 `d2d77ee6961d9f834740ae450653a9f9235da27f43f3b82ed35ca7b2acc56abb`를 기록하고 있다. 그 시도에는 LSFG layer_enable=1, timed_out=true, 30초 시간이 기록돼 있다. 이것을 자연 발생 Cemu 크래시라고 단정할 수 없다. 다른 이전 실행을 입증하는 자료도 아니다.

## 모듈 제약 / 설계

- 첨부 ZIP: `C:/Users/angel/Documents/ChatGPT/Lossless Scaling ARM64/build/lsfg-cemu-arm64-windows-arm64-20260928.zip`.
- C ABI v1, Cemu의 VkDevice/compute-capable queue를 빌리는 동기 compute 모듈. present/cadence는 호스트 담당.
- SDR RGBA8_UNORM, 2X, FP32, Quality 고정. 최소 각 축 128.
- create/create_context는 CPU 메타데이터만 만든다. 첫 ON generate에서 DLL 검증/셰이더/GPU 자원 준비 및 내부 3회 워밍업.
- ON/OFF와 reset은 다음 generate에서 GPU context를 재구성하게 한다. 시작 시 준비를 분리하려면 prepare API 및 자원/이력 수명 분리가 필요.
- OFF generate는 GPU 작업과 기다림 없음. Cemu의 OFF 경로도 추가 복사를 피할 것.
- 이전/현재/출력 host 이미지, GENERAL layout, transfer usage, 외부 직렬화 계약 준수.
- 제출 후 timeout은 이미지와 자원을 보존하고 drain 완료 확인. 무조건 즉시 재사용/삭제/원본 복귀하면 안 됨.
- ON 화면 경로 제안: game → FSR(EASU+RCAS) → LSFG → 일정한 원본/생성 출력 간격 → Cemu overlay → present. 게임 내부 HUD는 분리되지 않음.
- 검증표에는 실제 Cemu 통합 미검증 및 동일 이미지 입력의 경계 5픽셀 RGB 최대 오차 8이 기록돼 있음. 성공으로 보고하지 말 것.

## 후속 진행 원칙

1. 사용자 지정 PR #5의 소스와 대응 CI 빌드를 등록한다. PR은 Draft/open이고 test_SE 대상이다. 정식 Release+SE 브랜치와 혼동하지 않는다.
2. 정확한 원본 및 빌드 전처리를 기준으로 독립 LSFG 테스트 환경을 구성한다.
3. OFF/ON/토글/크기 변경/종료를 실제 실행과 출력 증거로 검증한다. 인위적인 시간 제한 종료와 앱 크래시를 구별한다.
4. 성공 후 네 버전에 각각 LSFG만 반영한다. 임의 진단/실험 코드를 릴리즈에 섞지 않는다.

## PR #5 최신성 확인 결과

- PR #5 source HEAD: `9c0b899eb31792353909ac7ff81ed42b2dd7f8fa`, 2026-09-20 11:20:30 UTC.
- 이어지는 직접 자식 `e851c8377c2c0fbcdc9042cf3971f60f0395d78b`는 빌드 workflow만 바꾼 carrier다. source diff는 `.github/workflows/final-adreno-compat-arm64.yml` 한 파일뿐이다.
- `build/test-se-once`의 run `35507685980` SUCCESS. artifact `10603854428`, `cemu-arm64-test-se-astra`, SHA-256 `2ff370b000729a95b5355f40f545e32a8ef90b6240928bc964e7f1224715c50a`.
- 전체 최근 CI 목록에서 이 run이 최신이다. 전체 PR 목록에 #5 이후 PR은 없으며 관련 기준 브랜치 HEAD들도 그 이전 상태다. PR5 및 로컬 generic-voice-haptics는 같은 HEAD이고 로컬 트리는 clean.
- PR5 본문의 full build pending은 과거 정보다. 뒤의 위 CI에서 full build가 성공했다. 실제 gameplay 검증은 여전히 별도 확인 대상이다.
- `import-pr5-source.ps1` 후 `download-cemu-artifacts.ps1`이 exec session `77124`에서 실행 중일 수 있으므로 먼저 poll할 것. 이 작업은 catalog의 Test를 PR5로 바꾸고 이전 Test를 historical_snapshots로 보존한다.
- 관리 worktree 생성 시도는 root 저장소에 해당 ref가 없어 실패했다. operation `86357c87-d72d-4bdb-8b49-d7c25be777e8`는 failed, 경로 생성 없음. 최상위는 원격/커밋 없는 정리용 저장소이고 실제 Cemu 저장소는 하위에 있어 이 도구가 직접 사용되지 않는다.
