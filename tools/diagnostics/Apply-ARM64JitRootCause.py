from pathlib import Path


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


def ensure_include(text, anchor, include_line, label):
    if include_line in text:
        return text
    if anchor not in text:
        raise RuntimeError(f"{label}: include anchor not found")
    return text.replace(anchor, anchor + include_line, 1)


# Stage 1/2: targeted IML -> RA diagnostics for guest 0x0420CB80.
p = Path("src/Cafe/HW/Espresso/Recompiler/IML/IMLRegisterAllocator.cpp")
t = p.read_text(encoding="utf-8")
t = ensure_include(
    t,
    '#include "Common/cpu_features.h"\n',
    '#include "diagnostics/RuntimeExperiments.h"\n',
    "ARM64 JIT root-cause RA include",
)

macro_anchor = '#define DEBUG_RA_INSTRUCTION_GEN 0\n'
helper_block = '''#define DEBUG_RA_INSTRUCTION_GEN 0

static bool IMLRA_IsJitPerfHotspot(const IMLSegment* imlSegment)
{
\tif (imlSegment->ppcAddress == 0x0420CB80u)
\t\treturn true;
\treturn imlSegment->isEnterable && imlSegment->enterPPCAddress == 0x0420CB80u;
}
'''
t = replace_once(t, macro_anchor, helper_block, "ARM64 JIT root-cause RA target helper")

rewrite_anchor = '''void IMLRA_GenerateSegmentMoveInstructions2(IMLRegisterAllocatorContext& ctx, IMLSegment* imlSegment)
{
\tIMLRA_RewriteRegisters(ctx, imlSegment);

#if DEBUG_RA_INSTRUCTION_GEN
'''
rewrite_block = '''void IMLRA_GenerateSegmentMoveInstructions2(IMLRegisterAllocatorContext& ctx, IMLSegment* imlSegment)
{
\tIMLRA_RewriteRegisters(ctx, imlSegment);

\tconst bool diagJitHotspot = RuntimeExperiments::Enabled("jit-iml-ra-hotspot") && IMLRA_IsJitPerfHotspot(imlSegment);
\tif (diagJitHotspot)
\t{
\t\tcemuLog_log(LogType::Force,
\t\t\t"[JIT_IML_RA_REWRITTEN] ppc=0x{:08x} enter=0x{:08x} seg={} loopDepth={} imlCount={}",
\t\t\timlSegment->ppcAddress, imlSegment->enterPPCAddress, imlSegment->momentaryIndex,
\t\t\timlSegment->loopDepth, imlSegment->imlList.size());
\t\tIMLDebug_DumpSegment(ctx.deprGenContext, imlSegment, false);
\t}

#if DEBUG_RA_INSTRUCTION_GEN
'''
t = replace_once(t, rewrite_anchor, rewrite_block, "ARM64 JIT root-cause rewritten dump")

postmove_anchor = '''\timlSegment->imlList = std::move(rebuiltInstructions);
\tcemu_assert_debug(hadSuffixInstruction == imlSegment->HasSuffixInstruction());

#if DEBUG_RA_INSTRUCTION_GEN
'''
postmove_block = '''\timlSegment->imlList = std::move(rebuiltInstructions);
\tcemu_assert_debug(hadSuffixInstruction == imlSegment->HasSuffixInstruction());

\tif (diagJitHotspot)
\t{
\t\tcemuLog_log(LogType::Force,
\t\t\t"[JIT_IML_RA_POSTMOVE] ppc=0x{:08x} enter=0x{:08x} seg={} imlCount={}",
\t\t\timlSegment->ppcAddress, imlSegment->enterPPCAddress, imlSegment->momentaryIndex,
\t\t\timlSegment->imlList.size());
\t\tIMLDebug_DumpSegment(ctx.deprGenContext, imlSegment, false);
\t}

#if DEBUG_RA_INSTRUCTION_GEN
'''
t = replace_once(t, postmove_anchor, postmove_block, "ARM64 JIT root-cause post-move dump")

