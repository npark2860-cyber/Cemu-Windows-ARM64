from pathlib import Path
r=Path('generic-voice-haptics')
def ins(path,a,b):
 p=r/path;s=p.read_bytes();a=a.encode();assert a in s,(path,a);p.write_bytes(s.replace(a,b.encode()))
v='src/Cafe/OS/libs/snd_core/ax_voice.cpp'
ins(v,'#include "util/helpers/fspinlock.h"','#include "util/helpers/fspinlock.h"\n#include <atomic>')
ins(v,'bool followTv{};','bool followTv{};\n\t\tbool snapshotLogged{};')
ins(v,'\t\tfloat gain = state.gain;','\t\tfloat gain = state.gain;')
ins(v,'\t\tEnhancedSoundDualSenseService::UpdateVoiceHaptics(state.playbackId, gain);','''\t\tif (!state.snapshotLogged)
\t\t{
\t\t\tstate.snapshotLogged = true;
\t\t\tstatic std::atomic_uint snapshots{0};
\t\t\tif (snapshots.fetch_add(1, std::memory_order_relaxed) < 16)
\t\t\t\tcemuLog_log(LogType::Force, "Haptic AX snapshot: voice={} id={} gain={}", index, state.playbackId, gain);
\t\t}
\t\tEnhancedSoundDualSenseService::UpdateVoiceHaptics(state.playbackId, gain);''')
ins(v,'\t\t\t\thapticState.playbackId = played ? playbackId : 0;','''\t\t\t\thapticState.playbackId = played ? playbackId : 0;
\t\t\t\tstatic std::atomic_uint starts{0};
\t\t\t\tif (starts.fetch_add(1, std::memory_order_relaxed) < 16)
\t\t\t\t\tcemuLog_log(LogType::Force, "Haptic route start: voice={} id={} loop={} followTv={} gain={} played={}",
\t\t\t\t\t\t(uint32)vpb->index, playbackId, route->hapticLoop, route->hapticFollowTv, route->hapticGain, played);''')
v='src/Cafe/OS/common/EnhancedSoundDualSenseService.h'
ins(v,'#include "config/CemuConfig.h"','#include "config/CemuConfig.h"\n#include "Cemu/Logging/CemuLogging.h"')
ins(v,'\t\t\tbool outputConfigured = false;','\t\t\tbool outputConfigured = false;\n\t\t\tbool loggedDevice = false;\n\t\t\tunsigned loggedOutputs = 0;')
ins(v,'\t\t\t\tif (!GetConfig().enhanced_sound_experience)','''\t\t\t\tif (!loggedDevice)
\t\t\t\t{
\t\t\t\t\tloggedDevice = true;
\t\t\t\t\t cemuLog_log(LogType::Force, "Haptic output: eligible USB DualSense detected");
\t\t\t\t}
\t\t\t\tif (!GetConfig().enhanced_sound_experience)''')
ins(v,'\t\t\t\t\t\trumble->SetVibration(hapticFrame->lowLevel, hapticFrame->highLevel);','''\t\t\t\t\t\tif ((hapticFrame->lowLevel || hapticFrame->highLevel) && loggedOutputs < 8)
\t\t\t\t\t\t{
\t\t\t\t\t\t\t++loggedOutputs;
\t\t\t\t\t\t\tcemuLog_log(LogType::Force, "Haptic output send: low={} high={}", hapticFrame->lowLevel, hapticFrame->highLevel);
\t\t\t\t\t\t}
\t\t\t\t\t\trumble->SetVibration(hapticFrame->lowLevel, hapticFrame->highLevel);''')
ins(v,'\t\tcatch (...)','\t\tcatch (const std::exception& error)\n\t\t{\n\t\t\tcemuLog_log(LogType::Force, "Haptic worker stopped: {}", error.what());\n\t\t}\n\t\tcatch (...)')
ins(v,'// Enhanced Sound/Haptics are optional and must never make Cemu fatal.','// Enhanced Sound/Haptics are optional and must never make Cemu fatal.\n\t\t\tcemuLog_log(LogType::Force, "Haptic worker stopped: unknown exception");')
