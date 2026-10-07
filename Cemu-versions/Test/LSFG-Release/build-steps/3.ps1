$ErrorActionPreference = 'Stop'
$main = 'src/gui/wxgui/MainWindow.cpp'
$m = Get-Content $main -Raw
$oldMain = 'return BUILD_VERSION_WITH_NAME_STRING;'
$newMain = 'return wxASCII_STR("Cemu ARM64");'
if (([regex]::Matches($m, [regex]::Escape($oldMain))).Count -ne 1) { throw 'MainWindow title anchor count mismatch' }
$m = $m.Replace($oldMain, $newMain)
Set-Content -Path $main -Value $m -NoNewline

$ws = 'src/gui/wxgui/wxWindowSystem.cpp'
$w = Get-Content $ws -Raw
$oldWindow = 'windowText = BUILD_VERSION_WITH_NAME_STRING;'
$newWindow = 'windowText = "Cemu ARM64";'
if (([regex]::Matches($w, [regex]::Escape($oldWindow))).Count -ne 1) { throw 'WindowSystem title anchor count mismatch' }
$w = $w.Replace($oldWindow, $newWindow)
Set-Content -Path $ws -Value $w -NoNewline

git diff --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
git diff -- $main $ws
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