allocate_anchor = '''\tDbgVerifyAllRanges(ctx);
\tIMLRA_AnalyzeRangeDataFlow(ppcImlGenContext);
\tIMLRA_GenerateMoveInstructions(ctx);
'''
allocate_block = '''\tDbgVerifyAllRanges(ctx);
\tIMLRA_AnalyzeRangeDataFlow(ppcImlGenContext);

\tif (RuntimeExperiments::Enabled("jit-iml-ra-hotspot"))
\t{
\t\tfor (IMLSegment* segIt : ppcImlGenContext->segmentList2)
\t\t{
\t\t\tif (!IMLRA_IsJitPerfHotspot(segIt))
\t\t\t\tcontinue;
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[JIT_IML_RA_PREMOVE] ppc=0x{:08x} enter=0x{:08x} seg={} loopDepth={} imlCount={}",
\t\t\t\tsegIt->ppcAddress, segIt->enterPPCAddress, segIt->momentaryIndex,
\t\t\t\tsegIt->loopDepth, segIt->imlList.size());
\t\t\tIMLDebug_DumpSegment(ppcImlGenContext, segIt, true);
\t\t}
\t}

\tIMLRA_GenerateMoveInstructions(ctx);
'''
t = replace_once(t, allocate_anchor, allocate_block, "ARM64 JIT root-cause pre-move dump")
p.write_text(t, encoding="utf-8", newline="\n")


# Stage 3: correlate each post-RA IML instruction with emitted AArch64 byte offsets.
p = Path("src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp")
t = p.read_text(encoding="utf-8")
t = ensure_include(
    t,
    '#include "HW/Espresso/PPCState.h"\n',
    '#include "diagnostics/RuntimeExperiments.h"\n',
    "ARM64 JIT root-cause backend include",
)

segment_anchor = '''\t\tsegIt->x64Offset = aarch64GenContext.getSize();

\t\taarch64GenContext.storeSegmentStart(segIt);
'''
segment_block = '''\t\tsegIt->x64Offset = aarch64GenContext.getSize();
\t\tconst bool diagJitHotspot = RuntimeExperiments::Enabled("jit-iml-ra-hotspot") &&
\t\t\t(segIt->ppcAddress == 0x0420CB80u || (segIt->isEnterable && segIt->enterPPCAddress == 0x0420CB80u));
\t\tif (diagJitHotspot)
\t\t{
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[JIT_IML_NATIVE_SEG] ppc=0x{:08x} enter=0x{:08x} seg={} native_base_off=0x{:x} imlCount={}",
\t\t\t\tsegIt->ppcAddress, segIt->enterPPCAddress, segIt->momentaryIndex,
\t\t\t\tsegIt->x64Offset, segIt->imlList.size());
\t\t}

\t\taarch64GenContext.storeSegmentStart(segIt);
'''
t = replace_once(t, segment_anchor, segment_block, "ARM64 JIT root-cause native segment start")

instruction_anchor = '''\t\t\tIMLInstruction* imlInstruction = segIt->imlList.data() + i;
\t\t\tif (imlInstruction->type == PPCREC_IML_TYPE_R_NAME)
'''
instruction_block = '''\t\t\tIMLInstruction* imlInstruction = segIt->imlList.data() + i;
\t\t\tconst uint32 diagNativeBefore = diagJitHotspot
\t\t\t\t? static_cast<uint32>(aarch64GenContext.getSize() - segIt->x64Offset)
\t\t\t\t: 0;
\t\t\tif (imlInstruction->type == PPCREC_IML_TYPE_R_NAME)
'''
t = replace_once(t, instruction_anchor, instruction_block, "ARM64 JIT root-cause instruction offset start")

