from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


path = Path("src/Cafe/HW/Latte/Core/LatteCommandProcessor.cpp")
text = path.read_text(encoding="utf-8")

state_anchor = '''bool conditionalRenderActive = false;

LatteCMDPtr LatteCP_itSetPredication(LatteCMDPtr cmd, uint32 nWords)
{
'''
state_block = '''bool conditionalRenderActive = false;

// XCX-only observation trace for raw PM4 IT_SET_PREDICATION packets.
// This trace does not change predication state, query memory, draw execution,
// query results, or the historical XCX 0x100000 workaround.
static uint64 s_xcxPredicationPacketCount = 0;
static uint64 s_xcxPredicationEnableCount = 0;
static uint64 s_xcxPredicationDisableCount = 0;

static bool XCXPredicationTraceEnabled(uint64 titleId)
{
\treturn titleId == 0x00050000101C4C00ULL || // XCX EU
\t\ttitleId == 0x00050000101C4D00ULL || // XCX US
\t\ttitleId == 0x0005000010116100ULL;   // XCX JP
}

static bool XCXPredicationTraceSample(uint64 n)
{
\treturn n <= 128 || (n % 1000ULL) == 0;
}

LatteCMDPtr LatteCP_itSetPredication(LatteCMDPtr cmd, uint32 nWords, const char* source)
{
'''
text = replace_once(text, state_anchor, state_block, "predication trace state/signature")

decode_anchor = '''\tuint32 queryTypeFlag = (flags >> 13) & 7;
\tuint32 pixelsMustPassFlag = (flags >> 31) & 1;
\tuint32 dontWaitFlag = (flags >> 1) & 19;

\tif (queryTypeFlag == 0)
'''
decode_block = '''\tuint32 queryTypeFlag = (flags >> 13) & 7;
\tuint32 pixelsMustPassFlag = (flags >> 31) & 1;
\tuint32 dontWaitFlag = (flags >> 1) & 19;

\tconst uint64 traceTitleId = CafeSystem::GetForegroundTitleId();
\tif (XCXPredicationTraceEnabled(traceTitleId))
\t{
\t\tconst uint64 packetN = ++s_xcxPredicationPacketCount;
\t\tconst uint32 dontWaitBit19 = (flags >> 19) & 1;
\t\tif (queryTypeFlag == 0)
\t\t{
\t\t\tconst uint64 disableN = ++s_xcxPredicationDisableCount;
\t\t\tif (XCXPredicationTraceSample(disableN))
\t\t\t{
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[XCX_PREDICATION] DISABLE n={} packets={} title={:016x} source={} phys={:08x} flags={:08x} queryType={} pixelsMustPass={} dontWaitBit19={} legacyDontWaitDecoded={}",
\t\t\t\t\tdisableN, packetN, traceTitleId, source, physQueryInfo, flags, queryTypeFlag,
\t\t\t\t\tpixelsMustPassFlag, dontWaitBit19, dontWaitFlag);
\t\t\t}
\t\t}
\t\telse
\t\t{
\t\t\tconst uint64 enableN = ++s_xcxPredicationEnableCount;
\t\t\tif (XCXPredicationTraceSample(enableN))
\t\t\t{
\t\t\t\tMPTR virtualQueryInfo = MPTR_NULL;
\t\t\t\tuint64 rawStart = 0;
\t\t\t\tuint64 rawEnd = 0;
\t\t\t\tuint64 resultValue = 0;
\t\t\t\tbool highBitPending = false;
\t\t\t\tif (physQueryInfo != MPTR_NULL)
\t\t\t\t{
\t\t\t\t\tvirtualQueryInfo = memory_physicalToVirtual(physQueryInfo);
\t\t\t\t\tuint32* queryMem = (uint32*)memory_getPointerFromPhysicalOffset(physQueryInfo);
\t\t\t\t\trawStart = *(uint64*)(queryMem + 0);
\t\t\t\t\trawEnd = *(uint64*)(queryMem + 2);
\t\t\t\t\thighBitPending = ((rawStart & 0x8000000000000000ULL) != 0) ||
\t\t\t\t\t\t((rawEnd & 0x8000000000000000ULL) != 0);
\t\t\t\t\tif (!highBitPending)
\t\t\t\t\t\tresultValue = rawEnd - rawStart;
\t\t\t\t}
\t\t\t\tconst bool seeded100000 = (rawStart == 0 && rawEnd == 0x100000ULL);
\t\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t\t"[XCX_PREDICATION] ENABLE n={} packets={} title={:016x} source={} phys={:08x} virt={:08x} flags={:08x} queryType={} pixelsMustPass={} dontWaitBit19={} legacyDontWaitDecoded={} rawStart={:016x} rawEnd={:016x} result={} highBitPending={} seeded100000={}",
\t\t\t\t\tenableN, packetN, traceTitleId, source, physQueryInfo, virtualQueryInfo, flags,
\t\t\t\t\tqueryTypeFlag, pixelsMustPassFlag, dontWaitBit19, dontWaitFlag,
\t\t\t\t\trawStart, rawEnd, resultValue, highBitPending, seeded100000);
\t\t\t}
\t\t}
\t}

\tif (queryTypeFlag == 0)
'''
text = replace_once(text, decode_anchor, decode_block, "predication observation body")

text = replace_once(
    text,
    "\t\t\t\t\tLatteCP_itSetPredication(cmdData, nWords);\n",
    "\t\t\t\t\tLatteCP_itSetPredication(cmdData, nWords, \"indirect\");\n",
    "indirect predication callsite",
)
text = replace_once(
    text,
    "\t\t\t\tLatteCP_itSetPredication(cmd, nWords);\n",
    "\t\t\t\tLatteCP_itSetPredication(cmd, nWords, \"toplevel\");\n",
    "top-level predication callsite",
)

path.write_text(text, encoding="utf-8", newline="\n")

patched = path.read_text(encoding="utf-8")

for marker in (
    "[XCX_PREDICATION] ENABLE",
    "[XCX_PREDICATION] DISABLE",
    'source={} phys={:08x} virt={:08x}',
    'LatteCP_itSetPredication(cmdData, nWords, "indirect");',
    'LatteCP_itSetPredication(cmd, nWords, "toplevel");',
):
    if marker not in patched:
        raise RuntimeError(f"missing marker/postcondition: {marker}")

for title_id in (
    "0x00050000101C4C00ULL",
    "0x00050000101C4D00ULL",
    "0x0005000010116100ULL",
):
    if title_id not in patched:
        raise RuntimeError(f"missing XCX title gate: {title_id}")

# Preserve current behavior verbatim. The experiment only observes it.
for token in (
    "conditionalRenderActive = false;",
    "conditionalRenderActive = true;",
    "uint32 dontWaitFlag = (flags >> 1) & 19;",
):
    if token not in patched:
        raise RuntimeError(f"baseline predication behavior missing: {token}")

print("XCX IT_SET_PREDICATION observation trace installed; behavior unchanged")
