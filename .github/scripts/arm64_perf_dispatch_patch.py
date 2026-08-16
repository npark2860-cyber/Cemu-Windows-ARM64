from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


path = Path("src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp")
text = path.read_text(encoding="utf-8")

text = replace_once(
    text,
    "bool AArch64GenContext_t::macro(IMLInstruction* imlInstruction)\n{\n\tif (imlInstruction->operation == PPCREC_IML_MACRO_B_TO_REG)",
    "bool AArch64GenContext_t::macro(IMLInstruction* imlInstruction)\n{\n\tstatic_assert(offsetof(PPCRecompilerInstanceData_t, ppcRecompilerDirectJumpTable) == 0);\n\n\tif (imlInstruction->operation == PPCREC_IML_MACRO_B_TO_REG)",
    "assert jump table zero offset",
)

text = replace_once(
    text,
    "\t\tmov(TEMP_GPR1.WReg, offsetof(PPCRecompilerInstanceData_t, ppcRecompilerDirectJumpTable));\n\t\tadd(TEMP_GPR1.WReg, TEMP_GPR1.WReg, branchDstReg, ShMod::LSL, 1);\n\t\tldr(TEMP_GPR1.XReg, AdrExt(PPC_REC_INSTANCE_REG, TEMP_GPR1.WReg, ExtMod::UXTW));",
    "\t\t// The jump table is the first member of PPCRecompilerInstanceData_t, so its base is x27.\n\t\t// Guest PPC addresses are byte addresses; each table entry is 8 bytes for each 4-byte PPC instruction.\n\t\tlsl(TEMP_GPR1.WReg, branchDstReg, 1);\n\t\tldr(TEMP_GPR1.XReg, AdrExt(PPC_REC_INSTANCE_REG, TEMP_GPR1.WReg, ExtMod::UXTW));",
    "remove redundant B_TO_REG zero-base materialization",
)

text = replace_once(
    text,
    "\t\tuint32 currentInstructionAddress = imlInstruction->op_macro.param;\n\t\tmov(TEMP_GPR1.XReg, (uint64)offsetof(PPCRecompilerInstanceData_t, ppcRecompilerDirectJumpTable)); // newIP = 0 special value for recompiler exit\n\t\tldr(TEMP_GPR1.XReg, AdrReg(PPC_REC_INSTANCE_REG, TEMP_GPR1.XReg));\n\t\tmov(LR.WReg, currentInstructionAddress);",
    "\t\tuint32 currentInstructionAddress = imlInstruction->op_macro.param;\n\t\t// newIP = 0 is the first direct-jump-table entry; load it directly from the table base.\n\t\tldr(TEMP_GPR1.XReg, AdrNoOfs(PPC_REC_INSTANCE_REG));\n\t\tmov(LR.WReg, currentInstructionAddress);",
    "remove redundant LEAVE zero-base materialization",
)

path.write_text(text, encoding="utf-8")
print("Applied ARM64 direct jump-table zero-offset experiment")
