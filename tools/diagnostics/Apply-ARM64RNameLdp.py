from pathlib import Path


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


p = Path("src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp")
t = p.read_text(encoding="utf-8")

func_signature = 'bool PPCRecompiler_generateAArch64Code(struct PPCRecFunction_t* PPCRecFunction, struct ppcImlGenContext_t* ppcImlGenContext)\n'
helper_block = r'''static bool PPCRecompilerAArch64Gen_GetPairableRNameGpr(const IMLInstruction* ins, uint32& guestGpr)
{
\tif (ins->type != PPCREC_IML_TYPE_R_NAME)
\t\treturn false;
\tif (ins->op_r_name.regR.GetBaseFormat() != IMLRegFormat::I64)
\t\treturn false;
\tconst uint32 name = ins->op_r_name.name;
\tif (name < PPCREC_NAME_R0 || name >= PPCREC_NAME_R0 + 32)
\t\treturn false;
\tguestGpr = name - PPCREC_NAME_R0;
\treturn true;
}

static void PPCRecompilerAArch64Gen_BuildRNameLdpPartners(IMLSegment* seg, std::vector<sint32>& partners)
{
\tsize_t runBegin = 0;
\twhile (runBegin < seg->imlList.size())
\t{
\t\tif (seg->imlList[runBegin].type != PPCREC_IML_TYPE_R_NAME)
\t\t{
\t\t\trunBegin++;
\t\t\tcontinue;
\t\t}

\t\tsize_t runEnd = runBegin + 1;
\t\twhile (runEnd < seg->imlList.size() && seg->imlList[runEnd].type == PPCREC_IML_TYPE_R_NAME)
\t\t\trunEnd++;

\t\tsint32 byGuestGpr[32];
\t\tfor (sint32& entry : byGuestGpr)
\t\t\tentry = -1;

\t\tfor (size_t i = runBegin; i < runEnd; ++i)
\t\t{
\t\t\tuint32 guestGpr = 0;
\t\t\tif (!PPCRecompilerAArch64Gen_GetPairableRNameGpr(&seg->imlList[i], guestGpr))
\t\t\t\tcontinue;
\t\t\tif (byGuestGpr[guestGpr] == -1)
\t\t\t\tbyGuestGpr[guestGpr] = static_cast<sint32>(i);
\t\t\telse
\t\t\t\tbyGuestGpr[guestGpr] = -2;
\t\t}

\t\tfor (uint32 guestGpr = 0; guestGpr + 1 < 32;)
\t\t{
\t\t\tconst sint32 lowIndex = byGuestGpr[guestGpr];
\t\t\tconst sint32 highIndex = byGuestGpr[guestGpr + 1];
\t\t\tif (lowIndex >= 0 && highIndex >= 0)
\t\t\t{
\t\t\t\tconst IMLInstruction& lowIns = seg->imlList[lowIndex];
\t\t\t\tconst IMLInstruction& highIns = seg->imlList[highIndex];
\t\t\t\tif (lowIns.op_r_name.regR.GetRegID() != highIns.op_r_name.regR.GetRegID())
\t\t\t\t{
\t\t\t\t\tpartners[lowIndex] = highIndex;
\t\t\t\t\tpartners[highIndex] = lowIndex;
\t\t\t\t\tguestGpr += 2;
\t\t\t\t\tcontinue;
\t\t\t\t}
\t\t\t}
\t\t\tguestGpr++;
\t\t}

\t\trunBegin = runEnd;
\t}
}

static void PPCRecompilerAArch64Gen_EmitRNameLdp(AArch64GenContext_t& ctx, IMLInstruction* a, IMLInstruction* b)
{
\tuint32 guestA = 0;
\tuint32 guestB = 0;
\tconst bool validA = PPCRecompilerAArch64Gen_GetPairableRNameGpr(a, guestA);
\tconst bool validB = PPCRecompilerAArch64Gen_GetPairableRNameGpr(b, guestB);
\tcemu_assert_debug(validA && validB);
\tcemu_assert_debug(guestA + 1 == guestB || guestB + 1 == guestA);

\tIMLInstruction* lowIns = guestA < guestB ? a : b;
\tIMLInstruction* highIns = guestA < guestB ? b : a;
\tconst uint32 lowGuest = std::min(guestA, guestB);

\tWReg lowReg = aliasAs<WReg>(gpReg<XReg>(lowIns->op_r_name.regR));
\tWReg highReg = aliasAs<WReg>(gpReg<XReg>(highIns->op_r_name.regR));
\tconst sint32 stateOffset = static_cast<sint32>(offsetof(PPCInterpreter_t, gpr) + sizeof(uint32) * lowGuest);
\tctx.ldp(lowReg, highReg, AdrImm(HCPU_REG, stateOffset));
}

'''
t = replace_once(t, func_signature, helper_block + func_signature, "ARM64 R_NAME LDP helpers")

