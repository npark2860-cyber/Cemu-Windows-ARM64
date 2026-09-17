from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "src/Cafe/OS/common/EnhancedSoundRouter.h"
GRAPHIC_PACK = ROOT / "src/Cafe/GraphicPack/GraphicPack2.cpp"
AX_VOICE = ROOT / "src/Cafe/OS/libs/snd_core/ax_voice.cpp"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def patch_router(text: str) -> str:
    old = "\t\tAddDRC = 1,\n"
    new = "\t\tAddDRC = 1,\n\t\tSpatialDRC = 2,\n"
    if old in text:
        return replace_once(text, old, new, "router mode enum")
    if "SpatialDRC = 2" not in text:
        raise RuntimeError("router mode enum anchor not found")
    return text


def patch_graphic_pack(text: str) -> str:
    old = r'''		const auto mode = routes.FindOption("mode");
		if (!mode || !boost::iequals(*mode, "add_drc"))
		{
			cemuLog_log(LogType::Force, "Graphic pack \"{}\": sound_routes.ini section \"{}\" skipped because Stage A mode must be add_drc", owner, section);
			continue;
		}'''
    new = r'''		const auto mode = routes.FindOption("mode");
		if (!mode)
		{
			cemuLog_log(LogType::Force, "Graphic pack \"{}\": sound_routes.ini section \"{}\" skipped because mode is missing", owner, section);
			continue;
		}
		if (boost::iequals(*mode, "add_drc"))
			rule.mode = EnhancedSoundRouter::Mode::AddDRC;
		else if (boost::iequals(*mode, "spatial_drc"))
			rule.mode = EnhancedSoundRouter::Mode::SpatialDRC;
		else
		{
			cemuLog_log(LogType::Force, "Graphic pack \"{}\": sound_routes.ini section \"{}\" skipped because mode must be add_drc or spatial_drc", owner, section);
			continue;
		}'''
    if old in text:
        return replace_once(text, old, new, "Graphic Pack route mode parser")
    if 'boost::iequals(*mode, "spatial_drc")' not in text:
        raise RuntimeError("Graphic Pack route mode parser anchor not found")
    return text


