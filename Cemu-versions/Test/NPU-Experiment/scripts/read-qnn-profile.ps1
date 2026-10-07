param([Parameter(Mandatory)][string]$Path)
$ErrorActionPreference = 'Stop'
$events = @(Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -Depth 64)
$nodes = @($events | Where-Object { $_.cat -eq 'Node' -and $_.args.provider })
$kernels = @($events | Where-Object { $_.cat -eq 'Node' -and $_.name -like '*kernel_time' })
$missingProvider = @($kernels | Where-Object { -not $_.args.provider })
$providers = @($nodes | ForEach-Object { [string]$_.args.provider } | Sort-Object -Unique)
[pscustomobject]@{
    verified_qnn_only = ($kernels.Count -gt 0 -and $missingProvider.Count -eq 0 -and $providers.Count -eq 1 -and $providers[0] -eq 'QNNExecutionProvider')
    node_events = $nodes.Count
    kernel_events = $kernels.Count
    kernels_without_provider = $missingProvider.Count
    providers = $providers
    note = 'Provider evidence must be combined with explicit QnnHtp backend selection and disabled CPU fallback.'
}
