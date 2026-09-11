from pathlib import Path


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


# Extend the report-only JIT hotspot set to all currently established BOTW
# RUNNING-only hotspots. No generated runtime behavior is changed.
p = Path("src/Cafe/HW/Espresso/Recompiler/IML/IMLRegisterAllocator.cpp")
t = p.read_text(encoding="utf-8")
old = '''static bool IMLRA_IsJitPerfHotspot(const IMLSegment* imlSegment)
{
\tif (imlSegment->ppcAddress == 0x0420CB80u || imlSegment->ppcAddress == 0x02A281A0u)
\t\treturn true;
\treturn imlSegment->isEnterable &&
\t\t(imlSegment->enterPPCAddress == 0x0420CB80u || imlSegment->enterPPCAddress == 0x02A281A0u);
}
'''
new = '''static bool IMLRA_IsJitPerfHotspot(const IMLSegment* imlSegment)
{
\tconst uint32 ppc = imlSegment->ppcAddress;
\tconst uint32 enter = imlSegment->enterPPCAddress;
\tif (ppc == 0x0420CB80u || ppc == 0x02A281A0u || ppc == 0x03B84854u ||
\t\tppc == 0x0399B4DCu || ppc == 0x03818C6Cu)
\t\treturn true;
\treturn imlSegment->isEnterable &&
\t\t(enter == 0x0420CB80u || enter == 0x02A281A0u || enter == 0x03B84854u ||
\t\t enter == 0x0399B4DCu || enter == 0x03818C6Cu);
}
'''
t = replace_once(t, old, new, "ARM64 JIT RA expanded hotspot set")
p.write_text(t, encoding="utf-8", newline="\n")


p = Path("src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp")
t = p.read_text(encoding="utf-8")
old = '''\t\tconst bool diagJitHotspot = RuntimeExperiments::Enabled("jit-iml-ra-hotspot") &&
\t\t\t(segIt->ppcAddress == 0x0420CB80u || segIt->ppcAddress == 0x02A281A0u ||
\t\t\t (segIt->isEnterable && (segIt->enterPPCAddress == 0x0420CB80u || segIt->enterPPCAddress == 0x02A281A0u)));
'''
new = '''\t\tconst uint32 diagPpc = segIt->ppcAddress;
\t\tconst uint32 diagEnter = segIt->enterPPCAddress;
\t\tconst bool diagJitHotspot = RuntimeExperiments::Enabled("jit-iml-ra-hotspot") &&
\t\t\t(diagPpc == 0x0420CB80u || diagPpc == 0x02A281A0u || diagPpc == 0x03B84854u ||
\t\t\t diagPpc == 0x0399B4DCu || diagPpc == 0x03818C6Cu ||
\t\t\t (segIt->isEnterable && (diagEnter == 0x0420CB80u || diagEnter == 0x02A281A0u ||
\t\t\t  diagEnter == 0x03B84854u || diagEnter == 0x0399B4DCu || diagEnter == 0x03818C6Cu)));
'''
t = replace_once(t, old, new, "ARM64 JIT native expanded hotspot set")

# Add a compile-time-only branch-shape summary for any compiled function that
# contains one of the established hotspots. Anchor only on the generation
# comment because earlier diagnostic transforms intentionally insert runtime
# gates immediately after aarch64GenContext construction.
anchor = '''\t// generate iml instruction code
'''
block = '''\tif (RuntimeExperiments::Enabled("jit-iml-ra-hotspot"))
\t{
\t\tbool diagBranchShapeFunction = false;
\t\tfor (IMLSegment* seg : ppcImlGenContext->segmentList2)
\t\t{
\t\t\tconst uint32 ppc = seg->ppcAddress;
\t\t\tconst uint32 enter = seg->enterPPCAddress;
\t\t\tif (ppc == 0x0420CB80u || ppc == 0x02A281A0u || ppc == 0x03B84854u ||
\t\t\t\tppc == 0x0399B4DCu || ppc == 0x03818C6Cu ||
\t\t\t\t(seg->isEnterable && (enter == 0x0420CB80u || enter == 0x02A281A0u || enter == 0x03B84854u ||
\t\t\t\t enter == 0x0399B4DCu || enter == 0x03818C6Cu)))
\t\t\t{
\t\t\t\tdiagBranchShapeFunction = true;
\t\t\t\tbreak;
\t\t\t}
\t\t}

\t\tif (diagBranchShapeFunction)
\t\t{
\t\t\tuint32 totalIml = 0;
\t\t\tuint32 directJump = 0;
\t\t\tuint32 conditionalJump = 0;
\t\t\tuint32 cycleCheck = 0;
\t\t\tuint32 branchToReg = 0;
\t\t\tuint32 branchLink = 0;
\t\t\tuint32 branchFar = 0;
\t\t\tuint32 leave = 0;
\t\t\tuint32 hle = 0;
\t\t\tfor (IMLSegment* seg : ppcImlGenContext->segmentList2)
\t\t\t{
\t\t\t\tfor (const IMLInstruction& inst : seg->imlList)
\t\t\t\t{
\t\t\t\t\t++totalIml;
\t\t\t\t\tif (inst.type == PPCREC_IML_TYPE_JUMP)
\t\t\t\t\t\t++directJump;
\t\t\t\t\telse if (inst.type == PPCREC_IML_TYPE_CONDITIONAL_JUMP)
\t\t\t\t\t\t++conditionalJump;
\t\t\t\t\telse if (inst.type == PPCREC_IML_TYPE_CJUMP_CYCLE_CHECK)
\t\t\t\t\t\t++cycleCheck;
\t\t\t\t\telse if (inst.type == PPCREC_IML_TYPE_MACRO)
\t\t\t\t\t{
\t\t\t\t\t\tif (inst.operation == PPCREC_IML_MACRO_B_TO_REG) ++branchToReg;
\t\t\t\t\t\telse if (inst.operation == PPCREC_IML_MACRO_BL) ++branchLink;
\t\t\t\t\t\telse if (inst.operation == PPCREC_IML_MACRO_B_FAR) ++branchFar;
\t\t\t\t\t\telse if (inst.operation == PPCREC_IML_MACRO_LEAVE) ++leave;
\t\t\t\t\t\telse if (inst.operation == PPCREC_IML_MACRO_HLE) ++hle;
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[JIT_BRANCH_SHAPE] func=0x{:08x} segments={} iml={} direct_jump={} conditional_jump={} cycle_check={} table_b_to_reg={} table_bl={} table_b_far={} leave={} hle={}",
\t\t\t\tPPCRecFunction->ppcAddress, ppcImlGenContext->segmentList2.size(), totalIml,
\t\t\t\tdirectJump, conditionalJump, cycleCheck, branchToReg, branchLink, branchFar, leave, hle);
\t\t}
\t}

\t// generate iml instruction code
'''
t = replace_once(t, anchor, block, "ARM64 JIT branch-shape summary")
p.write_text(t, encoding="utf-8", newline="\n")

print("[arm64-jit-branch-shape] expanded report-only hotspot/branch-shape diagnostics")
