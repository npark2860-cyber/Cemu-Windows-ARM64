from pathlib import Path
import zipfile,hashlib,configparser,json
r=Path('generic-voice-haptics');old=r/'enhanced_sound_policies/BreathOfTheWild/MasterCycleHaptics';dst=r/'enhanced_sound_policies/BreathOfTheWild/DualSenseExperienceUnified'
assert old.is_dir() and not dst.exists()
old.rename(dst)
p=Path(r'C:\Users\angel\Downloads\BOTW_DualSenseExperience_UI_Sheikah_v3.zip')
with zipfile.ZipFile(p) as z:
 prefix='BOTW_DualSenseExperience_UI_Sheikah_v3/'
 upstream=z.read(prefix+'sound_routes.ini').decode('utf-8-sig')
 original=configparser.ConfigParser(interpolation=None);original.read_string(upstream)
 motor=(dst/'sound_routes.ini').read_text()
 (dst/'sound_routes.ini').write_text('; Exact motorcycle routes must precede the upstream wildcard routes.\n\n'+motor+'\n; Original UI/Sheikah v3 routes follow, unchanged.\n\n'+upstream,encoding='utf-8')
 assets={}
 for name in ['PresetPiton.bnvib','UIFadeIn.bnvib','UiRollOver.bnvib']:
  data=z.read(prefix+'haptics/'+name);(dst/'haptics'/name).write_bytes(data);assets[name]=hashlib.sha256(data).hexdigest()
 (dst/'UPSTREAM_README_KO.txt').write_bytes(z.read(prefix+'README_KO.txt'))
 print('upstream routes:',len(original.sections()),'combined:',len(original.sections())+8)
 provenance={'source_archive':p.name,'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'original_route_count':len(original.sections()),'original_routes':{s:dict(original[s]) for s in original.sections()},'original_asset_sha256':assets}
 (dst/'upstream-v3-provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (dst/'rules.txt').write_text('''[Definition]
titleIds = 00050000101C9300,00050000101C9400,00050000101C9500
name = DualSense Experience - UI + Sheikah + Master Cycle - TEST
path = "The Legend of Zelda: Breath of the Wild/Enhancements/DualSense Experience - Unified"
description = "Preserves UI/Sheikah v3 sound and haptic settings; adds voice-follow Master Cycle haptics. Requires generic voice-haptics Test_SE build. Disable overlapping older packs. See README."
version = 8
default = false
''',encoding='utf-8')
for name in ['CURRENT_HANDOFF.md','docs/GENERIC_VOICE_HAPTICS.md','tests/enhanced_sound/CMakeLists.txt']:
 p=r/name;b=p.read_bytes();b=b.replace(b'BreathOfTheWild/MasterCycleHaptics',b'BreathOfTheWild/DualSenseExperienceUnified');p.write_bytes(b)
p=r/'tests/enhanced_sound/haptic_tests.cpp';s=p.read_text().replace('count == 8','count == 11').replace('all eight haptic patterns','all eleven haptic patterns');p.write_text(s)
