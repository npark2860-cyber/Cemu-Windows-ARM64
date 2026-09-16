from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACER_HEADER = ROOT / "src/Cafe/OS/common/BotWSoundSourceTracer.h"
CORE_FS = ROOT / "src/Cafe/OS/libs/coreinit/coreinit_FS.cpp"
AX_VOICE = ROOT / "src/Cafe/OS/libs/snd_core/ax_voice.cpp"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def patch_tracer_header() -> None:
    text = TRACER_HEADER.read_text(encoding="utf-8-sig")

    include_anchor = '#include "Cafe/HW/MMU/MMU.h"\n'
    if 'BotWSoundFingerprintCatalog.h' not in text:
        text = replace_once(
            text,
            include_anchor,
            include_anchor + '#include "Cafe/OS/common/BotWSoundFingerprintCatalog.h"\n',
            "tracer fingerprint include",
        )
    if 'BotWSoundSourceTracerV3Support.h' not in text:
        fingerprint_include = '#include "Cafe/OS/common/BotWSoundFingerprintCatalog.h"\n'
        text = replace_once(
            text,
            fingerprint_include,
            fingerprint_include + '#include "Cafe/OS/common/BotWSoundSourceTracerV3Support.h"\n',
            "tracer v3 support include",
        )

    register_anchor = (
        '\tinline void TraceVoice(std::string_view eventName, uint32 voiceIndex, uint32 sampleBase,\n'
    )
    if 'RegisterReadCompleted' not in text:
        register_impl = (
            '\tinline void RegisterReadCompleted(uint32 fileHandle, uint32 destination, uint32 size)\n'
            '\t{\n'
            '\t\tif (destination == 0 || size == 0)\n'
            '\t\t\treturn;\n'
            '\t\tstd::string path;\n'
            '\t\t{\n'
            '\t\t\tstd::scoped_lock lock(s_mutex);\n'
            '\t\t\tauto it = s_openSoundFiles.find(fileHandle);\n'
            '\t\t\tif (it == s_openSoundFiles.end())\n'
            '\t\t\t\treturn;\n'
            '\t\t\tpath = it->second;\n'
            '\t\t}\n'
            '\t\tif (ToLower(path).ends_with(".bars"))\n'
            '\t\t\tBotWSoundSourceTracerV3Support::RegisterBarsReadCompleted(path, destination, size);\n'
            '\t}\n\n'
        )
        text = replace_once(text, register_anchor, register_impl + register_anchor, "tracer completed read hook")

    source_anchor = '\t\tconst auto source = FindSourceLocked(sampleBase);\n'
    if 'FindMatchForPath(sampleBase' not in text:
        source_replacement = (
            '\t\tauto source = FindSourceLocked(sampleBase);\n'
            '\t\t// v3: a direct FS range can identify the BARS file while the old nearest-track\n'
            '\t\t// heuristic still fails to recover the cue. Use the already catalogued BFWAV\n'
            '\t\t// sample fingerprint with the known BARS path as a disambiguation hint.\n'
            '\t\tif (source && source->trackName.empty())\n'
            '\t\t{\n'
            '\t\t\tconst auto fingerprintSource = BotWSoundSourceTracerV3Support::FindMatchForPath(sampleBase, source->path);\n'
            '\t\t\tif (fingerprintSource)\n'
            '\t\t\t{\n'
            '\t\t\t\tsource->start = fingerprintSource->sourceStart;\n'
            '\t\t\t\tsource->size = fingerprintSource->sourceSize;\n'
            '\t\t\t\tsource->offset = fingerprintSource->dataOffset;\n'
            '\t\t\t\tsource->path = fingerprintSource->path;\n'
            '\t\t\t\tsource->trackName = fingerprintSource->trackName;\n'
            '\t\t\t}\n'
            '\t\t}\n'
            '\t\tif (!source)\n'
            '\t\t{\n'
            '\t\t\tconst auto fingerprintSource = BotWSoundFingerprintCatalog::FindMatch(sampleBase);\n'
            '\t\t\tif (fingerprintSource)\n'
            '\t\t\t{\n'
            '\t\t\t\tSourceMatch match;\n'
            '\t\t\t\tmatch.start = fingerprintSource->sourceStart;\n'
            '\t\t\t\tmatch.size = fingerprintSource->sourceSize;\n'
            '\t\t\t\tmatch.offset = fingerprintSource->dataOffset;\n'
            '\t\t\t\tmatch.path = fingerprintSource->path;\n'
            '\t\t\t\tmatch.trackName = fingerprintSource->trackName;\n'
            '\t\t\t\tsource = std::move(match);\n'
            '\t\t\t}\n'
            '\t\t}\n'
        )
        text = replace_once(text, source_anchor, source_replacement, "tracer v3 fingerprint fallback")

    TRACER_HEADER.write_text(text, encoding="utf-8")


