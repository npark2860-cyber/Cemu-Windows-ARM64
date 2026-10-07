from pathlib import Path
r=Path('generic-voice-haptics')
def replace(path,a,b):
 p=r/path;s=p.read_bytes();a=a.encode();b=b.encode();assert a in s,(path,a);p.write_bytes(s.replace(a,b))
v='src/Cafe/OS/libs/snd_core/ax_voice.cpp'
replace(v,'if (!state.playbackId)','if (!state.playbackId || !(state.loop || state.followTv))')
replace(v,'if (s_enhancedSoundHapticState[index].playbackId)','if (s_enhancedSoundHapticState[index].playbackId &&\n\t\t\t(s_enhancedSoundHapticState[index].loop || s_enhancedSoundHapticState[index].followTv))')
replace(v,'if (hapticState.playbackId != 0)','if (hapticState.playbackId != 0 && (hapticState.loop || hapticState.followTv))')
replace(v,'route->hapticLoop, &playbackId, &error, true);','route->hapticLoop, &playbackId, &error, route->hapticLoop || route->hapticFollowTv);')
replace(v,'    void __AXVPBResetVoices()\n    {','    void __AXVPBResetVoices()\n    {\n        EnhancedSoundDualSenseService::StopHaptics();')
# Only touch these known added lines, keeping the original mixed line endings.
m='src/Cafe/OS/common/EnhancedHapticMixer.h'
replace(m,'\t\t\t\tauto& entry = it->second;\n\t\t\t\tif (auto frame', '\t\t\t\tauto& entry = it->second;\n\t\t\t\t// Do not consume a finite clip while its first AX snapshot is pending.\n\t\t\t\tif (entry.voiceBound && !entry.hasSnapshot)\n\t\t\t\t{\n\t\t\t\t\t++it;\n\t\t\t\t\tcontinue;\n\t\t\t\t}\n\t\t\t\tif (auto frame')