context_anchor = '\tconst bool expCompareReuse = RuntimeExperiments::Enabled("arm64-compare-reuse");\n'
context_block = context_anchor + '\tconst bool expRNameLdp = RuntimeExperiments::Enabled("arm64-rname-ldp");\n'
t = replace_once(t, context_anchor, context_block, "ARM64 R_NAME LDP runtime gate")

segment_anchor = '''\t\taarch64GenContext.storeSegmentStart(segIt);

\t\tfor (size_t i = 0; i < segIt->imlList.size(); i++)
'''
segment_block = '''\t\taarch64GenContext.storeSegmentStart(segIt);

\t\tstd::vector<sint32> rnameLdpPartners;
\t\tif (expRNameLdp)
\t\t{
\t\t\trnameLdpPartners.assign(segIt->imlList.size(), -1);
\t\t\tPPCRecompilerAArch64Gen_BuildRNameLdpPartners(segIt, rnameLdpPartners);
\t\t\tif (diagJitHotspot)
\t\t\t{
\t\t\t\tuint32 pairCount = 0;
\t\t\t\tfor (size_t pairIndex = 0; pairIndex < rnameLdpPartners.size(); ++pairIndex)
\t\t\t\t{
\t\t\t\t\tif (rnameLdpPartners[pairIndex] > static_cast<sint32>(pairIndex))
\t\t\t\t\t\tpairCount++;
\t\t\t\t}
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[ARM64_RNAME_LDP] ppc=0x{:08x} enter=0x{:08x} pairs={} native_bytes_saved={}",
\t\t\t\t\tsegIt->ppcAddress, segIt->enterPPCAddress, pairCount, pairCount * 4);
\t\t\t}
\t\t}

\t\tfor (size_t i = 0; i < segIt->imlList.size(); i++)
'''
t = replace_once(t, segment_anchor, segment_block, "ARM64 R_NAME LDP segment pairing")

dispatch_anchor = '''\t\t\tif (imlInstruction->type == PPCREC_IML_TYPE_R_NAME)
\t\t\t{
\t\t\t\taarch64GenContext.r_name(imlInstruction);
\t\t\t}
'''
dispatch_block = '''\t\t\tconst sint32 rnameLdpPartner = expRNameLdp && !rnameLdpPartners.empty() ? rnameLdpPartners[i] : -1;
\t\t\tif (rnameLdpPartner >= 0)
\t\t\t{
\t\t\t\tif (rnameLdpPartner > static_cast<sint32>(i))
\t\t\t\t\tPPCRecompilerAArch64Gen_EmitRNameLdp(aarch64GenContext, imlInstruction, segIt->imlList.data() + rnameLdpPartner);
\t\t\t}
\t\t\telse if (imlInstruction->type == PPCREC_IML_TYPE_R_NAME)
\t\t\t{
\t\t\t\taarch64GenContext.r_name(imlInstruction);
\t\t\t}
'''
t = replace_once(t, dispatch_anchor, dispatch_block, "ARM64 R_NAME LDP dispatch")

p.write_text(t, encoding="utf-8", newline="\n")
print("[arm64-rname-ldp] installed")
