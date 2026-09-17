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

    old_state = r'''	struct EnhancedSoundDrcState
	{
		bool applied{};
		AXCHMIX_DEPR nativeTv0[AX_TV_CHANNEL_COUNT * AX_BUS_COUNT]{};
		AXCHMIX_DEPR nativeDrc0[AX_DRC_CHANNEL_COUNT * AX_BUS_COUNT]{};
	};'''
    new_state = r'''	struct EnhancedSoundDrcState
	{
		bool applied{};
		bool internalMixWrite{};
		uint16 routeGain{};
		AXCHMIX_DEPR nativeTv0[AX_TV_CHANNEL_COUNT * AX_BUS_COUNT]{};
		AXCHMIX_DEPR nativeDrc0[AX_DRC_CHANNEL_COUNT * AX_BUS_COUNT]{};
	};'''
    if old_state in text:
        text = replace_once(text, old_state, new_state, "Enhanced Sound persisted mix state")
    elif "bool internalMixWrite{};" not in text or "uint16 routeGain{};" not in text:
        raise RuntimeError("Enhanced Sound state anchor not found")

    old_head = r'''		AXVPBInternal_t* internal = __AXVPBInternalVoiceArray + (sint32)vpb->index;
		if ((device == AX_DEV_DRC || device == AX_DEV_TV) && deviceIndex == 0)
			s_enhancedSoundDrcState[(sint32)vpb->index].applied = false;
		sint32 channelCount;'''
    new_head = r'''		AXVPBInternal_t* internal = __AXVPBInternalVoiceArray + (sint32)vpb->index;
		auto& enhancedState = s_enhancedSoundDrcState[(sint32)vpb->index];
		const bool preserveEnhancedMix = !enhancedState.internalMixWrite && enhancedState.applied && deviceIndex == 0 &&
			(device == AX_DEV_DRC || device == AX_DEV_TV);
		sint32 channelCount;'''
    if old_head in text:
        text = replace_once(text, old_head, new_head, "AXSetVoiceDeviceMix persistent state")
    elif "const bool preserveEnhancedMix" not in text:
        raise RuntimeError("AXSetVoiceDeviceMix persistence anchor not found")

    old_tail = r'''		vpb->sync = (uint32)vpb->sync | (AX_SYNCFLAG_DEVICEMIXMASK | AX_SYNCFLAG_DEVICEMIX);
		AXVoiceProtection_Acquire(vpb);
		return 0;
	}'''
    new_tail = r'''		vpb->sync = (uint32)vpb->sync | (AX_SYNCFLAG_DEVICEMIXMASK | AX_SYNCFLAG_DEVICEMIX);
		AXVoiceProtection_Acquire(vpb);

		if (preserveEnhancedMix)
		{
			if (device == AX_DEV_TV)
			{
				memcpy(enhancedState.nativeTv0, &internal->deviceMixTV[0], sizeof(enhancedState.nativeTv0));
				AXCHMIX_DEPR persistedTvMix[AX_TV_CHANNEL_COUNT * AX_BUS_COUNT];
				memcpy(persistedTvMix, enhancedState.nativeTv0, sizeof(persistedTvMix));
				for (uint32 i = 0; i < AX_TV_CHANNEL_COUNT * AX_BUS_COUNT; ++i)
				{
					const uint32 vol = _swapEndianU16(persistedTvMix[i].vol);
					const sint32 delta = _swapEndianS16(persistedTvMix[i].delta);
					persistedTvMix[i].vol = _swapEndianU16(static_cast<uint16>(vol / 2u));
					persistedTvMix[i].delta = _swapEndianS16(static_cast<sint16>(delta / 2));
				}
				enhancedState.internalMixWrite = true;
				AXSetVoiceDeviceMix(vpb, AX_DEV_TV, 0, persistedTvMix);
				enhancedState.internalMixWrite = false;
			}
			else if (device == AX_DEV_DRC)
			{
				memcpy(enhancedState.nativeDrc0, &internal->deviceMixDRC[0], sizeof(enhancedState.nativeDrc0));
				AXCHMIX_DEPR persistedDrcMix[AX_DRC_CHANNEL_COUNT * AX_BUS_COUNT];
				memcpy(persistedDrcMix, enhancedState.nativeDrc0, sizeof(persistedDrcMix));
				for (uint32 channel = 0; channel < 2 && channel < AX_DRC_CHANNEL_COUNT; ++channel)
				{
					const uint32 index = channel * AX_BUS_COUNT;
					const uint32 current = _swapEndianU16(persistedDrcMix[index].vol);
					const uint32 mixed = std::min<uint32>(0xFFFFu, current + enhancedState.routeGain);
					persistedDrcMix[index].vol = _swapEndianU16(static_cast<uint16>(mixed));
				}
				enhancedState.internalMixWrite = true;
				AXSetVoiceDeviceMix(vpb, AX_DEV_DRC, 0, persistedDrcMix);
				enhancedState.internalMixWrite = false;
			}
		}
		return 0;
	}'''
    if old_tail in text:
        text = replace_once(text, old_tail, new_tail, "AXSetVoiceDeviceMix post-write persistence")
    elif "persistedTvMix" not in text or "persistedDrcMix" not in text:
        raise RuntimeError("AXSetVoiceDeviceMix tail anchor not found")

    old_restore = r'''		if (!route)
		{
			// A reused voice no longer matches. Restore the exact native TV and DRC0
			// mixes captured before enhancement.
			AXSetVoiceDeviceMix(vpb, AX_DEV_TV, 0, nativeTvMix);
			AXSetVoiceDeviceMix(vpb, AX_DEV_DRC, 0, nativeDrcMix);
			return;
		}'''
    new_restore = r'''		if (!route)
		{
			// A reused voice no longer matches. Restore the exact native TV and DRC0
			// mixes captured before enhancement without reapplying our persistence hook.
			state.internalMixWrite = true;
			AXSetVoiceDeviceMix(vpb, AX_DEV_TV, 0, nativeTvMix);
			AXSetVoiceDeviceMix(vpb, AX_DEV_DRC, 0, nativeDrcMix);
			state.internalMixWrite = false;
			state = {};
			return;
		}'''
    if old_restore in text:
        text = replace_once(text, old_restore, new_restore, "Enhanced Sound restore guard")
    elif "state.internalMixWrite = true;" not in text:
        raise RuntimeError("Enhanced Sound restore anchor not found")

    old_apply = r'''		// Public AXSetVoiceDeviceMix intentionally marks the previous enhancement
		// stale. Re-arm the sidecar only after the attenuated TV and additive DRC0 writes.
		AXSetVoiceDeviceMix(vpb, AX_DEV_TV, 0, enhancedTvMix);
		AXSetVoiceDeviceMix(vpb, AX_DEV_DRC, 0, enhancedDrcMix);
		memcpy(state.nativeTv0, nativeTvMix, sizeof(state.nativeTv0));
		memcpy(state.nativeDrc0, nativeDrcMix, sizeof(state.nativeDrc0));
		state.applied = true;'''
    new_apply = r'''		// These writes are ours. Native game-side TV/DRC writes that arrive later are
		// captured by AXSetVoiceDeviceMix and the enhancement is reapplied there.
		state.internalMixWrite = true;
		AXSetVoiceDeviceMix(vpb, AX_DEV_TV, 0, enhancedTvMix);
		AXSetVoiceDeviceMix(vpb, AX_DEV_DRC, 0, enhancedDrcMix);
		state.internalMixWrite = false;
		memcpy(state.nativeTv0, nativeTvMix, sizeof(state.nativeTv0));
		memcpy(state.nativeDrc0, nativeDrcMix, sizeof(state.nativeDrc0));
		state.routeGain = route->gain;
		state.applied = true;'''
    if old_apply in text:
        text = replace_once(text, old_apply, new_apply, "Enhanced Sound guarded apply")
    elif "state.routeGain = route->gain;" not in text:
        raise RuntimeError("Enhanced Sound apply anchor not found")

    AX_VOICE.write_text(text, encoding="utf-8")
    print("Enhanced Sound persistent TV 50% / DRC routing patch applied")


if __name__ == "__main__":
    main()
