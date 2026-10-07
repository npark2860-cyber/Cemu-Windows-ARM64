from pathlib import Path
r=Path('generic-voice-haptics')
p=r/'src/Cafe/OS/common/EnhancedSoundDualSenseService.h';s=p.read_text();s=s.replace('s_hapticPlayer.Tick(now, !outputConfigured)','s_hapticPlayer.Tick(now, !outputConfigured && s_hapticPlayer.IsActive())').replace('s_loopClipCache;\n\n\n','s_loopClipCache;\n\n');p.write_text(s)
p=r/'src/Cafe/OS/libs/snd_core/ax_voice.cpp';s=p.read_text();s=s.replace('maximumSend = std::max(maximumSend,','maximumSend = std::max<uint16>(maximumSend,');p.write_text(s)
