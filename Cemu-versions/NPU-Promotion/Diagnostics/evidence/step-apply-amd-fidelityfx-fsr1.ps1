$ErrorActionPreference='Stop'
$global:LASTEXITCODE=0
$env:PYTHONIOENCODING='utf-8'
& 'C:\Users\angel\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools/graphics/Apply-FidelityFXFSRExperiment.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& 'C:\Users\angel\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools/graphics/Apply-FidelityFXFSRFullExperiment.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
git diff --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if($LASTEXITCODE -ne 0) {throw "Preprocessing step failed"}