def patch_ax_voice(text: str) -> str:
    old_state = r'''	struct EnhancedSoundDrcState
	{
		bool applied{};
		bool internalMixWrite{};
		uint16 routeGain{};
		AXCHMIX_DEPR nativeTv0[AX_TV_CHANNEL_COUNT * AX_BUS_COUNT]{};
		AXCHMIX_DEPR nativeDrc0[AX_DRC_CHANNEL_COUNT * AX_BUS_COUNT]{};
	};

	EnhancedSoundDrcState s_enhancedSoundDrcState[AX_MAX_VOICES]{};'''
    new_state = r'''	struct EnhancedSoundDrcState
	{
		bool applied{};
		bool internalMixWrite{};
		uint16 routeGain{};
		EnhancedSoundRouter::Mode routeMode{ EnhancedSoundRouter::Mode::AddDRC };
		AXCHMIX_DEPR nativeTv0[AX_TV_CHANNEL_COUNT * AX_BUS_COUNT]{};
		AXCHMIX_DEPR nativeDrc0[AX_DRC_CHANNEL_COUNT * AX_BUS_COUNT]{};
	};

	EnhancedSoundDrcState s_enhancedSoundDrcState[AX_MAX_VOICES]{};

	void AXApplyEnhancedSoundTvPolicy(AXCHMIX_DEPR* tvMix, EnhancedSoundRouter::Mode mode)
	{
		if (mode != EnhancedSoundRouter::Mode::AddDRC)
			return;
		for (uint32 i = 0; i < AX_TV_CHANNEL_COUNT * AX_BUS_COUNT; ++i)
		{
			const uint32 vol = _swapEndianU16(tvMix[i].vol);
			const sint32 delta = _swapEndianS16(tvMix[i].delta);
			tvMix[i].vol = _swapEndianU16(static_cast<uint16>(vol / 2u));
			tvMix[i].delta = _swapEndianS16(static_cast<sint16>(delta / 2));
		}
	}

	void AXApplyEnhancedSoundDrcPolicy(AXCHMIX_DEPR* drcMix, const AXCHMIX_DEPR* nativeTvMix,
		EnhancedSoundRouter::Mode mode, uint16 routeGain)
	{
		for (uint32 channel = 0; channel < 2 && channel < AX_DRC_CHANNEL_COUNT; ++channel)
		{
			const uint32 index = channel * AX_BUS_COUNT;
			uint32 send = routeGain;
			sint32 sendDelta = 0;
			if (mode == EnhancedSoundRouter::Mode::SpatialDRC)
			{
				if (channel >= AX_TV_CHANNEL_COUNT)
					continue;
				const uint32 tvVolume = std::min<uint32>(0x8000u, _swapEndianU16(nativeTvMix[index].vol));
				send = static_cast<uint32>((static_cast<uint64_t>(routeGain) * tvVolume + 0x4000u) / 0x8000u);
				const sint32 tvDelta = _swapEndianS16(nativeTvMix[index].delta);
				const int64_t scaledDelta = (static_cast<int64_t>(tvDelta) * routeGain) / 0x8000;
				sendDelta = static_cast<sint32>(std::clamp<int64_t>(scaledDelta, -32768, 32767));
			}

			const uint32 current = _swapEndianU16(drcMix[index].vol);
			const uint32 mixed = std::min<uint32>(0xFFFFu, current + send);
			drcMix[index].vol = _swapEndianU16(static_cast<uint16>(mixed));
			if (mode == EnhancedSoundRouter::Mode::SpatialDRC)
			{
				const sint32 currentDelta = _swapEndianS16(drcMix[index].delta);
				const sint32 mixedDelta = static_cast<sint32>(std::clamp<int64_t>(
					static_cast<int64_t>(currentDelta) + sendDelta, -32768, 32767));
				drcMix[index].delta = _swapEndianS16(static_cast<sint16>(mixedDelta));
			}
		}
	}'''
    if old_state in text:
        text = replace_once(text, old_state, new_state, "spatial DRC state/helpers")
    elif "AXApplyEnhancedSoundDrcPolicy" not in text or "routeMode" not in text:
        raise RuntimeError("spatial DRC state anchor not found")

    old_persist = r'''		if (preserveEnhancedMix)
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
		}'''
    new_persist = r'''		if (preserveEnhancedMix)
		{
			if (device == AX_DEV_TV)
			{
				memcpy(enhancedState.nativeTv0, &internal->deviceMixTV[0], sizeof(enhancedState.nativeTv0));
				if (enhancedState.routeMode == EnhancedSoundRouter::Mode::AddDRC)
				{
					AXCHMIX_DEPR persistedTvMix[AX_TV_CHANNEL_COUNT * AX_BUS_COUNT];
					memcpy(persistedTvMix, enhancedState.nativeTv0, sizeof(persistedTvMix));
					AXApplyEnhancedSoundTvPolicy(persistedTvMix, enhancedState.routeMode);
					enhancedState.internalMixWrite = true;
					AXSetVoiceDeviceMix(vpb, AX_DEV_TV, 0, persistedTvMix);
					enhancedState.internalMixWrite = false;
				}
				else if (enhancedState.routeMode == EnhancedSoundRouter::Mode::SpatialDRC)
				{
					// A spatial route follows the game's latest TV distance/pan envelope.
					// TV stays native; only the controller send is refreshed here.
					AXCHMIX_DEPR persistedDrcMix[AX_DRC_CHANNEL_COUNT * AX_BUS_COUNT];
					memcpy(persistedDrcMix, enhancedState.nativeDrc0, sizeof(persistedDrcMix));
					AXApplyEnhancedSoundDrcPolicy(persistedDrcMix, enhancedState.nativeTv0,
						enhancedState.routeMode, enhancedState.routeGain);
					enhancedState.internalMixWrite = true;
					AXSetVoiceDeviceMix(vpb, AX_DEV_DRC, 0, persistedDrcMix);
					enhancedState.internalMixWrite = false;
				}
			}
			else if (device == AX_DEV_DRC)
			{
				memcpy(enhancedState.nativeDrc0, &internal->deviceMixDRC[0], sizeof(enhancedState.nativeDrc0));
				AXCHMIX_DEPR persistedDrcMix[AX_DRC_CHANNEL_COUNT * AX_BUS_COUNT];
				memcpy(persistedDrcMix, enhancedState.nativeDrc0, sizeof(persistedDrcMix));
				AXApplyEnhancedSoundDrcPolicy(persistedDrcMix, enhancedState.nativeTv0,
					enhancedState.routeMode, enhancedState.routeGain);
				enhancedState.internalMixWrite = true;
				AXSetVoiceDeviceMix(vpb, AX_DEV_DRC, 0, persistedDrcMix);
				enhancedState.internalMixWrite = false;
			}
		}'''
    if old_persist in text:
        text = replace_once(text, old_persist, new_persist, "persistent spatial DRC refresh")
    elif "A spatial route follows the game's latest TV distance/pan envelope" not in text:
        raise RuntimeError("persistent spatial DRC anchor not found")

    old_resolve = r'''				const auto resolved = EnhancedSoundRouter::Resolve(source->path, source->trackName);
				if (resolved && resolved->mode == EnhancedSoundRouter::Mode::AddDRC)
					route = resolved;'''
    new_resolve = r'''				const auto resolved = EnhancedSoundRouter::Resolve(source->path, source->trackName);
				if (resolved && (resolved->mode == EnhancedSoundRouter::Mode::AddDRC ||
					resolved->mode == EnhancedSoundRouter::Mode::SpatialDRC))
					route = resolved;'''
    if old_resolve in text:
        text = replace_once(text, old_resolve, new_resolve, "spatial route resolve")
    elif "resolved->mode == EnhancedSoundRouter::Mode::SpatialDRC" not in text:
        raise RuntimeError("spatial route resolve anchor not found")

    old_apply = r'''		AXCHMIX_DEPR enhancedTvMix[AX_TV_CHANNEL_COUNT * AX_BUS_COUNT];
		memcpy(enhancedTvMix, nativeTvMix, sizeof(enhancedTvMix));
		for (uint32 i = 0; i < AX_TV_CHANNEL_COUNT * AX_BUS_COUNT; ++i)
		{
			const uint32 vol = _swapEndianU16(enhancedTvMix[i].vol);
			const sint32 delta = _swapEndianS16(enhancedTvMix[i].delta);
			enhancedTvMix[i].vol = _swapEndianU16(static_cast<uint16>(vol / 2u));
			enhancedTvMix[i].delta = _swapEndianS16(static_cast<sint16>(delta / 2));
		}

		AXCHMIX_DEPR enhancedDrcMix[AX_DRC_CHANNEL_COUNT * AX_BUS_COUNT];
		memcpy(enhancedDrcMix, nativeDrcMix, sizeof(enhancedDrcMix));
		for (uint32 channel = 0; channel < 2 && channel < AX_DRC_CHANNEL_COUNT; ++channel)
		{
			const uint32 index = channel * AX_BUS_COUNT;
			const uint32 current = _swapEndianU16(enhancedDrcMix[index].vol);
			const uint32 mixed = std::min<uint32>(0xFFFFu, current + route->gain);
			enhancedDrcMix[index].vol = _swapEndianU16(static_cast<uint16>(mixed));
		}'''
    new_apply = r'''		AXCHMIX_DEPR enhancedTvMix[AX_TV_CHANNEL_COUNT * AX_BUS_COUNT];
		memcpy(enhancedTvMix, nativeTvMix, sizeof(enhancedTvMix));
		AXApplyEnhancedSoundTvPolicy(enhancedTvMix, route->mode);

		AXCHMIX_DEPR enhancedDrcMix[AX_DRC_CHANNEL_COUNT * AX_BUS_COUNT];
		memcpy(enhancedDrcMix, nativeDrcMix, sizeof(enhancedDrcMix));
		AXApplyEnhancedSoundDrcPolicy(enhancedDrcMix, nativeTvMix, route->mode, route->gain);'''
    if old_apply in text:
        text = replace_once(text, old_apply, new_apply, "initial spatial DRC apply")
    elif "AXApplyEnhancedSoundTvPolicy(enhancedTvMix, route->mode);" not in text:
        raise RuntimeError("initial spatial DRC apply anchor not found")

    old_store = r'''		state.routeGain = route->gain;
		state.applied = true;'''
    new_store = r'''		state.routeGain = route->gain;
		state.routeMode = route->mode;
		state.applied = true;'''
    if old_store in text:
        text = replace_once(text, old_store, new_store, "spatial route mode persistence")
    elif "state.routeMode = route->mode;" not in text:
        raise RuntimeError("spatial route mode persistence anchor not found")

    return text


def main() -> None:
    router = ROUTER.read_text(encoding="utf-8-sig")
    graphic_pack = GRAPHIC_PACK.read_text(encoding="utf-8-sig")
    ax_voice = AX_VOICE.read_text(encoding="utf-8-sig")

    ROUTER.write_text(patch_router(router), encoding="utf-8")
    GRAPHIC_PACK.write_text(patch_graphic_pack(graphic_pack), encoding="utf-8")
    AX_VOICE.write_text(patch_ax_voice(ax_voice), encoding="utf-8")
    print("Enhanced Sound spatial_drc routing mode applied")


if __name__ == "__main__":
    main()