def patch_core_fs() -> None:
    text = CORE_FS.read_text(encoding="utf-8-sig")

    include_anchor = '#include "Cafe/OS/libs/coreinit/coreinit_FS.h"\n'
    if 'BotWSoundSourceTracer.h' not in text:
        text = replace_once(
            text,
            include_anchor,
            include_anchor + '#include "Cafe/OS/common/BotWSoundSourceTracer.h"\n',
            "coreinit tracer include",
        )

    open_anchor = (
        '\t\t\t*fsCmdBlockBody->returnValues.cmdOpenFile.handlePtr = '
        'fsCmdBlockBody->fsaShimBuffer.response.cmdOpenFile.fileHandleOutput;\n'
        '\t\t\tbreak;'
    )
    if 'RegisterFileOpen' not in text:
        open_replacement = (
            '\t\t\t*fsCmdBlockBody->returnValues.cmdOpenFile.handlePtr = '
            'fsCmdBlockBody->fsaShimBuffer.response.cmdOpenFile.fileHandleOutput;\n'
            '\t\t\tconst uint32 tracedHandle = (uint32)fsCmdBlockBody->fsaShimBuffer.response.cmdOpenFile.fileHandleOutput;\n'
            '\t\t\tBotWSoundSourceTracer::RegisterFileOpen(tracedHandle, '
            'reinterpret_cast<const char*>(fsCmdBlockBody->fsaShimBuffer.request.cmdOpenFile.path));\n'
            '\t\t\tbreak;'
        )
        text = replace_once(text, open_anchor, open_replacement, "FS open hook")

    read_anchor = (
        '\t\tif (usePos)\n'
        '\t\t\tflag |= FSA_CMD_FLAG_SET_POS;\n'
        '\t\telse\n'
        '\t\t\tflag &= ~FSA_CMD_FLAG_SET_POS;'
    )
    if 'RegisterRead(fileHandle' not in text:
        read_replacement = (
            '\t\tBotWSoundSourceTracer::RegisterRead(fileHandle, memory_getVirtualOffsetFromPointer(dest), '
            'static_cast<uint32>(transferSizeS64));\n\n' + read_anchor
        )
        text = replace_once(text, read_anchor, read_replacement, "FS read hook")

    finish_read_anchor = (
        '\t\tcase FSA_CMD_OPERATION_TYPE::READ:\n'
        '\t\tcase FSA_CMD_OPERATION_TYPE::WRITE:'
    )
    if 'RegisterReadCompleted' not in text:
        finish_read_replacement = (
            '\t\tcase FSA_CMD_OPERATION_TYPE::READ:\n'
            '\t\t{\n'
            '\t\t\tif (static_cast<sint32>(result) >= 0)\n'
            '\t\t\t{\n'
            '\t\t\t\tconst auto& traceRead = fsCmdBlockBody->fsaShimBuffer.request.cmdReadFile;\n'
            '\t\t\t\tconst uint64 traceSize64 = static_cast<uint64>((uint32)traceRead.size) * static_cast<uint64>((uint32)traceRead.count);\n'
            '\t\t\t\tif (traceSize64 <= 0xFFFFFFFFull)\n'
            '\t\t\t\t\tBotWSoundSourceTracer::RegisterReadCompleted((uint32)traceRead.fileHandle, traceRead.dest.GetMPTR(), static_cast<uint32>(traceSize64));\n'
            '\t\t\t}\n'
            '\t\t\tbreak;\n'
            '\t\t}\n'
            '\t\tcase FSA_CMD_OPERATION_TYPE::WRITE:'
        )
        text = replace_once(text, finish_read_anchor, finish_read_replacement, "FS read completion hook")

    close_anchor = (
        '\tsint32 FSCloseFileAsync(FSClient_t* fsClient, FSCmdBlock_t* fsCmdBlock, uint32 fileHandle, '
        'uint32 errorMask, FSAsyncParams* fsAsyncParams)\n'
        '\t{\n'
        '\t\t_FSCmdIntro();'
    )
    if 'RegisterFileClose(fileHandle)' not in text:
        close_replacement = close_anchor + '\n\t\tBotWSoundSourceTracer::RegisterFileClose(fileHandle);'
        text = replace_once(text, close_anchor, close_replacement, "FS close hook")

    CORE_FS.write_text(text, encoding="utf-8")


