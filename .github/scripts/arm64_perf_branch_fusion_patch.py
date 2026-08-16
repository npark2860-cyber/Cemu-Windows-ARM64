from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


optimizer_path = Path("src/Cafe/HW/Espresso/Recompiler/IML/IMLOptimizer.cpp")
backend_path = Path("src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp")

optimizer = optimizer_path.read_text(encoding="utf-8")
optimizer = replace_once(
    optimizer,
    "#ifdef ARCH_X86_64\n\t// x86 specific optimizations\n\tIMLOptimizerX86_SubstituteCJumpForEflagsJump(regIoAnalysis, seg); // this pass should be applied late since it creates invisible eflags dependencies (which would break further register dependency analysis)\n#endif",
    "#if defined(ARCH_X86_64) || defined(__aarch64__)\n\t// x86 EFLAGS and AArch64 NZCV can both carry compare results directly into a conditional branch.\n\tIMLOptimizerX86_SubstituteCJumpForEflagsJump(regIoAnalysis, seg); // this pass should be applied late since it creates invisible flags dependencies (which would break further register dependency analysis)\n#endif",
    "enable compare/branch fusion on AArch64",
)
optimizer_path.write_text(optimizer, encoding="utf-8")

backend = backend_path.read_text(encoding="utf-8")

backend = replace_once(
    backend,
    "struct NegativeRegValueJumpInfo\n{\n\tIMLSegment* target;\n\tWReg regValue;\n};\n\nusing JumpInfo = std::variant<\n\tUnconditionalJumpInfo,\n\tConditionalRegJumpInfo,\n\tNegativeRegValueJumpInfo>;",
    "struct NegativeRegValueJumpInfo\n{\n\tIMLSegment* target;\n\tWReg regValue;\n};\n\nstruct ConditionalFlagsJumpInfo\n{\n\tIMLSegment* target;\n\tCond cond;\n};\n\nusing JumpInfo = std::variant<\n\tUnconditionalJumpInfo,\n\tConditionalRegJumpInfo,\n\tNegativeRegValueJumpInfo,\n\tConditionalFlagsJumpInfo>;",
    "add flags jump info",
)

backend = replace_once(
    backend,
    "\tvoid cjump(IMLInstruction* imlInstruction, IMLSegment* imlSegment);\n\tvoid jump(IMLSegment* imlSegment);",
    "\tvoid cjump(IMLInstruction* imlInstruction, IMLSegment* imlSegment);\n\tvoid flagsJump(IMLInstruction* imlInstruction, IMLSegment* imlSegment);\n\tvoid jump(IMLSegment* imlSegment);",
    "declare flagsJump",
)

conditional_handler = """\tbool handleJump(sint64 addressOffset, const ConditionalRegJumpInfo& jump)\n\t{\n\t\tbool mustBeTrue = jump.mustBeTrue;\n\n\t\t// in +/-32KB\n\t\tif (-0x8000 <= addressOffset && addressOffset <= 0x7fff)\n\t\t{\n\t\t\tif (mustBeTrue)\n\t\t\t\ttbnz(jump.regBool, 0, addressOffset);\n\t\t\telse\n\t\t\t\ttbz(jump.regBool, 0, addressOffset);\n\t\t\treturn true;\n\t\t}\n\n\t\t// in +/-1MB\n\t\tif (-0x100000 <= addressOffset && addressOffset <= 0xfffff)\n\t\t{\n\t\t\tif (mustBeTrue)\n\t\t\t\tcbnz(jump.regBool, addressOffset);\n\t\t\telse\n\t\t\t\tcbz(jump.regBool, addressOffset);\n\t\t\treturn true;\n\t\t}\n\n\t\tLabel skipJump;\n\t\tif (mustBeTrue)\n\t\t\ttbz(jump.regBool, 0, skipJump);\n\t\telse\n\t\t\ttbnz(jump.regBool, 0, skipJump);\n\t\taddressOffset -= 4;\n\n\t\t// in +/-128MB\n\t\tif (-0x8000000 <= addressOffset && addressOffset <= 0x7ffffff)\n\t\t{\n\t\t\tb(addressOffset);\n\t\t\tL(skipJump);\n\t\t\treturn true;\n\t\t}\n\n\t\tcemu_assert_suspicious();\n\n\t\treturn false;\n\t}\n"""
flags_handler = conditional_handler + """\n\tbool handleJump(sint64 addressOffset, const ConditionalFlagsJumpInfo& jump)\n\t{\n\t\t// AArch64 B.cond reaches +/-1MB.\n\t\tif (-0x100000 <= addressOffset && addressOffset <= 0xfffff)\n\t\t{\n\t\t\tb(jump.cond, addressOffset);\n\t\t\treturn true;\n\t\t}\n\n\t\t// Preserve the existing two-instruction jump reservation for unusually distant targets.\n\t\tLabel skipJump;\n\t\tconst Cond inverseCond = static_cast<Cond>(static_cast<uint32>(jump.cond) ^ 1u);\n\t\tb(inverseCond, skipJump);\n\t\taddressOffset -= 4;\n\n\t\tif (-0x8000000 <= addressOffset && addressOffset <= 0x7ffffff)\n\t\t{\n\t\t\tb(addressOffset);\n\t\t\tL(skipJump);\n\t\t\treturn true;\n\t\t}\n\n\t\tcemu_assert_suspicious();\n\t\treturn false;\n\t}\n"""
backend = replace_once(backend, conditional_handler, flags_handler, "add flags jump handler")