tail_anchor = '''\t\t\telse
\t\t\t{
\t\t\t\tcodeGenerationFailed = true;
\t\t\t\tcemu_assert_suspicious();
\t\t\t\tcemuLog_log(LogType::Recompiler, "PPCRecompiler_generateAArch64Code(): Unsupported iml type {}", imlInstruction->type);
\t\t\t}
\t\t}
\t}
'''
tail_block = '''\t\t\telse
\t\t\t{
\t\t\t\tcodeGenerationFailed = true;
\t\t\t\tcemu_assert_suspicious();
\t\t\t\tcemuLog_log(LogType::Recompiler, "PPCRecompiler_generateAArch64Code(): Unsupported iml type {}", imlInstruction->type);
\t\t\t}

\t\t\tif (diagJitHotspot)
\t\t\t{
\t\t\t\tconst uint32 diagNativeAfter = static_cast<uint32>(aarch64GenContext.getSize() - segIt->x64Offset);
\t\t\t\tstd::string diagIml;
\t\t\t\tIMLDebug_DisassembleInstruction(*imlInstruction, diagIml);
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[JIT_IML_NATIVE] ppc=0x{:08x} iml={} native=0x{:03x}->0x{:03x} bytes={} {}",
\t\t\t\t\tsegIt->ppcAddress, i, diagNativeBefore, diagNativeAfter,
\t\t\t\t\tdiagNativeAfter - diagNativeBefore, diagIml);
\t\t\t}
\t\t}
\t}
'''
t = replace_once(t, tail_anchor, tail_block, "ARM64 JIT root-cause native instruction correlation")
p.write_text(t, encoding="utf-8", newline="\n")


# P0 companion: follow an initial AArch64 B imm26 for guest 0x02A281A0 and
# dump the actual branch target body. This extends the existing report-only
# jit-hotspot-native mapper installed by Apply-DiagnosticPerformanceBase.py.
p = Path("src/gui/wxgui/windows/PPCThreadsViewer/DebugPPCThreadsWindow.cpp")
t = p.read_text(encoding="utf-8")

branch_anchor = '''\t\t\t\tfor (uint32 nativeOffset = 0; nativeOffset < 128; nativeOffset += 16)
\t\t\t\t{
\t\t\t\t\tconst uint32 wordIndex = nativeOffset / 4;
\t\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t\t"[JIT_HOTSPOT_CODE] guest=0x{:08x} native_off=0x{:03x} {:08x} {:08x} {:08x} {:08x}",
\t\t\t\t\t\tsample.first, nativeOffset,
\t\t\t\t\t\tnativeWords[wordIndex + 0], nativeWords[wordIndex + 1],
\t\t\t\t\t\tnativeWords[wordIndex + 2], nativeWords[wordIndex + 3]);
\t\t\t\t}
'''
branch_block = branch_anchor + '''
\t\t\t\tif (sample.first == 0x02A281A0 && (nativeWords[0] & 0xFC000000u) == 0x14000000u)
\t\t\t\t{
\t\t\t\t\tconst sint32 branchImm26 = static_cast<sint32>(nativeWords[0] << 6) >> 6;
\t\t\t\t\tconst sint64 branchOffset = static_cast<sint64>(branchImm26) * 4;
\t\t\t\t\tconst uint8* branchTarget = reinterpret_cast<const uint8*>(nativeEntry) + branchOffset;
\t\t\t\t\tconst uint32* branchWords = reinterpret_cast<const uint32*>(branchTarget);
\t\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t\t"[JIT_HOTSPOT_BRANCH] guest=0x{:08x} imm26={} byte_off={} target=0x{:016x}",
\t\t\t\t\t\tsample.first, branchImm26, branchOffset, (uint64)(uintptr_t)branchTarget);
\t\t\t\t\tfor (uint32 nativeOffset = 0; nativeOffset < 128; nativeOffset += 16)
\t\t\t\t\t{
\t\t\t\t\t\tconst uint32 wordIndex = nativeOffset / 4;
\t\t\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t\t\t"[JIT_HOTSPOT_TARGET] guest=0x{:08x} target_off=0x{:03x} {:08x} {:08x} {:08x} {:08x}",
\t\t\t\t\t\t\tsample.first, nativeOffset,
\t\t\t\t\t\t\tbranchWords[wordIndex + 0], branchWords[wordIndex + 1],
\t\t\t\t\t\t\tbranchWords[wordIndex + 2], branchWords[wordIndex + 3]);
\t\t\t\t\t}
\t\t\t\t}
'''
t = replace_once(t, branch_anchor, branch_block, "ARM64 JIT hotspot branch target follow")
p.write_text(t, encoding="utf-8", newline="\n")

print("[arm64-jit-root-cause] installed")
