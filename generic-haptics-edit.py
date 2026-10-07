from pathlib import Path
root=Path('generic-voice-haptics')
def edit(path,changes):
 p=root/path;s=p.read_text(encoding='utf-8')
 for a,b in changes:
  assert a in s,(path,a)
  s=s.replace(a,b)
 p.write_text(s,encoding='utf-8',newline='\n')
edit('src/Cafe/OS/common/EnhancedSoundDualSenseService.h',[
 ('#include "Cafe/OS/common/EnhancedHapticEngine.h"','#include "Cafe/OS/common/EnhancedHapticMixer.h"'),
 ('EnhancedHapticEngine::Player s_hapticPlayer','EnhancedHapticEngine::Mixer s_hapticPlayer'),
 ('\tinline std::mutex s_playbackMutex;\n\tinline uint64_t s_nextPlaybackId{ 1 };\n\tinline uint64_t s_activePlaybackId{};\n',''),
 ('uint64_t* playbackId = nullptr, std::string* error = nullptr)','uint64_t* playbackId = nullptr, std::string* error = nullptr, bool voiceBound = false)'),
 ('''\t\tuint64_t id;
\t\t{
\t\t\tstd::scoped_lock lock(s_playbackMutex);
\t\t\tif (s_nextPlaybackId == 0)
\t\t\t\ts_nextPlaybackId = 1;
\t\t\tid = s_nextPlaybackId++;
\t\t\ts_activePlaybackId = id;
\t\t\ts_hapticPlayer.Play(std::move(clip), gain);
\t\t}''','''\t\tconst uint64_t id = s_hapticPlayer.Play(std::move(clip), gain, voiceBound);
\t\tif (!id)
\t\t{
\t\t\tif (error) *error = "Haptic playback capacity exhausted";
\t\t\treturn false;
\t\t}'''),
 ('''\t\tstd::scoped_lock lock(s_playbackMutex);
\t\tif (playbackId != 0 && s_activePlaybackId != playbackId)
\t\t\treturn;
\t\ts_activePlaybackId = 0;
\t\ts_hapticPlayer.Stop();''','\t\ts_hapticPlayer.Stop(playbackId);'),
 ('\n\n\tinline bool ApplyAdaptiveTriggerBowRaw','\n\tinline void UpdateVoiceHaptics(uint64_t id, float gain)\n\t{\n\t\ts_hapticPlayer.Update(id, gain);\n\t}\n\n\tinline bool ApplyAdaptiveTriggerBowRaw'),
 ('s_hapticPlayer.Tick(now)','s_hapticPlayer.Tick(now, !outputConfigured)'),
 ('uint64_t* = nullptr, std::string* error = nullptr)','uint64_t* = nullptr, std::string* error = nullptr, bool = false)'),
 ('inline void StopHaptics(uint64_t = 0) {}','inline void StopHaptics(uint64_t = 0) {}\n\tinline void UpdateVoiceHaptics(uint64_t, float) {}')])
edit('src/Cafe/OS/common/EnhancedSoundRouter.h',[
 ('bool hapticLoop{};','bool hapticLoop{};\n\t\tbool hapticFollowTv{};'),
 ('a.hapticLoop == b.hapticLoop;','a.hapticLoop == b.hapticLoop &&\n\t\t\ta.hapticFollowTv == b.hapticFollowTv;'),
 ('rule.hapticLoop\n','rule.hapticLoop,\n\t\t\t\t\trule.hapticFollowTv\n')])
p=root/'src/Cafe/GraphicPack/GraphicPack2.cpp';s=p.read_text(encoding='utf-8');a=s.index('\t\t\t\tif (const auto hapticLoop = routes.FindOption("haptic_loop"))');b=s.index('\n\t\t\t}\n',a);block=s[a:b];s=s[:b]+'\n'+block.replace('hapticLoop','hapticFollowTv').replace('haptic_loop','haptic_follow_tv')+s[b:];p.write_text(s,encoding='utf-8',newline='\n')
edit('src/Cafe/OS/libs/snd_core/ax_voice.cpp',[
 ('bool loop{};','bool loop{};\n\t\tbool followTv{};'),
 ('\t\ts_enhancedSoundHapticState[index] = {};','\t\tif (s_enhancedSoundHapticState[index].playbackId)\n\t\t\tEnhancedSoundDualSenseService::StopHaptics(s_enhancedSoundHapticState[index].playbackId);\n\t\ts_enhancedSoundHapticState[index] = {};'),
 ('if (hapticState.loop && hapticState.playbackId != 0)','if (hapticState.playbackId != 0)'),
 ('hapticState.loop != route->hapticLoop;','hapticState.loop != route->hapticLoop ||\n\t\t\t\thapticState.followTv != route->hapticFollowTv;'),
 ('route->hapticLoop, &playbackId, &error);','route->hapticLoop, &playbackId, &error, true);'),
 ('hapticState.loop = route->hapticLoop;','hapticState.loop = route->hapticLoop;\n\t\t\t\thapticState.followTv = route->hapticFollowTv;'),
 ('    void __AXVPBResetVoices()\n    {','    void __AXVPBResetVoices()\n    {\n        for (auto& state : s_enhancedSoundHapticState)\n        {\n            if (state.playbackId) EnhancedSoundDualSenseService::StopHaptics(state.playbackId);\n            state = {};\n        }')])
edit('src/Cafe/OS/libs/snd_core/ax_internal.h',[
 ('\t// AXIst\n','\tvoid AXUpdateVoiceHaptics(uint32 index, const AXVPBInternal_t* voice);\n\n\t// AXIst\n')])
# Publish the synchronized snapshot even for inactive/protected allocated voices.
edit('src/Cafe/OS/libs/snd_core/ax_ist.cpp',[
 ('\t\t\t\t\t\tvpb->sync = 0;\n\t\t\t\t\t}\n\t\t\t\t}\n','\t\t\t\t\t\tvpb->sync = 0;\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t\tAXUpdateVoiceHaptics(index, internalShadowCopy);\n')])
