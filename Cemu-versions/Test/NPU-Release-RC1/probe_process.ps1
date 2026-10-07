function Invoke-RecordedProbe {
    param(
        [Parameter(Mandatory=$true)][string]$Executable,
        [Parameter(Mandatory=$true)][string]$ArgumentLine,
        [Parameter(Mandatory=$true)][string]$WorkingDirectory,
        [Parameter(Mandatory=$true)][string]$StdoutPath,
        [Parameter(Mandatory=$true)][string]$StderrPath
    )
    $startInfo=New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName=$Executable
    $startInfo.Arguments=$ArgumentLine
    $startInfo.WorkingDirectory=$WorkingDirectory
    $startInfo.UseShellExecute=$false
    $startInfo.CreateNoWindow=$true
    $startInfo.RedirectStandardOutput=$true
    $startInfo.RedirectStandardError=$true
    $process=New-Object System.Diagnostics.Process
    $process.StartInfo=$startInfo
    $started=$false
    try {
        if(-not $process.Start()) {throw 'Could not start comparison process'}
        $started=$true
        # Drain both pipes concurrently while retaining our own process handle.
        $stdoutTask=$process.StandardOutput.ReadToEndAsync()
        $stderrTask=$process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        $exitCode=$process.ExitCode
        $encoding=New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($StdoutPath,$stdoutTask.GetAwaiter().GetResult(),$encoding)
        [System.IO.File]::WriteAllText($StderrPath,$stderrTask.GetAwaiter().GetResult(),$encoding)
        if($null -eq $exitCode) {throw 'Process handle did not provide an exit code'}
        return [int]$exitCode
    } finally {
        # Wait only; never kill a GPU process or abandon it on an output error.
        if($started -and -not $process.HasExited) {$process.WaitForExit()}
        $process.Dispose()
    }
}
