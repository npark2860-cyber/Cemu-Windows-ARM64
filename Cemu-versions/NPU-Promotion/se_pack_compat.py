"""Validate this known SE policy pack, then correct its format declaration.

This applies only to Release+SE. It does not enable SE packs in other roles,
change audio/haptic policies, or launch Cemu.
"""
from pathlib import Path
from datetime import datetime,timezone
import configparser,hashlib,json,math,re

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def correct_pack(root):
    root=Path(root)
    assert root.name=='Release+SE'
    source=root/'source'
    parser=(source/'src/Cafe/GraphicPack/GraphicPack2.cpp').read_text(encoding='utf-8')
    upstream=source/'enhanced_sound_policies/BreathOfTheWild/DualSenseExperienceUnified/rules.txt'
    assert re.search(r'(?m)^version\s*=\s*8\s*$',upstream.read_text(encoding='utf-8'))
    pack=root/'runtime/portable/graphicPacks/downloadedGraphicPacks/BreathOfTheWild/DualSenseExperience'
    if not pack.exists():return {'status':'PACK_NOT_INSTALLED'}
    rules=pack/'rules.txt';before=rules.read_bytes()
    definitions=configparser.ConfigParser(interpolation=None)
    definitions.read_string(before.decode('utf-8-sig'))
    assert definitions.sections()==['Definition']
    definition=definitions['Definition']
    assert set(definition)<= {'titleids','name','path','description','version','default'}
    assert definition['path'].strip('"')=='The Legend of Zelda: Breath of the Wild/Enhancements/DualSense Experience - Unified'
    assert definition['version'].strip() in ['8','9']
    assert all(re.fullmatch(r'[0-9a-fA-F]{16}',x.strip()) for x in definition['titleids'].split(','))
    routes=configparser.ConfigParser(interpolation=None)
    routes.read(pack/'sound_routes.ini',encoding='utf-8-sig')
    supported={'source','track','mode','gain','tv_volume','haptic','haptic_gain','haptic_follow_tv','haptic_loop'}
    # Check the actual installed policies against this exact SE parser.
    for key in supported:assert 'routes.FindOption("'+key+'")' in parser,key
    assets=set()
    for section in routes.sections():
        assert section.startswith('Route.')
        route=routes[section]
        assert set(route)<=supported,(section,set(route)-supported)
        assert route.get('source','') or route.get('track','')
        if 'mode' in route:assert route['mode'] in ['add_drc','spatial_drc']
        if 'gain' in route:assert 0<=int(route['gain'],0)<=65535
        if 'tv_volume' in route:assert 0<=int(route['tv_volume'])<=100
        for key in ['haptic_loop','haptic_follow_tv']:
            if key in route:assert route[key].lower() in ['true','false','yes','no','1','0']
        if 'haptic_gain' in route:
            value=float(route['haptic_gain']);assert math.isfinite(value) and 0<=value<=1
        if 'haptic' in route:
            name=Path(route['haptic']);assert not name.is_absolute() and '..' not in name.parts and name.suffix.lower()=='.bnvib'
            asset=pack/'haptics'/name;assert asset.is_file() and asset.stat().st_size>0,str(asset)
            assets.add(name.as_posix())
        assert 'mode' in route or 'haptic' in route
    # Newer format features cannot be hidden in additional patch/shader files.
    assert {p.name for p in pack.iterdir() if p.is_file()} <= {'rules.txt','sound_routes.ini','UPSTREAM_README_KO.txt','upstream-v3-provenance.json'}
    protected={p.relative_to(pack).as_posix():digest(p) for p in pack.rglob('*') if p.is_file() and p!=rules}
    evidence=root/'evidence/se-pack-format-fix';evidence.mkdir(parents=True,exist_ok=True)
    if definition['version'].strip()=='9':
        backup=evidence/'rules.version9.original.txt'
        if backup.exists():assert backup.read_bytes()==before
        else:backup.write_bytes(before)
        after,count=re.subn(rb'(?m)^(version\s*=\s*)9(?=\s*$)',rb'\g<1>8',before)
        assert count==1 and len(after)==len(before)
        assert sum(a!=b for a,b in zip(before,after))==1
        rules.write_bytes(after)
    else:after=before
    assert all(digest(pack/name)==value for name,value in protected.items())
    result={'status':'SE_PACK_FORMAT_8_VERIFIED','time':datetime.now(timezone.utc).isoformat(),
        'role':'Release+SE','rules':str(rules),'previous_version':definition['version'].strip(),'current_version':'8',
        'change':'Only the format version digit; existing SE parser supports every route option used.',
        'route_sections':len(routes.sections()),'referenced_haptic_assets':len(assets),
        'unchanged_policy_and_asset_files':protected,'before_sha256':hashlib.sha256(before).hexdigest(),
        'after_sha256':hashlib.sha256(after).hexdigest(),'mlc_modified':False,'cemu_executed':False,
        'runtime_game_or_controller_tested':False,'reload_required':'Restart Cemu to reload its in-memory pack definitions.'}
    report=evidence/('applied.json' if definition['version'].strip()=='9' else 'rechecked.json')
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return {k:v for k,v in result.items() if k!='unchanged_policy_and_asset_files'}

if __name__=='__main__':print(json.dumps(correct_pack(Path(__file__).resolve().parent/'Release+SE'),ensure_ascii=False,indent=2))
