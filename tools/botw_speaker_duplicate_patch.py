from pathlib import Path

import botw_sound_source_tracer_patch as tracer

ROOT = Path(__file__).resolve().parents[1]
TRACER_HEADER = ROOT / "src/Cafe/OS/common/BotWSoundSourceTracer.h"
AX_VOICE = ROOT / "src/Cafe/OS/libs/snd_core/ax_voice.cpp"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def patch_routing_helper() -> None:
    text = TRACER_HEADER.read_text(encoding="utf-8-sig")
    if "ShouldDuplicateToDRC" in text:
        return

    anchor = (
        '\tinline void TraceVoice(std::string_view eventName, uint32 voiceIndex, uint32 sampleBase,\n'
    )
    helper = r'''	inline std::optional<SourceMatch> ResolveSourceForRoutingLocked(uint32 sampleBase)
	{
		auto source = FindSourceLocked(sampleBase);
		if (source && source->trackName.empty())
		{
			const auto fingerprintSource = BotWSoundSourceTracerV3Support::FindMatchForPath(sampleBase, source->path);
			if (fingerprintSource)
			{
				source->start = fingerprintSource->sourceStart;
				source->size = fingerprintSource->sourceSize;
				source->offset = fingerprintSource->dataOffset;
				source->path = fingerprintSource->path;
				source->trackName = fingerprintSource->trackName;
			}
		}
		if (!source)
		{
			const auto fingerprintSource = BotWSoundFingerprintCatalog::FindMatch(sampleBase);
			if (fingerprintSource)
			{
				SourceMatch match;
				match.start = fingerprintSource->sourceStart;
				match.size = fingerprintSource->sourceSize;
				match.offset = fingerprintSource->dataOffset;
				match.path = fingerprintSource->path;
				match.trackName = fingerprintSource->trackName;
				source = std::move(match);
			}
		}
		return source;
	}

	inline bool ShouldDuplicateToDRC(uint32 sampleBase)
	{
		if (sampleBase == 0)
			return false;
		std::scoped_lock lock(s_mutex);
		const auto source = ResolveSourceForRoutingLocked(sampleBase);
		if (!source)
			return false;

		// Physical proof whitelist: only already runtime-confirmed empty-air weapon swing cues.
		// Do not include impact, equip, landing, enemy-hit or inferred semantic sounds here.
		const std::string_view track = source->trackName;
		return track == "Spear_Swing1" || track == "Spear_Swing2" ||
			track == "Spear_SwingFast1" || track == "Spear_SwingFast2" ||
			track == "LSword_Swing1" || track == "LSword_Swing3" || track == "LSword_Swing5";
	}

'''
    text = replace_once(text, anchor, helper + anchor, "speaker routing helper")
    TRACER_HEADER.write_text(text, encoding="utf-8")


def patch_ax_duplicate_route() -> None:
    text = AX_VOICE.read_text(encoding="utf-8-sig")
    if 'route_drc_duplicate' in text:
        return

    anchor = (
        '\t\t\t\t\tBotWSoundSourceTracer::TraceVoice("start", (uint32)vpb->index, traceSampleBase,\n'
        '\t\t\t\t\t\t_swapEndianU16(vpb->offsets.format), _swapEndianU32(vpb->offsets.currentOffset),\n'
        '\t\t\t\t\t\t_swapEndianU32(vpb->offsets.endOffset), _swapEndianU32(vpb->offsets.loopOffset),\n'
        '\t\t\t\t\t\t_swapEndianU16(internal->deviceMixMaskTV[0]), _swapEndianU16(internal->deviceMixMaskDRC[0]));\n'
    )

    replacement = anchor + r'''					if (BotWSoundSourceTracer::ShouldDuplicateToDRC(traceSampleBase))
					{
						const bool traceDrcAlreadyRouted =
							internal->deviceMixMaskDRC[0] != 0 || internal->deviceMixMaskDRC[1] != 0 ||
							internal->deviceMixMaskDRC[2] != 0 || internal->deviceMixMaskDRC[3] != 0;
						if (!traceDrcAlreadyRouted)
						{
							AXCHMIX_DEPR traceDrcMix[AX_DRC_CHANNEL_COUNT * AX_BUS_COUNT] = {};
							// DRC0 stereo main bus, 75% nominal voice gain. TV mix is left untouched.
							traceDrcMix[0 * AX_BUS_COUNT + 0].vol = _swapEndianU16(0x6000);
							traceDrcMix[1 * AX_BUS_COUNT + 0].vol = _swapEndianU16(0x6000);
							AXSetVoiceDeviceMix(vpb, AX_DEV_DRC, 0, traceDrcMix);
							BotWSoundSourceTracer::TraceVoice("route_drc_duplicate", (uint32)vpb->index, traceSampleBase,
								_swapEndianU16(vpb->offsets.format), _swapEndianU32(vpb->offsets.currentOffset),
								_swapEndianU32(vpb->offsets.endOffset), _swapEndianU32(vpb->offsets.loopOffset),
								_swapEndianU16(internal->deviceMixMaskTV[0]), _swapEndianU16(internal->deviceMixMaskDRC[0]));
						}
						else
						{
							BotWSoundSourceTracer::TraceVoice("route_drc_existing", (uint32)vpb->index, traceSampleBase,
								_swapEndianU16(vpb->offsets.format), _swapEndianU32(vpb->offsets.currentOffset),
								_swapEndianU32(vpb->offsets.endOffset), _swapEndianU32(vpb->offsets.loopOffset),
								_swapEndianU16(internal->deviceMixMaskTV[0]), _swapEndianU16(internal->deviceMixMaskDRC[0]));
						}
					}
'''
    text = replace_once(text, anchor, replacement, "AX speaker duplicate hook")
    AX_VOICE.write_text(text, encoding="utf-8")


def main() -> None:
    # Reuse the physically validated v3 source-correlation path first.
    tracer.patch_tracer_header()
    tracer.patch_core_fs()
    tracer.patch_ax_voice()

    # Add only the narrow DRC duplicate proof on top.
    patch_routing_helper()
    patch_ax_duplicate_route()
    print("BOTW DualSense speaker duplicate proof hooks applied")


if __name__ == "__main__":
    main()
