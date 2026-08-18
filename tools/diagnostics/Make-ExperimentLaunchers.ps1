$ErrorActionPreference = 'Stop'

New-Item -ItemType Directory -Force -Path 'artifact/experiments' | Out-Null
Copy-Item 'bin/Cemu_release.exe' 'artifact/Cemu_release.exe'
Copy-Item 'tools/diagnostics/README.md' 'artifact/experiments/README.md'

$launchers = @(
    @{ Bat='00_Normal.bat'; Exe='Cemu_00_Normal.exe'; Exp=''; Log='log_00_Normal.txt' },
    @{ Bat='A_DepthClip_Feature.bat'; Exe='Cemu_A_DepthClipFeature.exe'; Exp='depthclip-feature,pipeline-diag'; Log='log_A_DepthClipFeature.txt' },
    @{ Bat='B_DepthClip_Off.bat'; Exe='Cemu_B_DepthClipOff.exe'; Exp='depthclip-off,pipeline-diag'; Log='log_B_DepthClipOff.txt' },
    @{ Bat='C_Pipeline_Feedback_Off.bat'; Exe='Cemu_C_PipelineFeedbackOff.exe'; Exp='pipeline-feedback-off,pipeline-diag'; Log='log_C_PipelineFeedbackOff.txt' },
    @{ Bat='D_Both_PNext_Off.bat'; Exe='Cemu_D_BothPNextOff.exe'; Exp='depthclip-off,pipeline-feedback-off,pipeline-diag'; Log='log_D_BothPNextOff.txt' },
    @{ Bat='E_DepthClamp_Off.bat'; Exe='Cemu_E_DepthClampOff.exe'; Exp='depthclip-off,pipeline-feedback-off,depthclamp-off,pipeline-diag'; Log='log_E_DepthClampOff.txt' },
    @{ Bat='DIAG_Pipeline_Only.bat'; Exe='Cemu_DIAG_PipelineOnly.exe'; Exp='pipeline-diag'; Log='log_DIAG_PipelineOnly.txt' },
    @{ Bat='FULL_Pipeline_PNext_Off.bat'; Exe='Cemu_FULL_PipelinePNextOff.exe'; Exp='pipeline-pnext-off,pipeline-diag'; Log='log_FULL_PipelinePNextOff.txt' },
    @{ Bat='FULL_Raster_PNext_Off.bat'; Exe='Cemu_FULL_RasterPNextOff.exe'; Exp='raster-pnext-off,pipeline-diag'; Log='log_FULL_RasterPNextOff.txt' },
    @{ Bat='PERF_1_Timer_Stats.bat'; Exe='Cemu_PERF1_TimerStats.exe'; Exp='timer-stats'; Log='log_PERF1_TimerStats.txt' },
    @{ Bat='PERF_2_UDiv64_Stats.bat'; Exe='Cemu_PERF2_UDiv64.exe'; Exp='timer-udiv64,timer-stats'; Log='log_PERF2_UDiv64.txt' },
    @{ Bat='PERF_3_UDiv64_NoFence_Stats.bat'; Exe='Cemu_PERF3_UDiv64_NoFence.exe'; Exp='timer-udiv64,timer-no-extra-fence,timer-stats'; Log='log_PERF3_UDiv64_NoFence.txt' },
    @{ Bat='PERF_4_UDiv64_ARM64_ISB_Stats.bat'; Exe='Cemu_PERF4_UDiv64_ARM64_ISB.exe'; Exp='timer-udiv64,timer-arm64-serialize,timer-stats'; Log='log_PERF4_UDiv64_ARM64_ISB.txt' }
)

foreach ($entry in $launchers)
{
    $lines = @(
        '@echo off',
        'setlocal EnableExtensions',
        ('set "CEMU_EXPERIMENTS={0}"' -f $entry.Exp),
        ('set "CEMU_EXPERIMENT_LOG={0}"' -f $entry.Log),
        'set "BASE_EXE=%~dp0..\Cemu_release.exe"',
        ('set "NAMED_EXE=%~dp0..\{0}"' -f $entry.Exe),
        'if not exist "%BASE_EXE%" (',
        '    echo [ERROR] Cemu_release.exe not found.',
        '    pause',
        '    exit /b 1',
        ')',
        'copy /Y "%BASE_EXE%" "%NAMED_EXE%" >NUL',
        ('echo EXE={0}' -f $entry.Exe),
        ('echo CEMU_EXPERIMENTS={0}' -f $entry.Exp),
        ('echo CEMU_EXPERIMENT_LOG={0}' -f $entry.Log),
        'pushd "%~dp0.."',
        ('"{0}"' -f $entry.Exe),
        'set "RET=%ERRORLEVEL%"',
        'popd',
        'exit /b %RET%'
    )
    $body = [string]::Join("`r`n", $lines) + "`r`n"
    Set-Content -Path (Join-Path 'artifact/experiments' $entry.Bat) -Value $body -NoNewline -Encoding ascii
}

Write-Host "Generated $($launchers.Count) named experiment launchers with dedicated log filenames"
