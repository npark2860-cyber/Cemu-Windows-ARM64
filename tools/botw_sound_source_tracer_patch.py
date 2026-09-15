from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_FS = ROOT / "src/Cafe/OS/libs/coreinit/coreinit_FS.cpp"
AX_VOICE = ROOT / "src/Cafe/OS/libs/snd_core/ax_voice.cpp"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


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
    patch_core_fs()
    patch_ax_voice()
    print("BOTW sound source tracer hooks applied")
