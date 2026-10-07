$ErrorActionPreference='Stop'
$lab=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$release=(Resolve-Path -LiteralPath (Join-Path $lab '../LSFG-Release')).Path
$package=(Resolve-Path -LiteralPath (Join-Path $lab '../NPU-Release-v3')).Path
$base=Get-Content -LiteralPath (Join-Path $lab 'evidence/motion1080-probe-manifest.json') -Raw | ConvertFrom-Json
$exe=Join-Path $package 'runtime/Cemu-npu-exp-v3.exe'
$pe=[System.IO.File]::ReadAllBytes($exe)
if([BitConverter]::ToUInt16($pe,([BitConverter]::ToInt32($pe,60)+4)) -ne 0xaa64) {throw 'Wrong Cemu architecture'}
$log=Get-Content -LiteralPath (Join-Path $lab 'evidence/cemu-npu-build-v3.log') -Raw
if($log -match '(?m)^FAILED:' -or $log -notmatch 'Linking CXX executable.*Cemu_release.exe|ninja: no work to do') {throw 'No successful Cemu link/check evidence'}
$cache=Get-Content -LiteralPath (Join-Path $release 'build/CMakeCache.txt') -Raw
foreach($setting in @('CMAKE_BUILD_TYPE:STRING=Release','CEMU_ENABLE_LSFG:BOOL=ON','CEMU_ENABLE_NPU:BOOL=ON')) {if(-not $cache.Contains($setting)) {throw ('Unexpected build setting: '+$setting)}}
$baseline=(Get-FileHash -LiteralPath (Join-Path $release 'runtime-experiment/Cemu-lsfg-resize.exe') -Algorithm SHA256).Hash.ToLowerInvariant()
if($baseline -ne 'ced1fa7b1291dd29fec78188165651634e6e8a9a07025afc2904e35b63737504') {throw 'Working GPU LSFG baseline changed'}
$files=@(Get-ChildItem -LiteralPath (Join-Path $package 'runtime') -File -Recurse | Where-Object { $_.FullName -notlike ((Join-Path $package 'runtime/portable')+'\*') } | ForEach-Object { [ordered]@{path=[System.IO.Path]::GetRelativePath($package,$_.FullName).Replace('\','/');bytes=$_.Length;sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()} })
foreach($name in @('README.md','verify-build.ps1','run-module-smoke.ps1')) {$files += [ordered]@{path=$name;sha256=(Get-FileHash -LiteralPath (Join-Path $package $name) -Algorithm SHA256).Hash.ToLowerInvariant()}}
$sourcePaths=@('CMakeLists.txt','src/Cafe/CMakeLists.txt','src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp','src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h','src/Cafe/HW/Latte/Renderer/Vulkan/VulkanLSFG.cpp','src/Cafe/HW/Latte/Renderer/Vulkan/VulkanNPU.cpp','src/config/CemuConfig.h','src/gui/wxgui/GeneralSettings2.cpp','src/gui/wxgui/MainWindow.cpp','src/gui/wxgui/wxWindowSystem.cpp','src/Cafe/HW/Latte/Core/LatteOverlay.cpp','dependencies/npu-cemu/npu_cemu.h')
$sources=@($sourcePaths | ForEach-Object {[ordered]@{path=('LSFG-Release/source/'+$_);sha256=(Get-FileHash -LiteralPath (Join-Path (Join-Path $release 'source') $_) -Algorithm SHA256).Hash.ToLowerInvariant()}})
$sources+=@(@('src/imgui/imgui_impl_vulkan.cpp','src/imgui/imgui_impl_vulkan.h') | ForEach-Object {[ordered]@{path=('LSFG-Release/source/'+$_);sha256=(Get-FileHash -LiteralPath (Join-Path (Join-Path $release 'source') $_) -Algorithm SHA256).Hash.ToLowerInvariant()}})
$sources+=@(Get-ChildItem -LiteralPath $PSScriptRoot -File | ForEach-Object {[ordered]@{path=('NPU-Experiment/integration-v3/'+$_.Name);sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}})
$tests=Get-Content -LiteralPath (Join-Path $lab 'evidence/npu-buffered-timeline-cpu-tests-v3.json') -Raw | ConvertFrom-Json
if($tests.status -ne 'BUFFERED_TIMELINE_TESTS_PASSED' -or $tests.checks -ne 17) {throw 'Buffered timeline tests unavailable'}
$pathTests=Get-Content -LiteralPath (Join-Path $lab 'evidence/npu-path-cpu-tests-v3.log') -Raw
if(-not $pathTests.Contains('ORT_PATH_TESTS_PASSED checks=7') -or -not $pathTests.Contains('old_path_throws=1')) {throw 'Unicode regression evidence unavailable'}
$manifest=[ordered]@{created_at=(Get-Date).ToString('o');status='BUILT_NOT_RUNTIME_TESTED';variant='Release (NPU EXP v3)';base_commit='c5205ccbc8ffe41129fbe921b5420a79ff283216';base_gpu_lsfg_sha256=$baseline;cemu_machine='ARM64 0xAA64';executable='runtime/Cemu-npu-exp-v3.exe';cemu_sha256=(Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant();module_sha256=(Get-FileHash -LiteralPath (Join-Path $package 'runtime/cemu_npu.dll') -Algorithm SHA256).Hash.ToLowerInvariant();model=$base.model;npu_driver=$base.driver;gpu_driver=$base.graphics;files=$files;source_files=$sources;cpu_timeline_tests=$tests;cemu_executed=$false;borrowed_module_device_tested=$false;real_game_quality_validated=$false;scanout_cadence_validated=$false;source_dimensions=@(1920,1080);buffered_source_frames=1;shared_slots=3;worker_queue_submission=$false;render_thread_npu_wait=$false;shared_mlc_path=(Join-Path $release 'runtime-experiment/portable/mlc01');notes='Build and offline checks only. Standalone predecessor verified separately. Three-slot borrowed-device integration and Cemu game rendering still require runtime verification.'}
$manifest.processing_dimensions=@(1920,1080)
$manifest.supported_output='Any nonzero SDR UNORM swapchain extent with required transfer/filter support'
$manifest.scaled_real_and_generated_frames=$true
$manifest.cpu_unicode_regression_checks=7
$manifest.fixed_backend_path='App-local ASCII basename after verifying the loaded ORT DLL directory; wide model path retained'
$overlay=Get-Content -LiteralPath (Join-Path $lab 'evidence/npu-overlay-cpu-tests-v3.json') -Raw | ConvertFrom-Json
if($overlay.status -ne 'OVERLAY_CPU_CONTRACT_PASSED' -or $overlay.checks -lt 480) {throw 'Overlay lifetime regression unavailable'}
$manifest.overlay_cpu_contract=$overlay
$manifest.overlay_replay='Same immutable upload; final reader command tracked; wait only on ring-slot overwrite'
$manifest.source_frame_throttle='Generated presents neither wait for nor advance the previous source-frame command marker'
$manifest.module_unchanged_from_v2_game=$manifest.module_sha256 -eq '6eb9cb8acc8d722ebc7c21bc7b0a972618d7f8c4c256abe7ac6064f31be6600a'
if(-not $manifest.module_unchanged_from_v2_game) {throw 'Unexpected inference module change'}
$manifest.notes='v3 Cemu build and CPU checks only; not launched by agent. Identical NPU DLL/model/shaders already executed in the user-run v2 game session. Window scaling, overlay reuse and source-frame throttling require new user runtime verification; no performance gain claimed yet.'
$manifest | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $package 'NPU-RELEASE-BUILD.json') -Encoding utf8
& (Join-Path $package 'verify-build.ps1') | ConvertTo-Json | Tee-Object -FilePath (Join-Path $lab 'evidence/cemu-npu-preflight-v3.json')
