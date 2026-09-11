from pathlib import Path


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


# Extend the existing report-only jit-iml-ra-hotspot diagnostics from
# 0x0420CB80 to the resolved 0x02A281A0 hotspot as well. This script runs
# after Apply-ARM64JitRootCause.py has installed the base instrumentation.
p = Path("src/Cafe/HW/Espresso/Recompiler/IML/IMLRegisterAllocator.cpp")
t = p.read_text(encoding="utf-8")
old = '''static bool IMLRA_IsJitPerfHotspot(const IMLSegment* imlSegment)
{
\tif (imlSegment->ppcAddress == 0x0420CB80u)
\t\treturn true;
\treturn imlSegment->isEnterable && imlSegment->enterPPCAddress == 0x0420CB80u;
}
'''
new = '''static bool IMLRA_IsJitPerfHotspot(const IMLSegment* imlSegment)
{
\tif (imlSegment->ppcAddress == 0x0420CB80u || imlSegment->ppcAddress == 0x02A281A0u)
\t\treturn true;
\treturn imlSegment->isEnterable &&
\t\t(imlSegment->enterPPCAddress == 0x0420CB80u || imlSegment->enterPPCAddress == 0x02A281A0u);
}
'''
t = replace_once(t, old, new, "ARM64 JIT RA hotspot set")
p.write_text(t, encoding="utf-8", newline="\n")

p = Path("src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp")
t = p.read_text(encoding="utf-8")
old = '''\t\tconst bool diagJitHotspot = RuntimeExperiments::Enabled("jit-iml-ra-hotspot") &&
\t\t\t(segIt->ppcAddress == 0x0420CB80u || (segIt->isEnterable && segIt->enterPPCAddress == 0x0420CB80u));
'''
new = '''\t\tconst bool diagJitHotspot = RuntimeExperiments::Enabled("jit-iml-ra-hotspot") &&
\t\t\t(segIt->ppcAddress == 0x0420CB80u || segIt->ppcAddress == 0x02A281A0u ||
\t\t\t (segIt->isEnterable && (segIt->enterPPCAddress == 0x0420CB80u || segIt->enterPPCAddress == 0x02A281A0u)));
'''
t = replace_once(t, old, new, "ARM64 JIT native hotspot set")
p.write_text(t, encoding="utf-8", newline="\n")

branch_shape = Path(__file__).with_name("Extend-ARM64JitBranchShape.py")
exec(compile(branch_shape.read_text(encoding="utf-8"), str(branch_shape), "exec"))

print("[arm64-jit-root-cause-02a] extended report-only IML/RA/native correlation")
