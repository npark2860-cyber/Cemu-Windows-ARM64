from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AX_VOICE = ROOT / "src/Cafe/OS/libs/snd_core/ax_voice.cpp"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    text = AX_VOICE.read_text(encoding="utf-8-sig")

    if "struct EnhancedSoundDrcState" not in text:
        anchor = "\tstd::vector<AXVPB*> __AXFreeVoices;\n"
        state = r'''

	struct EnhancedSoundDrcState
	{
		bool applied{};
		AXCHMIX_DEPR nativeDrc0[AX_DRC_CHANNEL_COUNT * AX_BUS_COUNT]{};
	};

	EnhancedSoundDrcState s_enhancedSoundDrcState[AX_MAX_VOICES]{};
'''
        text = replace_once(text, anchor, anchor + state, "Enhanced Sound per-voice DRC state")

    if "s_enhancedSoundDrcState[index] = {};" not in text:
        anchor = "\t\tuint32 index = GetVoiceIndex(vpb);\n"
        text = replace_once(
            text,
            anchor,
            anchor + "\t\ts_enhancedSoundDrcState[index] = {};\n",
            "Enhanced Sound voice reset",
        )

    if "s_enhancedSoundDrcState[(sint32)vpb->index].applied = false;" not in text:
        anchor = (
            "\t\tAXVPBInternal_t* internal = __AXVPBInternalVoiceArray + (sint32)vpb->index;\n"
            "\t\tsint32 channelCount;\n"
        )
        replacement = (
            "\t\tAXVPBInternal_t* internal = __AXVPBInternalVoiceArray + (sint32)vpb->index;\n"
            "\t\tif (device == AX_DEV_DRC && deviceIndex == 0)\n"
            "\t\t\ts_enhancedSoundDrcState[(sint32)vpb->index].applied = false;\n"
            "\t\tsint32 channelCount;\n"
        )
        text = replace_once(text, anchor, replacement, "Enhanced Sound native DRC refresh")

    if "void AXApplyEnhancedSoundRoute" not in text:
        anchor = "\tvoid AXSetVoiceState(AXVPB* vpb, sint32 voiceState)\n"
        helper = r'''	void AXApplyEnhancedSoundRoute(AXVPB* vpb, MPTR sampleBase)
	{
		if (vpb == nullptr)
			return;

		auto& state = s_enhancedSoundDrcState[(sint32)vpb->index];
		std::optional<EnhancedSoundRouter::RouteMatch> route;

		if (GetConfig().enhanced_sound_experience && sampleBase != MPTR_NULL)
		{
			EnhancedSoundDualSenseService::EnsureRunning();
			const auto source = EnhancedSoundSourceTracker::ResolveSource(sampleBase);
			if (source)
			{
				const auto resolved = EnhancedSoundRouter::Resolve(source->path, source->trackName);
				if (resolved && resolved->mode == EnhancedSoundRouter::Mode::AddDRC)
					route = resolved;
			}
		}

		if (!route && !state.applied)
			return;

		AXVPBInternal_t* internal = __AXVPBInternalVoiceArray + (sint32)vpb->index;
		AXCHMIX_DEPR nativeDrcMix[AX_DRC_CHANNEL_COUNT * AX_BUS_COUNT];
		if (state.applied)
			memcpy(nativeDrcMix, state.nativeDrc0, sizeof(nativeDrcMix));
		else
			memcpy(nativeDrcMix, &internal->deviceMixDRC[0], sizeof(nativeDrcMix));

		if (!route)
		{
			// A reused voice no longer matches. Remove only our additive send and
			// restore the exact native DRC0 mix captured before enhancement.
			AXSetVoiceDeviceMix(vpb, AX_DEV_DRC, 0, nativeDrcMix);
			return;
		}

		AXCHMIX_DEPR enhancedDrcMix[AX_DRC_CHANNEL_COUNT * AX_BUS_COUNT];
		memcpy(enhancedDrcMix, nativeDrcMix, sizeof(enhancedDrcMix));
		for (uint32 channel = 0; channel < 2 && channel < AX_DRC_CHANNEL_COUNT; ++channel)
		{
			const uint32 index = channel * AX_BUS_COUNT;
			const uint32 current = _swapEndianU16(enhancedDrcMix[index].vol);
			const uint32 mixed = std::min<uint32>(0xFFFFu, current + route->gain);
			enhancedDrcMix[index].vol = _swapEndianU16(static_cast<uint16>(mixed));
		}

		// Public AXSetVoiceDeviceMix intentionally marks the previous enhancement
		// stale. Re-arm the sidecar only after the native-plus-additive DRC0 write.
		AXSetVoiceDeviceMix(vpb, AX_DEV_DRC, 0, enhancedDrcMix);
		memcpy(state.nativeDrc0, nativeDrcMix, sizeof(state.nativeDrc0));
		state.applied = true;
	}

'''
        text = replace_once(text, anchor, helper + anchor, "Enhanced Sound route refresh helper")

    old_state_hook = r'''			if (voiceState == 1 && GetConfig().enhanced_sound_experience)
			{
				EnhancedSoundDualSenseService::EnsureRunning();
				const MPTR enhancedSampleBase = _swapEndianU32(vpb->offsets.samples);
				if (enhancedSampleBase != MPTR_NULL)
				{
					const auto source = EnhancedSoundSourceTracker::ResolveSource(enhancedSampleBase);
					if (source)
					{
						const auto route = EnhancedSoundRouter::Resolve(source->path, source->trackName);
						if (route && route->mode == EnhancedSoundRouter::Mode::AddDRC)
						{
							AXCHMIX_DEPR enhancedDrcMix[AX_DRC_CHANNEL_COUNT * AX_BUS_COUNT];
							memcpy(enhancedDrcMix, &internal->deviceMixDRC[0], sizeof(enhancedDrcMix));
							for (uint32 channel = 0; channel < 2 && channel < AX_DRC_CHANNEL_COUNT; ++channel)
							{
								const uint32 index = channel * AX_BUS_COUNT;
								const uint32 current = static_cast<uint16>(enhancedDrcMix[index].vol);
								const uint32 mixed = std::min<uint32>(0xFFFFu, current + route->gain);
								enhancedDrcMix[index].vol = static_cast<uint16>(mixed);
							}
							// AXSetVoiceDeviceMix rewrites DRC0, so feed it a copy of the complete
							// native mix plus our main-bus send. TV and every native DRC entry survive.
							AXSetVoiceDeviceMix(vpb, AX_DEV_DRC, 0, enhancedDrcMix);
						}
					}
				}
			}
'''
    if old_state_hook in text:
        new_state_hook = r'''			if (voiceState == 1)
			{
				AXApplyEnhancedSoundRoute(vpb, _swapEndianU32(vpb->offsets.samples));
			}
'''
        text = replace_once(text, old_state_hook, new_state_hook, "Enhanced Sound voice-start refresh")
    elif "AXApplyEnhancedSoundRoute(vpb, _swapEndianU32(vpb->offsets.samples));" not in text:
        raise RuntimeError("Enhanced Sound voice-start hook not found")

    if "AXApplyEnhancedSoundRoute(vpb, MPTR_NULL);" not in text:
        anchor = "\t\t\tif (voiceState == 0)\n\t\t\t{\n\t\t\t\tvpb->depop = (uint32be)1;\n"
        replacement = (
            "\t\t\tif (voiceState == 0)\n"
            "\t\t\t{\n"
            "\t\t\t\tAXApplyEnhancedSoundRoute(vpb, MPTR_NULL);\n"
            "\t\t\t\tvpb->depop = (uint32be)1;\n"
        )
        text = replace_once(text, anchor, replacement, "Enhanced Sound voice-stop restore")

    if "AXApplyEnhancedSoundRoute(vpb, sampleBase);" not in text:
        anchor = (
            "\t\tmemcpy(&vpb->offsets, pbOffset, sizeof(AXPBOFFSET_t));\n"
            "\t\tsampleBase = memory_virtualToPhysical(sampleBase);\n"
        )
        replacement = (
            "\t\tmemcpy(&vpb->offsets, pbOffset, sizeof(AXPBOFFSET_t));\n"
            "\t\t// BOTW and other games can reuse a running AX voice with a new sample.\n"
            "\t\t// Re-resolve only in that reuse case; initial voices are resolved on start.\n"
            "\t\tif (vpb->playbackState == (uint32be)1)\n"
            "\t\t\tAXApplyEnhancedSoundRoute(vpb, sampleBase);\n"
            "\t\tsampleBase = memory_virtualToPhysical(sampleBase);\n"
        )
        text = replace_once(text, anchor, replacement, "Enhanced Sound running-voice offset refresh")

    AX_VOICE.write_text(text, encoding="utf-8")
    print("Enhanced Sound running-voice route refresh applied")


if __name__ == "__main__":
    main()