backend = replace_once(
    backend,
    "\telse if (imlInstruction->operation == PPCREC_IML_OP_CNTLZW)\n\t{\n\t\tclz(regR, regA);\n\t}\n\telse",
    "\telse if (imlInstruction->operation == PPCREC_IML_OP_CNTLZW)\n\t{\n\t\tclz(regR, regA);\n\t}\n\telse if (imlInstruction->operation == PPCREC_IML_OP_X86_CMP)\n\t{\n\t\tcmp(regR, regA);\n\t}\n\telse",
    "emit register compare without cset",
)

backend = replace_once(
    backend,
    "\telse if (imlInstruction->operation == PPCREC_IML_OP_LEFT_ROTATE)\n\t{\n\t\tror(reg, reg, 32 - (imm32 & 0x1f));\n\t}\n\telse",
    "\telse if (imlInstruction->operation == PPCREC_IML_OP_LEFT_ROTATE)\n\t{\n\t\tror(reg, reg, 32 - (imm32 & 0x1f));\n\t}\n\telse if (imlInstruction->operation == PPCREC_IML_OP_X86_CMP)\n\t{\n\t\tcmp_imm(reg, imm32, TEMP_GPR1.WReg);\n\t}\n\telse",
    "emit immediate compare without cset",
)

backend = replace_once(
    backend,
    "void AArch64GenContext_t::cjump(IMLInstruction* imlInstruction, IMLSegment* imlSegment)\n{\n\tauto regBool = gpReg<WReg>(imlInstruction->op_conditional_jump.registerBool);\n\tprepareJump(ConditionalRegJumpInfo{\n\t\t.target = imlSegment->nextSegmentBranchTaken,\n\t\t.regBool = regBool,\n\t\t.mustBeTrue = imlInstruction->op_conditional_jump.mustBeTrue,\n\t});\n}\n\nvoid AArch64GenContext_t::jump(IMLSegment* imlSegment)",
    "void AArch64GenContext_t::cjump(IMLInstruction* imlInstruction, IMLSegment* imlSegment)\n{\n\tauto regBool = gpReg<WReg>(imlInstruction->op_conditional_jump.registerBool);\n\tprepareJump(ConditionalRegJumpInfo{\n\t\t.target = imlSegment->nextSegmentBranchTaken,\n\t\t.regBool = regBool,\n\t\t.mustBeTrue = imlInstruction->op_conditional_jump.mustBeTrue,\n\t});\n}\n\nvoid AArch64GenContext_t::flagsJump(IMLInstruction* imlInstruction, IMLSegment* imlSegment)\n{\n\tCond cond = ImlCondToArm64Cond(imlInstruction->op_x86_eflags_jcc.cond);\n\tif (imlInstruction->op_x86_eflags_jcc.invertedCondition)\n\t\tcond = static_cast<Cond>(static_cast<uint32>(cond) ^ 1u);\n\tprepareJump(ConditionalFlagsJumpInfo{\n\t\t.target = imlSegment->nextSegmentBranchTaken,\n\t\t.cond = cond,\n\t});\n}\n\nvoid AArch64GenContext_t::jump(IMLSegment* imlSegment)",
    "define flagsJump",
)

backend = replace_once(
    backend,
    "\t\t\telse if (imlInstruction->type == PPCREC_IML_TYPE_CONDITIONAL_JUMP)\n\t\t\t{\n\t\t\t\taarch64GenContext.cjump(imlInstruction, segIt);\n\t\t\t}\n\t\t\telse if (imlInstruction->type == PPCREC_IML_TYPE_JUMP)",
    "\t\t\telse if (imlInstruction->type == PPCREC_IML_TYPE_CONDITIONAL_JUMP)\n\t\t\t{\n\t\t\t\taarch64GenContext.cjump(imlInstruction, segIt);\n\t\t\t}\n\t\t\telse if (imlInstruction->type == PPCREC_IML_TYPE_X86_EFLAGS_JCC)\n\t\t\t{\n\t\t\t\taarch64GenContext.flagsJump(imlInstruction, segIt);\n\t\t\t}\n\t\t\telse if (imlInstruction->type == PPCREC_IML_TYPE_JUMP)",
    "generate flags jump",
)

backend_path.write_text(backend, encoding="utf-8")

print("Applied ARM64 compare/conditional-branch fusion experiment")
