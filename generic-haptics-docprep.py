from pathlib import Path
r=Path('generic-voice-haptics')
p=r/'src/Cafe/OS/common/EnhancedSoundDualSenseService.h'
s=p.read_text();s=s.replace('\tinline std::unique_ptr<std::jthread> s_worker;\n','');s=s.replace('\tinline uint64_t s_triggerRevision{};','\tinline uint64_t s_triggerRevision{};\n\t// Stop/join the worker before destroying the shared state above.\n\tinline std::unique_ptr<std::jthread> s_worker;');p.write_text(s)
# Put the game-specific mapping and assets exclusively in the optional pack.
import shutil
src=Path('mastercycle-haptics/MasterCycleHapticsPreview/CombinedDiagnostic')
dst=r/'enhanced_sound_policies/BreathOfTheWild/MasterCycleHaptics'
shutil.copytree(src,dst,dirs_exist_ok=True)
p=dst/'sound_routes.ini';s=p.read_text();s=s.replace('haptic_gain = 1.0','haptic_gain = 1.0\nhaptic_follow_tv = true');p.write_text(s)
p=dst/'rules.txt';s=p.read_text().replace('CombinedDiagnostic - PREVIEW','Voice Follow - TEST').replace('/CombinedDiagnostic','/Voice Follow').replace('Validation preview. Enable only ONE Master Cycle profile. No automatic low/mid/high speed detection. Single-player haptic interruption applies; see README. Requires existing Enhanced Sound Experience.','Requires the generic voice-haptics test build. Enable only this Master Cycle profile. Follows TV sends and voice lifetime; no speed-state detection. See README.');p.write_text(s)
for name in ['BRANCH_POLICY.md','ACTIVE_BRANCH_ROLES.md']:
 p=r/name;s=p.read_text(encoding='utf-8').replace('`test/se-fingerprint-index-v1`','`test_SE`');p.write_text(s,encoding='utf-8')
p=r/'ACTIVE_BRANCH_ROLES.md';s=p.read_text(encoding='utf-8');a=s.index('- [Test]: current dedicated workflow');b=s.index('\n',a);s=s[:a]+'- [Test]: `test_SE` is the source branch. Its inherited `final-adreno-compat-arm64.yml` currently guards the stock Release ref; do not dispatch it as a Test build. `build/test-se-once` is only a build carrier. The generic voice-haptics PR does not alter or dispatch workflows.'+s[b:];p.write_text(s,encoding='utf-8')
p=r/'README.md';s=p.read_text(encoding='utf-8');s=s.replace('### Links:', '### Test_SE haptics\n\n[Generic voice-haptics design, configuration and validation](docs/GENERIC_VOICE_HAPTICS.md).\n[Current Test_SE handoff](CURRENT_HANDOFF.md).\n\n### Links:');p.write_text(s,encoding='utf-8')
