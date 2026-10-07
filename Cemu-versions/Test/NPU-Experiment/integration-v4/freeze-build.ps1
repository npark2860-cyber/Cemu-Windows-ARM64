$ErrorActionPreference='Stop'
$lab=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$test=(Resolve-Path -LiteralPath (Join-Path $lab '..')).Path
$baseRoot=Join-Path $test 'NPU-Release-v3'
$base=Get-Content -LiteralPath (Join-Path $baseRoot 'NPU-RELEASE-BUILD.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$package=Join-Path $test 'NPU-Release-v4'
$manifestPath=Join-Path $package 'NPU-RELEASE-BUILD.json'
if(Test-Path -LiteralPath $manifestPath) {throw 'Preserve the frozen v4 manifest'}
$titlePaths=@('LSFG-Release/source/src/gui/wxgui/MainWindow.cpp','LSFG-Release/source/src/gui/wxgui/wxWindowSystem.cpp')
$sources=@()
foreach($file in $base.source_files) {
    $path=Join-Path $test $file.path
    $hash=(Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant()
    if($file.path -in $titlePaths) {
        $backup=Join-Path $lab ('evidence/before-npu-v4/'+[System.IO.Path]::GetFileName($path))
        if((Get-FileHash -LiteralPath $backup).Hash.ToLowerInvariant() -ne $file.sha256) {throw 'Original v3 title source backup changed'}
        $old=[System.IO.File]::ReadAllText($backup).Replace("`r`n","`n")
        $current=[System.IO.File]::ReadAllText($path).Replace("`r`n","`n")
        if($current.Replace('NPU EXP v4 - Release - Flow Cache','NPU EXP v3 - Release') -cne $old) {throw ('Unexpected source changes beyond title: '+$file.path)}
    } elseif($hash -ne $file.sha256) {throw ('Source drift from v3: '+$file.path)}
    $sources+=@{path=$file.path;sha256=$hash}
}
$sources+=@(Get-ChildItem -LiteralPath $PSScriptRoot -File | ForEach-Object {@{path=('NPU-Experiment/integration-v4/'+$_.Name);sha256=(Get-FileHash -LiteralPath $_.FullName).Hash.ToLowerInvariant()}})
$log=Get-Content -LiteralPath (Join-Path $lab 'evidence/cemu-npu-build-v4.log') -Raw
if($log -match '(?m)^FAILED:' -or $log -notmatch 'Linking CXX executable.*Cemu_release.exe') {throw 'Successful v4 link evidence unavailable'}
$cache=Get-Content -LiteralPath (Join-Path $test 'LSFG-Release/build/CMakeCache.txt') -Raw
foreach($setting in @('CMAKE_BUILD_TYPE:STRING=Release','CEMU_ENABLE_LSFG:BOOL=ON','CEMU_ENABLE_NPU:BOOL=ON')) {if(-not $cache.Contains($setting)) {throw ('Unexpected build setting: '+$setting)}}
if((Get-FileHash -LiteralPath (Join-Path $test 'LSFG-Release/runtime-experiment/Cemu-lsfg-resize.exe')).Hash.ToLowerInvariant() -ne $base.base_gpu_lsfg_sha256) {throw 'Original GPU LSFG binary changed'}
$candidate=Join-Path $lab 'flow-cache-v4/runtime/flow-cached.spv'
$shaderHash=(Get-FileHash -LiteralPath $candidate).Hash.ToLowerInvariant()
$files=@()
foreach($file in $base.files) {
    if(-not $file.path.StartsWith('runtime/')) {continue}
    $relative=$file.path
    if($relative -eq $base.executable) {$relative='runtime/Cemu-npu-exp-v4.exe'}
    $path=Join-Path $package $relative
    $hash=(Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant()
    if($relative -eq 'runtime/shaders/motion1080-flow.spv') {
        if($hash -ne $shaderHash) {throw 'Packaged flow shader differs from verified candidate'}
    } elseif($relative -ne 'runtime/Cemu-npu-exp-v4.exe' -and $hash -ne $file.sha256) {throw ('Unexpected runtime dependency change: '+$relative)}
    $files+=@{path=$relative;bytes=(Get-Item -LiteralPath $path).Length;sha256=$hash}
}
foreach($name in @('README.md','verify-build.ps1')) {$files+=@{path=$name;sha256=(Get-FileHash -LiteralPath (Join-Path $package $name)).Hash.ToLowerInvariant()}}
$reportPath=Join-Path $lab 'evidence/flow-cache-v4-20260929-165722-515.json'
$report=Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
if($report.status -ne 'FLOW_CACHE_WARP_MAPPING_VERIFIED' -or $report.equivalent_warp_pairs -ne 45 -or $report.measured_pairs -ne 30 -or $report.warp_mapping_differing_pixels -ne 0) {throw 'Verified standalone result missing'}
$exe=Join-Path $package 'runtime/Cemu-npu-exp-v4.exe'
$manifest=[ordered]@{
    created_at=(Get-Date).ToString('o');status='BUILT_NOT_GAME_TESTED';variant='Release (NPU EXP v4 - Flow Cache)';
    base_commit=$base.base_commit;base_package='NPU-Release-v3';base_manifest_sha256=(Get-FileHash -LiteralPath (Join-Path $baseRoot 'NPU-RELEASE-BUILD.json')).Hash.ToLowerInvariant();
    base_gpu_lsfg_sha256=$base.base_gpu_lsfg_sha256;cemu_machine='ARM64 0xAA64';executable='runtime/Cemu-npu-exp-v4.exe';
    cemu_sha256=(Get-FileHash -LiteralPath $exe).Hash.ToLowerInvariant();module_sha256=$base.module_sha256;model=$base.model;
    npu_driver=$base.npu_driver;gpu_driver=$base.gpu_driver;files=$files;source_files=$sources;
    source_change_from_v3='Two window title strings only';runtime_change_from_v3='Cemu executable identity plus motion1080-flow.spv; every other pinned runtime file is byte-identical';
    module_unchanged_from_v3=$true;flow_shader_sha256=$shaderHash;flow_shared_memory_bytes=31488;flow_dispatch=@(15,9,2);
    standalone_gpu_report='NPU-Experiment/evidence/flow-cache-v4-20260929-165722-515.json';standalone_gpu_report_sha256=(Get-FileHash -LiteralPath $reportPath).Hash.ToLowerInvariant();
    standalone_flow_mean_ms=@{baseline=$report.baseline.mean_ms;cached=$report.cached.mean_ms;saved=$report.baseline.mean_ms-$report.cached.mean_ms;reduction_percent=100*(1-$report.cached.mean_ms/$report.baseline.mean_ms)};
    standalone_flow_p95_ms=@{baseline=$report.baseline.p95_ms;cached=$report.cached.p95_ms};standalone_measured_pairs=30;warp_mapping_equivalent_pairs=45;warp_mapping_differing_pixels=0;
    semantic_comparison='GPU flow; exact confidence/reliable vectors and CPU consumer mapping per full-resolution pixel. Unreliable vectors and diagnostic cost differences recorded separately.';
    gpu_warp_output_compared=$false;cemu_executed_by_agent=$false;real_game_quality_validated=$false;game_performance_validated=$false;scanout_cadence_validated=$false;
    processing_dimensions=@(1920,1080);supported_output=$base.supported_output;scaled_real_and_generated_frames=$true;
    buffered_source_frames=1;shared_slots=3;worker_queue_submission=$false;render_thread_npu_wait=$false;shared_mlc_path=$base.shared_mlc_path;
    config_seed='Independent copy of current v3 settings/controller/gameProfiles/graphicPacks; MLC not copied or edited';
    overlay_cpu_contract_reused=$base.overlay_cpu_contract;overlay_replay=$base.overlay_replay;source_frame_throttle=$base.source_frame_throttle;
    notes='Standalone flow GPU comparison completed by user. Game package prepared and file-verified only; user game test pending. No four-variant rollout.'
}
$manifest | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $manifestPath -Encoding utf8
& (Join-Path $package 'verify-build.ps1') | ConvertTo-Json | Tee-Object -FilePath (Join-Path $lab 'evidence/cemu-npu-preflight-v4.json')
