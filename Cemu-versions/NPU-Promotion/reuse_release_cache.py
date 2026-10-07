"""Reuse the tested Release build only for files proven byte-identical.

Both builds use Q:/source and Q:/build with the same pinned toolchain. Ninja
still reconfigures and rebuilds changed inputs; no timestamp is forged for a
file whose contents differ. Other variants receive separate clean builds.
"""
from pathlib import Path
import json,os,shutil
from prepare import HERE,VERSIONS,sha,write
old=VERSIONS/'Test/LSFG-Release'
new=HERE/'Release'
assert (new/'evidence/integrated.json').exists()
assert not (new/'build').exists()
shutil.copytree(old/'build',new/'build')
matched=0
for base,dirs,files in os.walk(new/'source'):
    dirs[:]=[d for d in dirs if d not in ['.git','bin','vcpkg','metal-cpp']]
    for name in files:
        p=Path(base)/name
        rel=p.relative_to(new/'source');other=old/'source'/rel
        if other.is_file() and p.stat().st_size==other.stat().st_size and sha(p)==sha(other):
            stat=other.stat();os.utime(p,ns=(stat.st_atime_ns,stat.st_mtime_ns));matched+=1
write(new/'evidence/cache-reuse.json',json.dumps({'source':'Test/LSFG-Release/build','byte_identical_source_files':matched,'unchanged_virtual_paths':['Q:/source','Q:/build'],'other_variants':'separate clean builds','ninja_rebuilds_changed_inputs':True},indent=2)+'\n')
print('Release cache copied; identical source timestamps retained:',matched)
