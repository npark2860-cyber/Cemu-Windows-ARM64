$ErrorActionPreference='Stop'
$global:LASTEXITCODE=0
$env:PYTHONIOENCODING='utf-8'
git diff --check -- src/Cafe/OS/libs/snd_core/ax_voice.cpp src/Cafe/OS/common/EnhancedSoundCueDiagnostic.h
if (-not (Test-Path 'src/Cafe/OS/common/EnhancedSoundCueDiagnostic.h')) { throw 'cue diagnostic header missing' }
$ax = Get-Content 'src/Cafe/OS/libs/snd_core/ax_voice.cpp' -Raw
$diag = Get-Content 'src/Cafe/OS/common/EnhancedSoundCueDiagnostic.h' -Raw
if ($ax -notmatch 'EnhancedSoundCueDiagnostic::Record') { throw 'cue record hook missing' }
if ($ax -notmatch 'ResolveSourceCandidates') { throw 'V2 candidate source path missing' }
if ($diag -notmatch 'enhanced_sound_cue_capture\.csv') { throw 'cue CSV output missing' }
if ($diag -notmatch 'source_path,track_name,route_match') { throw 'cue CSV schema incomplete' }

if($LASTEXITCODE -ne 0) {throw "Preprocessing step failed"}
