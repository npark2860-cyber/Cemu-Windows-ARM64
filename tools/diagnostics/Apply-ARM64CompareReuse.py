from pathlib import Path


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


p = Path("src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp")
t = p.read_text(encoding="utf-8")

include_line = '#include "diagnostics/RuntimeExperiments.h"\n'
if include_line not in t:
    anchor = '#include "diagnostics/RuntimeDiagnostics.h"\n'
    if anchor not in t:
        anchor = '#include "HW/Espresso/PPCState.h"\n'
    if anchor not in t:
        raise RuntimeError("ARM64 compare reuse: include anchor not found")
    t = t.replace(anchor, anchor + include_line, 1)

func_signature = 'bool PPCRecompiler_generateAArch64Code(struct PPCRecFunction_t* PPCRecFunction, struct ppcImlGenContext_t* ppcImlGenContext)\n'
helper_block = '''static bool PPCRecompilerAArch64Gen_IsSameCompare(const IMLInstruction* a, const IMLInstruction* b)
{
\tif (a->type != b->type)
\t\treturn false;
\tif (a->type == PPCREC_IML_TYPE_COMPARE)
\t\treturn a->op_compare.regA == b->op_compare.regA && a->op_compare.regB == b->op_compare.regB;
\tif (a->type == PPCREC_IML_TYPE_COMPARE_S32)
\t\treturn a->op_compare_s32.regA == b->op_compare_s32.regA && a->op_compare_s32.immS32 == b->op_compare_s32.immS32;
\treturn false;
}

'''
t = replace_once(t, func_signature, helper_block + func_signature, "ARM64 compare reuse helper")

context_anchor = '\tAArch64GenContext_t aarch64GenContext{&allocator};\n'
context_block = context_anchor + '\tconst bool expCompareReuse = RuntimeExperiments::Enabled("arm64-compare-reuse");\n'
t = replace_once(t, context_anchor, context_block, "ARM64 compare reuse runtime gate")

compare_anchor = '''\t\t\telse if (imlInstruction->type == PPCREC_IML_TYPE_COMPARE)
\t\t\t{
\t\t\t\taarch64GenContext.compare(imlInstruction);
\t\t\t}
\t\t\telse if (imlInstruction->type == PPCREC_IML_TYPE_COMPARE_S32)
\t\t\t{
\t\t\t\taarch64GenContext.compare_s32(imlInstruction);
\t\t\t}
'''
compare_block = '''\t\t\telse if (imlInstruction->type == PPCREC_IML_TYPE_COMPARE)
\t\t\t{
\t\t\t\taarch64GenContext.compare(imlInstruction);
\t\t\t\tif (expCompareReuse)
\t\t\t\t{
\t\t\t\t\tsize_t extra = 0;
\t\t\t\t\tfor (size_t lookAhead = 1; lookAhead < 4 && (i + lookAhead) < segIt->imlList.size(); ++lookAhead)
\t\t\t\t\t{
\t\t\t\t\t\tIMLInstruction* nextIns = segIt->imlList.data() + i + lookAhead;
\t\t\t\t\t\tif (!PPCRecompilerAArch64Gen_IsSameCompare(imlInstruction, nextIns))
\t\t\t\t\t\t\tbreak;
\t\t\t\t\t\tWReg regR = gpReg<WReg>(nextIns->op_compare.regR);
\t\t\t\t\t\tCond cond = ImlCondToArm64Cond(nextIns->op_compare.cond);
\t\t\t\t\t\taarch64GenContext.cset(regR, cond);
\t\t\t\t\t\textra++;
\t\t\t\t\t}
\t\t\t\t\ti += extra;
\t\t\t\t}
\t\t\t}
\t\t\telse if (imlInstruction->type == PPCREC_IML_TYPE_COMPARE_S32)
\t\t\t{
\t\t\t\taarch64GenContext.compare_s32(imlInstruction);
\t\t\t\tif (expCompareReuse)
\t\t\t\t{
\t\t\t\t\tsize_t extra = 0;
\t\t\t\t\tfor (size_t lookAhead = 1; lookAhead < 4 && (i + lookAhead) < segIt->imlList.size(); ++lookAhead)
\t\t\t\t\t{
\t\t\t\t\t\tIMLInstruction* nextIns = segIt->imlList.data() + i + lookAhead;
\t\t\t\t\t\tif (!PPCRecompilerAArch64Gen_IsSameCompare(imlInstruction, nextIns))
\t\t\t\t\t\t\tbreak;
\t\t\t\t\t\tWReg regR = gpReg<WReg>(nextIns->op_compare_s32.regR);
\t\t\t\t\t\tCond cond = ImlCondToArm64Cond(nextIns->op_compare_s32.cond);
\t\t\t\t\t\taarch64GenContext.cset(regR, cond);
\t\t\t\t\t\textra++;
\t\t\t\t\t}
\t\t\t\t\ti += extra;
\t\t\t\t}
\t\t\t}
'''
t = replace_once(t, compare_anchor, compare_block, "ARM64 consecutive compare flag reuse")

p.write_text(t, encoding="utf-8", newline="\n")
print("[arm64-compare-reuse] installed")
