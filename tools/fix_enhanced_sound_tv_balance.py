from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AX_VOICE = ROOT / "src/Cafe/OS/libs/snd_core/ax_voice.cpp"
DUALSENSE = ROOT / "src/Cafe/OS/common/EnhancedSoundDualSenseService.h"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def patch_dualsense_volume() -> None:
    text = DUALSENSE.read_text(encoding="utf-8-sig")
    old = "\t\t\t180, // audio volume\n"
    new = "\t\t\t255, // audio volume\n"
    if old in text:
        text = replace_once(text, old, new, "DualSense speaker volume")
    elif new not in text:
        raise RuntimeError("DualSense speaker volume anchor not found")
    DUALSENSE.write_text(text, encoding="utf-8")


def patch_tv_balance() -> None:
    text = AX_VOICE.read_text(encoding="utf-8-sig")

    old_state = r'''	struct EnhancedSoundDrcState
	{
		bool applied{};
		AXCHMIX_DEPR nativeDrc0[AX_DRC_CHANNEL_COUNT * AX_BUS_COUNT]{};
	};'''
    new_state = r'''	struct EnhancedSoundDrcState
	{
		bool applied{};
		AXCHMIX_DEPR nativeTv0[AX_TV_CHANNEL_COUNT * AX_BUS_COUNT]{};
		AXCHMIX_DEPR nativeDrc0[AX_DRC_CHANNEL_COUNT * AX_BUS_COUNT]{};
	};'''
    if old_state in text:
        text = replace_once(text, old_state, new_state, "Enhanced Sound native TV state")
    elif "nativeTv0[AX_TV_CHANNEL_COUNT * AX_BUS_COUNT]" not in text:
        raise RuntimeError("Enhanced Sound DRC state anchor not found")

    old_stale = "\t\tif (device == AX_DEV_DRC && deviceIndex == 0)\n\t\t\ts_enhancedSoundDrcState[(sint32)vpb->index].applied = false;\n"
    new_stale = "\t\tif ((device == AX_DEV_DRC || device == AX_DEV_TV) && deviceIndex == 0)\n\t\t\ts_enhancedSoundDrcState[(sint32)vpb->index].applied = false;\n"
    if old_stale in text:
        text = replace_once(text, old_stale, new_stale, "Enhanced Sound native mix refresh")
    elif new_stale not in text:
        raise RuntimeError("Enhanced Sound stale-state anchor not found")

    old_native = r'''		AXVPBInternal_t* internal = __AXVPBInternalVoiceArray + (sint32)vpb->index;
		AXCHMIX_DEPR nativeDrcMix[AX_DRC_CHANNEL_COUNT * AX_BUS_COUNT];
		if (state.applied)
			memcpy(nativeDrcMix, state.nativeDrc0, sizeof(nativeDrcMix));
		else
			memcpy(nativeDrcMix, &internal->deviceMixDRC[0], sizeof(nativeDrcMix));'''
    new_native = r'''		AXVPBInternal_t* internal = __AXVPBInternalVoiceArray + (sint32)vpb->index;
		AXCHMIX_DEPR nativeTvMix[AX_TV_CHANNEL_COUNT * AX_BUS_COUNT];
		AXCHMIX_DEPR nativeDrcMix[AX_DRC_CHANNEL_COUNT * AX_BUS_COUNT];
		if (state.applied)
		{
			memcpy(nativeTvMix, state.nativeTv0, sizeof(nativeTvMix));
			memcpy(nativeDrcMix, state.nativeDrc0, sizeof(nativeDrcMix));
		}
		else
		{
			memcpy(nativeTvMix, &internal->deviceMixTV[0], sizeof(nativeTvMix));
			memcpy(nativeDrcMix, &internal->deviceMixDRC[0], sizeof(nativeDrcMix));
		}'''
    if old_native in text:
        text = replace_once(text, old_native, new_native, "Enhanced Sound native TV/DRC capture")
    elif "AXCHMIX_DEPR nativeTvMix[AX_TV_CHANNEL_COUNT * AX_BUS_COUNT]" not in text:
        raise RuntimeError("Enhanced Sound native mix capture anchor not found")

    old_restore = r'''		if (!route)
		{
			// A reused voice no longer matches. Remove only our additive send and
			// restore the exact native DRC0 mix captured before enhancement.
			AXSetVoiceDeviceMix(vpb, AX_DEV_DRC, 0, nativeDrcMix);
			return;
		}

		AXCHMIX_DEPR enhancedDrcMix[AX_DRC_CHANNEL_COUNT * AX_BUS_COUNT];'''
    new_restore = r'''		if (!route)
		{
			// A reused voice no longer matches. Restore the exact native TV and DRC0
			// mixes captured before enhancement.
			AXSetVoiceDeviceMix(vpb, AX_DEV_TV, 0, nativeTvMix);
			AXSetVoiceDeviceMix(vpb, AX_DEV_DRC, 0, nativeDrcMix);
			return;
		}

		AXCHMIX_DEPR enhancedTvMix[AX_TV_CHANNEL_COUNT * AX_BUS_COUNT];
		memcpy(enhancedTvMix, nativeTvMix, sizeof(enhancedTvMix));
		for (uint32 i = 0; i < AX_TV_CHANNEL_COUNT * AX_BUS_COUNT; ++i)
		{
			const uint32 vol = _swapEndianU16(enhancedTvMix[i].vol);
			const sint32 delta = _swapEndianS16(enhancedTvMix[i].delta);
			enhancedTvMix[i].vol = _swapEndianU16(static_cast<uint16>(vol / 2u));
			enhancedTvMix[i].delta = _swapEndianS16(static_cast<sint16>(delta / 2));
		}

		AXCHMIX_DEPR enhancedDrcMix[AX_DRC_CHANNEL_COUNT * AX_BUS_COUNT];'''
    if old_restore in text:
        text = replace_once(text, old_restore, new_restore, "Enhanced Sound TV attenuation")
    elif "enhancedTvMix[AX_TV_CHANNEL_COUNT * AX_BUS_COUNT]" not in text:
        raise RuntimeError("Enhanced Sound restore anchor not found")

    old_write = r'''		// Public AXSetVoiceDeviceMix intentionally marks the previous enhancement
		// stale. Re-arm the sidecar only after the native-plus-additive DRC0 write.
		AXSetVoiceDeviceMix(vpb, AX_DEV_DRC, 0, enhancedDrcMix);
		memcpy(state.nativeDrc0, nativeDrcMix, sizeof(state.nativeDrc0));
		state.applied = true;'''
    new_write = r'''		// Public AXSetVoiceDeviceMix intentionally marks the previous enhancement
		// stale. Re-arm the sidecar only after the attenuated TV and additive DRC0 writes.
		AXSetVoiceDeviceMix(vpb, AX_DEV_TV, 0, enhancedTvMix);
		AXSetVoiceDeviceMix(vpb, AX_DEV_DRC, 0, enhancedDrcMix);
		memcpy(state.nativeTv0, nativeTvMix, sizeof(state.nativeTv0));
		memcpy(state.nativeDrc0, nativeDrcMix, sizeof(state.nativeDrc0));
		state.applied = true;'''
    if old_write in text:
        text = replace_once(text, old_write, new_write, "Enhanced Sound TV/DRC write")
    elif "memcpy(state.nativeTv0, nativeTvMix" not in text:
        raise RuntimeError("Enhanced Sound write anchor not found")

    AX_VOICE.write_text(text, encoding="utf-8")


def main() -> None:
    patch_dualsense_volume()
    patch_tv_balance()
    print("Enhanced Sound TV 50% balance + DualSense 255 volume applied")


if __name__ == "__main__":
    main()
