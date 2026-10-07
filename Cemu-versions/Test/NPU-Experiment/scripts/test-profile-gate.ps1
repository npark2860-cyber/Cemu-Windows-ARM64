$ErrorActionPreference = 'Stop'
$lab = Split-Path $PSScriptRoot -Parent
$cases = @(
    @{name='qnn-kernel';providers=@('QNNExecutionProvider');expected=$true},
    @{name='multiple-qnn';providers=@('QNNExecutionProvider','QNNExecutionProvider');expected=$true},
    @{name='cpu-fallback';providers=@('QNNExecutionProvider','CPUExecutionProvider');expected=$false},
    @{name='cpu-only';providers=@('CPUExecutionProvider');expected=$false},
    @{name='unknown-provider';providers=@('UnknownProvider');expected=$false},
    @{name='missing-provider';providers=@('QNNExecutionProvider','');expected=$false},
    @{name='empty-profile';providers=@();expected=$false}
)
foreach ($case in $cases) {
    $events = @($case.providers | ForEach-Object { @{cat='Node';name='kernel_time';args=@{provider=$_}} })
    $path = Join-Path $lab ('evidence/profile-gate-' + $case.name + '.json')
    ConvertTo-Json -InputObject $events -Depth 5 | Set-Content -LiteralPath $path -Encoding utf8
    $result = & (Join-Path $PSScriptRoot 'read-qnn-profile.ps1') -Path $path
    if ($result.verified_qnn_only -ne $case.expected) { throw ('Profile gate failed: ' + $case.name) }
}
[pscustomobject]@{mode='CPU-only synthetic profile fixtures';checks=$cases.Count;failures=0;device_executed=$false} | ConvertTo-Json
