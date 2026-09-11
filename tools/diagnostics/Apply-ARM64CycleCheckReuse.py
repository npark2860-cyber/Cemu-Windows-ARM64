from pathlib import Path


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


p = Path("src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp")
t = p.read_text(encoding="utf-8")

anchor = '''\t\t\telse if (imlInstruction->type == PPCREC_IML_TYPE_CJUMP_CYCLE_CHECK)\n\t\t\t{\n\t\t\t\taarch64GenContext.conditionalJumpCycleCheck(segIt);\n\t\t\t}\n'''

replacement = '''\t\t\telse if (imlInstruction->type == PPCREC_IML_TYPE_CJUMP_CYCLE_CHECK)\n\t\t\t{\n\t\t\t\tbool reuseCycleCountValue = false;\n\t\t\t\tif (RuntimeExperiments::Enabled("arm64-cyclecheck-reuse") && i > 0)\n\t\t\t\t{\n\t\t\t\t\tIMLInstruction* previousInstruction = segIt->imlList.data() + (i - 1);\n\t\t\t\t\treuseCycleCountValue = previousInstruction->type == PPCREC_IML_TYPE_MACRO &&\n\t\t\t\t\t\tpreviousInstruction->operation == PPCREC_IML_MACRO_COUNT_CYCLES;\n\t\t\t\t}\n\n\t\t\t\tif (reuseCycleCountValue)\n\t\t\t\t{\n\t\t\t\t\taarch64GenContext.prepareJump(NegativeRegValueJumpInfo{\n\t\t\t\t\t\t.target = segIt->nextSegmentBranchTaken,\n\t\t\t\t\t\t.regValue = TEMP_GPR1.WReg,\n\t\t\t\t\t});\n\t\t\t\t\tif (RuntimeExperiments::Enabled("jit-iml-ra-hotspot") &&\n\t\t\t\t\t\t(segIt->ppcAddress == 0x02A281A0u || segIt->ppcAddress == 0x0420CB80u))\n\t\t\t\t\t{\n\t\t\t\t\t\tcemuLog_log(LogType::Force,\n\t\t\t\t\t\t\t"[ARM64_CYCLECHECK_REUSE] ppc=0x{:08x} iml={} reuse=TEMP_GPR1",\n\t\t\t\t\t\t\tsegIt->ppcAddress, i);\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t\telse\n\t\t\t\t{\n\t\t\t\t\taarch64GenContext.conditionalJumpCycleCheck(segIt);\n\t\t\t\t}\n\t\t\t}\n'''

t = replace_once(t, anchor, replacement, "ARM64 cycle-check TEMP_GPR1 reuse")
p.write_text(t, encoding="utf-8", newline="\n")

print("[arm64-cyclecheck-reuse] installed")
