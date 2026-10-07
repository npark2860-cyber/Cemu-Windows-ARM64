# Cemu Windows ARM64 추가 최적화 분석 / TODO

분석일: 2026-09-18. 대상: Snapdragon X Elite / Adreno X1-85.

분석한 브랜치: `final-adreno-compat-arm64`. 실제 복제한 HEAD: `d359c53da77dddac6c34554d3b894099896b070e`.

[고정 커밋 소스](https://github.com/npark2860-cyber/Cemu-Windows-ARM64/tree/d359c53da77dddac6c34554d3b894099896b070e)

이 문서는 소스 정적 분석이다. 코드를 수정하거나 패치 스크립트를 실행하지 않았고 빌드·게임 실행·프로파일링도 하지 않았다. 아래 병목은 코드에서 확인한 작업을 바탕으로 한 가설이며, 실행 빈도와 실제 비용은 미확인이다. 숫자로 FPS 향상을 예측하지 않는다. 예상 효과는 줄어드는 작업과 영향을 받을 성능 지표로 표현한다.

**우선순위는 버퍼 복사·해시 통합, 실제 coherent staging 메모리의 불필요한 flush 제거, JIT 작업 대기 개선이다. ARM64 명령 자체를 활용하는 후보는 정수 텍스처 변환과 극히 제한된 JIT store 축약이다.**

## 분석 기준과 보호 경로

체크인 소스와 실제 Release 빌드 입력이 같지 않다. [릴리즈 워크플로](https://github.com/npark2860-cyber/Cemu-Windows-ARM64/blob/d359c53da77dddac6c34554d3b894099896b070e/.github/workflows/final-adreno-compat-arm64.yml#L46)는 빌드 전에 다음을 적용한다.

- swapchain `LOAD_OP_LOAD`, command buffer `SIMULTANEOUS_USE`, 배경 clear 경로의 기존 pre-e834 동작.
- `Apply-PSDefaultLinkageFix.py`의 DEFAULT_VAL linkage 수정.
- FSR1 EASU/RCAS 패치. 이름에 Experiment가 있어도 현재 Release 워크플로에 포함되어 있다.

`VulkanQuery.cpp:44–52`에는 Bayo2/SFZ/XCX의 JPN/USA/EUR 9개 title ID가 있고, 직접 `vkGetQueryPoolResults`로 읽는 경로도 확인했다. 이 경로, query 결과의 의미, barrier/access/stage mask, robust-buffer-access 판단, shader linkage, FSR 정밀도는 변경 대상으로 삼지 않는다.

향후 실험은 저장소의 `BRANCH_POLICY.md`대로 Diagnostics에서 계측하고 Test에서 한 변수씩 수행해야 한다. 이 분석은 Release에 실험 코드나 계측을 넣자는 제안이 아니다.

## 이미 존재하므로 신규 아이디어에서 제외한 것

| 기존 기능 | 확인한 위치 | 판단 |
|---|---|---|
| ARM64 LSE 선택 및 fallback | `BackendAArch64.cpp:1109`, `atomic_cmp_store()`의 `casal` / `ldaxr`·`stlxr` | LSE 도입·원자 ordering 완화 제안 제외 |
| pipeline 캐시 / 비동기 컴파일 | `VulkanRendererCore.cpp:246`, `VulkanPipelineCompiler.cpp:899`, stable cache 파일 | 캐시·async를 새로 도입하자는 제안 제외 |
| SPIR-V 캐시 | `RendererShaderVk.cpp:267`, `ShaderCacheLoading_begin()` | 캐시가 없다는 전제 제외 |
| descriptor 캐시 | `VulkanRendererCore.cpp:579`, `draw_getOrCreateDescriptorSet()` | descriptor를 매 draw 생성한다는 가설 제외 |
| uniform 증분 갱신 | `VulkanRendererCore.cpp:452`, dirty mask 및 `hasChange` | TODO 주석만 보고 dirty tracking 미구현으로 판단하지 않음 |
| staging ring / heap allocator | `VKRMemoryManager.cpp` | 매 업로드마다 새 Vulkan 메모리를 할당한다는 전제 제외 |
| texture light / sampled hash | `LatteTextureCache.cpp:25–196` | 검사 샘플 수 감소는 정확도 조건상 제외 |
| audio delta==0 분기 | `ax_mix.cpp:632` | 상수 볼륨 경로 자체는 이미 존재 |

## 1. BufferCache 업로드의 복사와 해시 순회 통합 — 우선

1. **병목 가설:** `uploadPages()`는 guest RAM을 `s_pageUploadBuffer`로 복사한 뒤 같은 버퍼를 다시 순회하여 페이지 hash를 계산한다. 이후 Vulkan staging으로 한 번 더 복사한다. 갱신량이 큰 장면에서는 CPU 캐시 트래픽과 루프 비용이 누적될 수 있다. 함수에 복사+해시 통합 TODO도 남아 있다.
2. **수정 대상:** [LatteBufferCache.cpp:1255](https://github.com/npark2860-cyber/Cemu-Windows-ARM64/blob/d359c53da77dddac6c34554d3b894099896b070e/src/Cafe/HW/Latte/Core/LatteBufferCache.cpp#L1255), `BufferCacheNode::uploadPages()`, `hashPage()`; 호출 관계 확인 대상은 `VulkanRenderer.cpp:3835`, `bufferCache_upload()`.
3. **ARM64 효과 근거 / 아이디어:** 한 번 로드한 64비트 값으로 기존 네 개 hash 누산기를 갱신하고 같은 값을 snapshot 버퍼에 저장한다. ARM64 정수 multiply/rotate와 load/store 스케줄링을 활용하고 중복 읽기를 줄인다. 이것을 무조건 NEON화할 필요는 없다. 기존 64비트 곱셈·rotate 의미를 유지하는 scalar 경로부터 비교한다.
4. **예상 효과:** snapshot을 hash하기 위한 추가 전체 읽기 순회를 제거할 수 있다. 이미 캐시에 있는 읽기이므로 DRAM 대역폭 절감량과 같지는 않다. 동적 vertex/uniform 갱신이 많으면 renderer CPU 시간 감소 가능; 정적 장면·GPU 병목에서는 전체 효과가 작다.
5. **구현 난이도:** 중. 기존 snapshot·renderer API를 유지하면 변경 범위가 좁다.
6. **회귀 위험:** 중. hash한 값과 실제 업로드한 값이 반드시 일치해야 한다. guest RAM을 다시 읽어 hash하거나, streamout signature 필터를 우회하면 안 된다. 직접 guest→staging 통합은 이번 첫 실험에서 제외한다.
7. **검증:** 고정 입력에 대한 기존/신규 페이지 hash 및 snapshot 바이트 일치; random·zero·signature 입력; 여러 페이지 크기; concurrent guest 갱신 상황에서 업로드 바이트/hash 대응; 프레임당 업로드량·함수 CPU 시간·streamout 장면 비교. 최적화된 libc memcpy보다 실제로 빠른지도 측정한다.

## 2. Staging 메모리의 실제 coherent 속성에 따른 flush 생략 — 우선, 조건부

1. **병목 가설:** ring staging은 `HOST_VISIBLE`만 요구해 메모리 타입을 고르지만, `FlushReservation()`은 매번 `vkFlushMappedMemoryRanges()`를 호출한다. 실제 선택된 타입에 `HOST_COHERENT`도 있으면 불필요한 API 호출일 수 있다. 현재 장치에서 어떤 타입이 선택되는지는 확인하지 않았다.
2. **수정 대상:** [VKRMemoryManager.cpp:25](https://github.com/npark2860-cyber/Cemu-Windows-ARM64/blob/d359c53da77dddac6c34554d3b894099896b070e/src/Cafe/HW/Latte/Renderer/Vulkan/VKRMemoryManager.cpp#L25), `allocateAdditionalUploadBuffer()`, `FlushReservation()`(109), `CreateBuffer()`(461), `FindMemoryType()`(383); `VKRMemoryManager.h`의 ring buffer 메타데이터.
3. **ARM64 효과 근거 / 아이디어:** 실제 선택한 memory type의 속성을 보존하고 coherent일 때만 flush를 생략한다. ARM ISA 특유의 개선은 아니지만 ARM64 host의 드라이버 호출 overhead를 줄일 수 있다. UMA라는 이유만으로 coherent를 가정하거나 다른 memory type을 강제하지 않는다.
4. **예상 효과:** 해당 staging 메모리가 coherent면 업로드 건수만큼 flush 호출을 없앨 수 있다. non-coherent면 이 단계의 성능 이익은 없다. 이미 coherent 여부를 검사하는 uniform upload 경로를 중복 최적화 대상으로 잡지 않는다.
5. **구현 난이도:** 낮음~중. 선택된 속성 전달에 작은 인터페이스 변경이 필요하다.
6. **회귀 위험:** 낮음~중. 요구한 flags와 실제 선택한 flags를 혼동하면 위험하다. non-coherent flush는 유지한다. ring의 128바이트 정렬/TODO는 장치 `nonCoherentAtomSize`와 별도로 대조해야 하며 현재 Adreno에서 오류가 난다고 단정할 수 없다.
7. **검증:** selected memoryTypeIndex·실제 flags·atom size를 기록하고 분기별 flush 횟수/CPU 시간 비교. coherent/non-coherent 양쪽에서 업로드 readback 바이트 비교 및 validation layer 검사. descriptor/barrier/fence는 그대로 둔다.

후속 후보로는 non-coherent 범위를 동일 제출 내에서 모아 flush하는 방법이 있지만 우선순위가 낮다. submit 전 flush 보장, 범위 정렬, ring wrap, 같은 atom의 in-flight 접근까지 검토해야 하므로 coherent 생략과 한 패치로 묶지 않는다. [Khronos 메모리 속성 규정](https://docs.vulkan.org/refpages/latest/refpages/source/VkMemoryPropertyFlagBits.html), [flush 규정](https://docs.vulkan.org/refpages/latest/refpages/source/vkFlushMappedMemoryRanges.html).

## 3. JIT worker의 10ms polling을 작업 도착 알림으로 변경 — 우선

1. **병목 가설:** `PPCRecompiler_thread()`는 바깥 루프마다 10ms sleep 후 작업 큐를 비운다. 큐가 비어 있던 순간 새 코드가 들어오면 다음 poll까지 interpreter 사용이 늘 수 있다. 실제 대기 시간은 OS 스케줄링으로 더 길어질 수 있다.
2. **수정 대상:** [PPCRecompiler.cpp:453](https://github.com/npark2860-cyber/Cemu-Windows-ARM64/blob/d359c53da77dddac6c34554d3b894099896b070e/src/Cafe/HW/Espresso/Recompiler/PPCRecompiler.cpp#L453), `PPCRecompiler_thread()`, `PPCRecompiler_visitAddressNoBlock()`(69), `PPCRecompiler_Shutdown()`(705 부근), worker 상태 구조체.
3. **ARM64 효과 근거 / 아이디어:** 기존 단일 worker와 queue 보호를 유지하면서 empty→non-empty 전환 및 종료를 event/semaphore 등으로 알린다. ARM64 명령 생성이나 register allocator를 건드리지 않고 네이티브 JIT에 도달하기 전 interpreter 시간을 줄인다. ARM64에만 적용되는 원리는 아니다.
4. **예상 효과:** 빈 큐에서 새 작업을 받는 경우 10ms 주기 polling 지연을 줄일 가능성. 새 지역·코드 최초 실행의 프레임시간과 초기 진입 개선이 중심이다. 이미 JIT가 준비된 정상 상태 FPS는 거의 변하지 않을 수 있다.
5. **구현 난이도:** 중. 이벤트 자체보다 lost wakeup 및 shutdown 처리의 정확성이 핵심이다.
6. **회귀 위험:** 중. 생산자의 non-blocking 성질을 보존하고, notification 누락·깨우기 폭증·종료 join 교착을 막아야 한다. jump-table publication, 코드 캐시 flush와 invalidation 동작은 유지한다.
7. **검증:** enqueue→compile-start 지연 분포, interpreter 체류시간, 큐 길이, idle wakeup 수; empty↔non-empty 반복·게임 재시작·컴파일 도중 종료; 동일 실행 구간의 JIT 결과 및 crash 여부. 10ms 단축을 프레임당 10ms 향상으로 해석하지 않는다.

## 4. 정수 텍스처 decoder의 픽셀 내부 byte-swap 벡터화 — ARM64 우선 후보

1. **병목 가설:** R32G32B32A32_UINT와 R16G16B16A16_UINT decoder는 픽셀마다 네 component를 각각 load/swap/store한다. 해당 포맷을 실제로 CPU에서 업로드하는 게임이면 비용이 생긴다. tiled 주소 계산이 지배적이면 이 부분의 개선폭은 작다.
2. **수정 대상:** [LatteTextureLoader.h:387](https://github.com/npark2860-cyber/Cemu-Windows-ARM64/blob/d359c53da77dddac6c34554d3b894099896b070e/src/Cafe/HW/Latte/Core/LatteTextureLoader.h#L387), `TextureDecoder_R32_G32_B32_A32_UINT::decode()`(396), `TextureDecoder_R16_G16_B16_A16_UINT::decode()`(434).
3. **ARM64 효과 근거 / 아이디어:** 한 픽셀의 16바이트 또는 8바이트를 Advanced SIMD로 읽고 component 단위 byte-reverse 후 저장한다. 기존 `LatteTextureLoader_GetInput()`과 stepX/stepY를 그대로 사용한다. 서로 다른 tiled 픽셀의 물리적 연속성을 가정하지 않는다. [Arm Advanced SIMD 문서](https://developer.arm.com/documentation/101028/0009/Advanced-SIMD--Neon--intrinsics).
4. **예상 효과:** 해당 변환 커널의 명령 수 감소. 다만 clang-cl이 이미 같은 명령을 만들면 이익은 없고, 해당 포맷이 드물면 게임 전체 효과도 거의 없다. 포맷별 업로드 바이트 집계 후 진행한다.
5. **구현 난이도:** 낮음~중. 두 decoder에만 제한하면 작다.
6. **회귀 위험:** 낮음~중. component endian 의미, 정확한 8/16바이트 읽기 범위, misalignment, slice/mip 경계를 보존해야 한다. 소스의 endian TODO를 해석해서 포맷 의미까지 바꾸면 안 된다.
7. **검증:** Release 툴체인의 생성 명령을 먼저 확인. 기존 decoder 대비 모든 출력 바이트 비교, linear/1D/2D tiled, 작은 mip·홀수 크기·slice·step 조합; 업로드 burst와 warmed scene 비교. 이미 벡터화되어 있으면 종료한다.

## 5. ARM64 JIT의 byte-swapped 16비트 store 한정 명령 축약 — 후순위

1. **병목 가설:** `store()`의 16비트 swap 경로는 `REV Wtmp, Wdata` → `LSR Wtmp, #16` → `STRH`를 생성한다. 최종적으로 하위 16비트만 저장하므로 `REV16 Wtmp, Wdata` → `STRH`로 같은 저장 바이트를 만들 수 있다.
2. **수정 대상:** [BackendAArch64.cpp:1057](https://github.com/npark2860-cyber/Cemu-Windows-ARM64/blob/d359c53da77dddac6c34554d3b894099896b070e/src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp#L1057), `AArch64GenContext_t::store()`의 `copyWidth == 16 && swapEndian` 분기만.
3. **ARM64 효과 근거 / 아이디어:** A64의 halfword 내부 byte reverse를 사용해 shift 하나를 없앤다. 원본 레지스터, effective address 계산, UXTW, guest 32비트 주소 wrap은 그대로 유지한다. signed load나 FPU 경로까지 확대하지 않는다.
4. **예상 효과:** 해당 store 한 번당 발행 명령 1개·JIT 코드 4바이트 감소. 이 명령이 hot loop에서 많아야 의미가 있으며 전체 FPS 개선은 작거나 측정되지 않을 수 있다.
5. **구현 난이도:** 코드 변경은 낮음, JIT 회귀 검증은 중.
6. **회귀 위험:** 범위는 작지만 CPU 실행 경로여서 보수적으로 중. 상위 16비트 및 temporary 사용 관계를 점검해야 한다. 검증된 JIT를 먼저 바꿔야 할 이유는 없다.
7. **검증:** 하위 16비트 전 값과 여러 상위 비트 패턴에서 저장 결과 비교; 원본 register 불변 확인; indexed/non-indexed, 양·음 offset, 비정렬 및 경계 주소의 기존 동작과 차등 검사; 실제 hot block의 해당 opcode 빈도와 실행시간 측정.

## 6. Shader / pipeline 컴파일 동시성의 실행 중 예산 조정 — 조건부

1. **병목 가설:** pipeline pool은 물리 core 수에서 계산하고 최대 8개까지 만든다. 별도 shader pool은 2개다. 컴파일 burst가 발생하면 JIT·guest CPU·renderer·audio와 CPU 및 cache를 경쟁할 수 있다. 다만 pipeline worker가 shader 완료를 기다리기도 하므로 '항상 10개가 CPU를 쓴다'는 뜻은 아니다.
2. **수정 대상:** [VulkanPipelineCompiler.cpp:1080](https://github.com/npark2860-cyber/Cemu-Windows-ARM64/blob/d359c53da77dddac6c34554d3b894099896b070e/src/Cafe/HW/Latte/Renderer/Vulkan/VulkanPipelineCompiler.cpp#L1080), `compilePipeline_thread()`, `PipelineCompiler::CompileThreadPool_Start()`; `RendererShaderVk.cpp:131`, `_ShaderVkThreadPool::StartThreads()`와 `CompilerThreadFunc()`.
3. **ARM64 효과 근거 / 아이디어:** 먼저 runtime pipeline worker 상한만 2/4/8로 A/B 비교한다. X Elite에서 CPU 사용량·cache 경쟁·전력 조건에 맞는 예산을 찾는 플랫폼 튜닝이다. core 번호를 임의로 P/E core로 구분하거나 고정 affinity를 강제하지 않는다. 기존 lower-priority 설정도 이미 존재한다.
4. **예상 효과:** cold shader 구간의 p95/p99 frame time과 audio deadline 개선 가능. 반대로 컴파일 완료가 늦어져 기존 async rendering 누락 시간이 늘거나 동기 대기가 커질 수 있다. warm cache 정상 상태 이익은 작다.
5. **구현 난이도:** 고정 상한 실험은 낮음. 로딩/실행 단계별 adaptive budget은 중이며 첫 실험에서 제외한다.
6. **회귀 위험:** 중. shader/pipeline 생성 옵션, cache identity, 정확도는 유지하되 완료 순서·시점 변화는 관찰해야 한다. 정확도 비교는 동일 설정에서 pipeline이 준비된 프레임도 따로 수행한다.
7. **검증:** cold/warm 각각 compiler queue 체류시간·sync compile 시간·완료량·CPU ready time·renderer/JIT/audio 스레드 지연 측정. 평균 FPS만 보지 않고 최초 로딩 시간, shader 누락 지속시간, p99와 오디오 underrun을 함께 비교한다.

## 7. Cubeb 출력 버퍼의 앞부분 erase 제거 — Cubeb 사용 시 우선

1. **병목 가설:** `data_cb()`는 mutex 안에서 출력 복사 후 vector 앞부분을 `erase()`한다. 남은 모든 오디오 바이트 이동이 callback마다 발생할 수 있고 producer도 같은 mutex를 사용한다.
2. **수정 대상:** [CubebAPI.cpp:33](https://github.com/npark2860-cyber/Cemu-Windows-ARM64/blob/d359c53da77dddac6c34554d3b894099896b070e/src/audio/CubebAPI.cpp#L33), `CubebAPI::data_cb()`, `FeedBlock()`, `NeedAdditionalBlocks()`; `CubebAPI.h`의 buffer 메타데이터.
3. **ARM64 효과 근거 / 아이디어:** 고정 용량 ring에 read/write index와 queued-byte count를 둔다. 기존 mutex를 유지한 상태에서 잔여 데이터 이동만 제거한다. ARM64의 lock-free memory ordering 변경까지 할 필요가 없으며 cache traffic·lock 보유시간 감소가 목적이다.
4. **예상 효과:** callback마다 남은 queued bytes를 이동하는 비용 제거. 평균 FPS보다 callback 최악 지연과 CPU 여유 개선에 의미가 있다. XAudio2를 사용 중이면 이 후보의 효과는 없다. XAudio2에는 이미 재사용 audio buffer가 있다.
5. **구현 난이도:** 중. 자료구조 변경은 해당 backend 내부에 제한한다.
6. **회귀 위험:** 낮음~중. wrap 시 두 구간 copy, frame/channel 경계, 부족 데이터 silence fill, 기존 capacity/drop 기준과 장치 재시작을 보존해야 한다.
7. **검증:** PCM 바이트 순서 일치, producer block과 callback 길이가 서로 다른 경우, 빈/가득 찬 buffer, wrap, stereo/다채널, TV/DRC, 장치 전환; callback p99·mutex 보유시간·underrun/drop 수를 비교한다.

## 8. Audio 상수 볼륨 mixing의 ARM64 SIMD 생성 확인 및 보강 — 조건부

1. **병목 가설:** `AXVoiceMix_MergeInto()`의 delta==0과 `AXMix_MergeBusSamples()`의 delta==0 루프는 독립 sample 연산이다. 후자는 endian 변환과 float→int 변환도 수행한다. voice 수가 많을 때 비용이 커질 수 있으나 compiler auto-vectorization 여부는 미확인이다.
2. **수정 대상:** [ax_mix.cpp:632](https://github.com/npark2860-cyber/Cemu-Windows-ARM64/blob/d359c53da77dddac6c34554d3b894099896b070e/src/Cafe/OS/libs/snd_core/ax_mix.cpp#L632), `AXVoiceMix_MergeInto()`의 상수 볼륨 분기, `AXMix_MergeBusSamples()`(877 부근)의 상수 볼륨 분기.
3. **ARM64 효과 근거 / 아이디어:** 생성 코드가 scalar이고 실제 hot path일 때만 Advanced SIMD로 여러 sample을 처리한다. 이미 있는 delta==0 최적화를 다시 도입하는 것이 아니라 그 분기의 native code를 개선하는 후보다. ADPCM history, biquad/IIR, delta 누산 순서는 건드리지 않는다.
4. **예상 효과:** 비벡터화된 mixer 커널의 처리량 개선 가능. audio 전체 및 게임 FPS의 개선폭은 그 커널 점유율에 제한된다. 이미 적절한 SIMD라면 효과 없음.
5. **구현 난이도:** 중.
6. **회귀 위험:** 중. FMA 사용 여부, FP rounding, float→int truncation, overflow·NaN 경계, sample 순서를 바꾸면 PCM 결과가 달라질 수 있다. fast-math나 precision 축소는 제외한다.
7. **검증:** 동일 compiler 설정의 기존 경로를 oracle로 buffer 및 최종 PCM 차등 비교. 경계 sample·음수·clip 근방·여러 channel·voice 수 검사; generated assembly, 3ms audio 작업 시간, underrun 수 측정. 기존과 다른 수치 결과가 생기면 채택하지 않는다.

## 9. Vulkan 제출 임계값의 비용 기반 조정 — 계측 후 후순위

1. **병목 가설:** 제출 후 기본 임계값은 draw 300개다. query 등의 요청은 `RequestSubmitSoon()`으로 더 빨리 제출하게 만들고, readback은 `draw_endSequence()`에서 즉시 제출한다. 기본 draw 개수는 명령 기록 비용이나 업로드량을 표현하지 못하므로 일부 장면에서 submit overhead 또는 GPU 대기가 생길 가능성이 있다.
2. **수정 대상:** [VulkanRenderer.cpp:2191](https://github.com/npark2860-cyber/Cemu-Windows-ARM64/blob/d359c53da77dddac6c34554d3b894099896b070e/src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp#L2191), `SubmitCommandBuffer()`의 기본 threshold 설정, `RequestSubmitSoon()`; `VulkanRendererCore.cpp:1818` 부근 `draw_endSequence()`.
3. **ARM64 효과 근거 / 아이디어:** ARM64 host/Adreno 드라이버의 기록·제출 비용을 실제 측정해 기본 threshold만 작은 범위에서 비교한다. readback/query/idle/present의 강제 제출 요청은 그대로 우선시한다. CPU ISA 전용 기법은 아니다.
4. **예상 효과:** threshold 때문에 작은 command buffer가 다수 제출되는 장면이면 API 및 상태 재설정 비용 감소 가능. query/readback/present가 대부분 제출을 강제하면 효과가 거의 없다. threshold를 높이면 오히려 GPU 시작이 늦어질 수 있다.
5. **구현 난이도:** 고정 threshold 비교는 낮음, 시간/byte 기반 adaptive 방식은 중~높음. 첫 실험은 고정값 한 변수로 제한한다.
6. **회귀 위험:** 중~높음. query 사용 시점·GPU 진행·ring 압력과 frame pacing이 연결되어 있어 앞선 후보보다 우선순위가 낮다. 이전 submit semaphore chain, ALL_COMMANDS wait mask, fence, protected query 결과 및 Release의 SIMULTANEOUS_USE를 제거하지 않는다. 이를 제거해야만 이익이 난다면 이번 범위에서는 기각한다.
7. **검증:** submit 이유별 횟수, draws/bytes per command buffer, queue-submit CPU 시간, GPU idle, command-buffer-ring/full uniform-ring 대기, present 지연과 input latency; Bayo2/SFZ/XCX query 관련 PASS 장면과 TV/DRC 동시 출력 반복. 교착·missing draw·장시간 frame spike가 없어야 한다.

## 추가로 검토했지만 지금은 제안하지 않는 변경

- **Texture hash의 AVX2→NEON 단순 이식:** 큰 texture의 x86 AVX2 경로와 ARM scalar 경로는 샘플 stride·hash 연산부터 다르다. 단순 이식은 기존 ARM 경로의 검사 의미를 보존하는 최적화가 아니다. 샘플 수 축소도 제외한다.
- **전면 zero-copy guest RAM / host buffer 강제:** `bufferCache_init()` 부근에 host-memory 선택의 미사용 코드가 있어도, UMA만으로 동시 접근·가시성·수명 문제가 해결되지는 않는다. 기존 snapshot 및 streamout 보존을 흔들 위험이 크다.
- **barrier 및 semaphore 삭제, wait-stage 완화:** 성능 가능성은 있으나 이 저장소의 검증된 Adreno 호환성을 우선하면 근거 없이 시도할 대상이 아니다.
- **JIT register allocator 교체, LDP/STP 전면화, FP 정밀도 변경:** 작은 실험으로 검증하기 어렵고 보호한 CPU 경로를 넓게 바꾼다.
- **descriptor 캐시 추가 / uniform dirty tracking 추가:** 이미 있다. 세대 번호 기반 추가 shortcut은 invalidation 누락 위험에 비해 현재 병목 증거가 부족하다.
- **pipeline cache save redesign:** `PipelineCacheSaveThread()`는 이미 15초 지연, try_lock 기반 우선권 배려, lock 밖 파일 쓰기를 수행한다. vkGetPipelineCacheData 순간의 exclusive lock 비용은 계측할 만하지만 항상 심각한 문제라고 판단할 근거는 없다.
- **runtime SPIR-V cache read의 무조건 확대:** 현재 read는 `s_isLoadingShadersVk`로 제한되고 write는 runtime에도 한다. 이 조건만 지우기 전에 cache key·gfx pack·소스 변형과 invalidation의 정합성을 더 검토해야 한다. 이번 소규모 우선 후보에서 제외한다.

## 실행 가능한 TODO 순서

- [ ] 동일 commit 및 Release 패치 적용 상태를 고정한 기준 artifact 확보. 현재 문서의 분석 commit과 다른 버전이면 관련 소스를 다시 대조.
- [ ] X Elite에서 선택된 audio backend, Vulkan memory type/flags/atom size, shader/pipeline worker 수 확인.
- [ ] 동일 저장지점·입력·해상도·FSR·VSync·전원 모드·드라이버·발열 조건을 고정. cold cache 실험에는 기준 cache의 별도 복사본 사용.
- [ ] Diagnostics에서 가벼운 집계 위주로 upload bytes/hash CPU 시간, flush 횟수/시간, JIT queue latency, compiler CPU 경쟁, submit 이유, audio callback 시간 수집. 계측 overhead 자체도 확인.
- [ ] 소스상 반복 작업이 실제 CPU 프로파일에 나타나면 1→2→3 순으로 한 변수씩 실험. Cubeb 사용 시 7도 앞 순서로 승격.
- [ ] 4·8은 clang-cl 생성 명령에서 자동 벡터화 여부 확인 후 결정. 5는 hot opcode 빈도가 확인된 경우에만 진행.
- [ ] shader cold 구간 경쟁이 확인되면 6, submit overhead가 확인되면 9를 진행.
- [ ] 각 실험은 원본/후보를 번갈아 최소 여러 차례 재생해 median·p95·p99 frame time, 관련 스레드 CPU 시간, underrun/crash를 비교. 측정 산포보다 작은 차이는 효과 미확인으로 처리.
- [ ] 보호 title의 이용 가능한 모든 지역판 PASS 장면, BOTW 기준 장면, streamout/texture streaming/TV·DRC/장시간 플레이를 확인. 미검증 지역·경로는 명시하고 전체 PASS라고 부르지 않음.
- [ ] byte-exact 대상은 바이트 비교, rendering은 동일 시점 이미지 및 query 동작 확인, audio는 PCM 비교. validation layer 사용 성능과 일반 실행 성능은 분리.
- [ ] 성능 이익과 회귀 없음이 둘 다 확인된 작은 변경만 기존 promotion 정책에 따라 승격.

전체 이익은 CPU/GPU 중 어느 쪽이 프레임을 제한하는지에 따라 달라진다. 가령 CPU 임계 경로의 10%를 차지하는 부분을 20% 줄여도 그 경로 단축은 약 2%이며, GPU 병목이면 FPS가 그대로일 수 있다. 각 후보의 수치를 합산해서 FPS 향상률을 만들면 안 된다.