def patch_ax_voice() -> None:
    text = AX_VOICE.read_text(encoding="utf-8-sig")

    include_anchor = '#include "Cafe/OS/libs/snd_core/ax_internal.h"\n'
    if 'BotWSoundSourceTracer.h' not in text:
        text = replace_once(
            text,
            include_anchor,
            include_anchor + '#include "Cafe/OS/common/BotWSoundSourceTracer.h"\n',
            "AX tracer include",
        )

    state_anchor = (
        '\t\t\tAXSetSyncFlag(vpb, AX_SYNCFLAG_PLAYBACKSTATE);\n'
        '\t\t\tAXVoiceProtection_Acquire(vpb);\n'
        '\t\t\tif (voiceState == 0)'
    )
    if 'TraceVoice("start"' not in text:
        state_replacement = (
            '\t\t\tAXSetSyncFlag(vpb, AX_SYNCFLAG_PLAYBACKSTATE);\n'
            '\t\t\tAXVoiceProtection_Acquire(vpb);\n'
            '\t\t\tif (voiceState == 1)\n'
            '\t\t\t{\n'
            '\t\t\t\tconst MPTR traceSampleBase = _swapEndianU32(vpb->offsets.samples);\n'
            '\t\t\t\tif (traceSampleBase != MPTR_NULL)\n'
            '\t\t\t\t{\n'
            '\t\t\t\t\tBotWSoundSourceTracer::TraceVoice("start", (uint32)vpb->index, traceSampleBase,\n'
            '\t\t\t\t\t\t_swapEndianU16(vpb->offsets.format), _swapEndianU32(vpb->offsets.currentOffset),\n'
            '\t\t\t\t\t\t_swapEndianU32(vpb->offsets.endOffset), _swapEndianU32(vpb->offsets.loopOffset),\n'
            '\t\t\t\t\t\t_swapEndianU16(internal->deviceMixMaskTV[0]), _swapEndianU16(internal->deviceMixMaskDRC[0]));\n'
            '\t\t\t\t}\n'
            '\t\t\t}\n'
            '\t\t\tif (voiceState == 0)'
        )
        text = replace_once(text, state_anchor, state_replacement, "AX state hook")

    offsets_anchor = (
        '\t\tmemcpy(&vpb->offsets, pbOffset, sizeof(AXPBOFFSET_t));\n'
        '\t\tsampleBase = memory_virtualToPhysical(sampleBase);'
    )
    if 'TraceVoice("offsets"' not in text:
        offsets_replacement = (
            '\t\tAXVPBInternal_t* traceInternal = __AXVPBInternalVoiceArray + (sint32)vpb->index;\n'
            '\t\tBotWSoundSourceTracer::TraceVoice("offsets", (uint32)vpb->index, sampleBase,\n'
            '\t\t\t_swapEndianU16(pbOffset->format), _swapEndianU32(pbOffset->currentOffset),\n'
            '\t\t\t_swapEndianU32(pbOffset->endOffset), _swapEndianU32(pbOffset->loopOffset),\n'
            '\t\t\t_swapEndianU16(traceInternal->deviceMixMaskTV[0]), _swapEndianU16(traceInternal->deviceMixMaskDRC[0]));\n'
            '\t\tmemcpy(&vpb->offsets, pbOffset, sizeof(AXPBOFFSET_t));\n'
            '\t\tsampleBase = memory_virtualToPhysical(sampleBase);'
        )
        text = replace_once(text, offsets_anchor, offsets_replacement, "AX offsets hook")

    AX_VOICE.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    patch_tracer_header()
    patch_core_fs()
    patch_ax_voice()
    print("BOTW sound source tracer v3 hooks applied")
