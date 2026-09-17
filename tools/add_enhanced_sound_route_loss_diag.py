from pathlib import Path

AX_PATH = Path("src/Cafe/OS/libs/snd_core/ax_voice.cpp")
DIAG_HEADER_PATH = Path("src/Cafe/OS/common/EnhancedSoundRouteDiagnostic.h")

text = AX_PATH.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    text = text.replace(old, new, 1)


replace_once(
    '#include "Cafe/OS/common/EnhancedSoundDualSenseService.h"\n',
    '#include "Cafe/OS/common/EnhancedSoundDualSenseService.h"\n'
    '#include "Cafe/OS/common/EnhancedSoundRouteDiagnostic.h"\n',
    "diagnostic include",
)

replace_once(
    'void AXApplyEnhancedSoundRoute(AXVPB* vpb, MPTR sampleBase)\n',
    'void AXApplyEnhancedSoundRoute(AXVPB* vpb, MPTR sampleBase, std::string_view trigger)\n',
    "route function signature",
)

replace_once(
    '\t\tauto& state = s_enhancedSoundDrcState[(sint32)vpb->index];\n'
    '\t\tstd::optional<EnhancedSoundRouter::RouteMatch> route;\n\n'
    '\t\tif (GetConfig().enhanced_sound_experience && sampleBase != MPTR_NULL)\n'
    '\t\t{\n'
    '\t\t\tEnhancedSoundDualSenseService::EnsureRunning();\n'
    '\t\t\tconst auto source = EnhancedSoundSourceTracker::ResolveSource(sampleBase);\n'
    '\t\t\tif (source)\n'
    '\t\t\t{\n'
    '\t\t\t\tconst auto resolved = EnhancedSoundRouter::Resolve(source->path, source->trackName);\n'
    '\t\t\t\tif (resolved && (resolved->mode == EnhancedSoundRouter::Mode::AddDRC ||\n'
    '\t\t\t\t\tresolved->mode == EnhancedSoundRouter::Mode::SpatialDRC))\n'
    '\t\t\t\t\troute = resolved;\n'
    '\t\t\t}\n'
    '\t\t}\n\n'
    '\t\tif (!route && !state.applied)\n',
    '\t\tauto& state = s_enhancedSoundDrcState[(sint32)vpb->index];\n'
    '\t\tstd::optional<EnhancedSoundSourceTracker::SourceMatch> source;\n'
    '\t\tstd::optional<EnhancedSoundRouter::RouteMatch> route;\n\n'
    '\t\tif (GetConfig().enhanced_sound_experience && sampleBase != MPTR_NULL)\n'
    '\t\t{\n'
    '\t\t\tEnhancedSoundDualSenseService::EnsureRunning();\n'
    '\t\t\tsource = EnhancedSoundSourceTracker::ResolveSource(sampleBase);\n'
    '\t\t\tif (source)\n'
    '\t\t\t{\n'
    '\t\t\t\tconst auto resolved = EnhancedSoundRouter::Resolve(source->path, source->trackName);\n'
    '\t\t\t\tif (resolved && (resolved->mode == EnhancedSoundRouter::Mode::AddDRC ||\n'
    '\t\t\t\t\tresolved->mode == EnhancedSoundRouter::Mode::SpatialDRC))\n'
    '\t\t\t\t\troute = resolved;\n'
    '\t\t\t}\n\n'
    '\t\t\tEnhancedSoundRouteDiagnostic::Record(\n'
    '\t\t\t\ttrigger, static_cast<uint32>(vpb->index),\n'
    '\t\t\t\tvpb->playbackState == (uint32be)1 ? 1u : 0u, sampleBase, state.applied,\n'
    '\t\t\t\tsource.has_value(), source ? std::string_view(source->path) : std::string_view{},\n'
    '\t\t\t\tsource ? std::string_view(source->trackName) : std::string_view{},\n'
    '\t\t\t\troute.has_value(), route ? static_cast<uint32>(route->mode) : 0u,\n'
    '\t\t\t\troute ? route->gain : 0u);\n'
    '\t\t}\n\n'
    '\t\tif (!route && !state.applied)\n',
    "route resolution diagnostic",
)

replace_once(
    'AXApplyEnhancedSoundRoute(vpb, _swapEndianU32(vpb->offsets.samples));',
    'AXApplyEnhancedSoundRoute(vpb, _swapEndianU32(vpb->offsets.samples), "voice_start");',
    "voice start trigger",
)
replace_once(
    'AXApplyEnhancedSoundRoute(vpb, MPTR_NULL);',
    'AXApplyEnhancedSoundRoute(vpb, MPTR_NULL, "voice_stop");',
    "voice stop trigger",
)
replace_once(
    'AXApplyEnhancedSoundRoute(vpb, sampleBase);',
    'AXApplyEnhancedSoundRoute(vpb, sampleBase, "offsets_reuse");',
    "running offsets trigger",
)

replace_once(
    '\tvoid AXSetVoiceSamplesAddr(AXVPB* vpb, void* sampleBase)\n'
    '\t{\n'
    '\t\tvpb->offsets.samples = _swapEndianU32(memory_getVirtualOffsetFromPointer(sampleBase));\n'
    '\t\tAXGetVoiceOffsets(vpb, &vpb->offsets);\n'
    '\t}\n',
    '\tvoid AXSetVoiceSamplesAddr(AXVPB* vpb, void* sampleBase)\n'
    '\t{\n'
    '\t\tconst MPTR enhancedSampleBase = memory_getVirtualOffsetFromPointer(sampleBase);\n'
    '\t\tvpb->offsets.samples = _swapEndianU32(enhancedSampleBase);\n'
    '\t\tif (GetConfig().enhanced_sound_experience && vpb->playbackState == (uint32be)1 && enhancedSampleBase != MPTR_NULL)\n'
    '\t\t{\n'
    '\t\t\tconst auto source = EnhancedSoundSourceTracker::ResolveSource(enhancedSampleBase);\n'
    '\t\t\tstd::optional<EnhancedSoundRouter::RouteMatch> route;\n'
    '\t\t\tif (source)\n'
    '\t\t\t{\n'
    '\t\t\t\tconst auto resolved = EnhancedSoundRouter::Resolve(source->path, source->trackName);\n'
    '\t\t\t\tif (resolved && (resolved->mode == EnhancedSoundRouter::Mode::AddDRC ||\n'
    '\t\t\t\t\tresolved->mode == EnhancedSoundRouter::Mode::SpatialDRC))\n'
    '\t\t\t\t\troute = resolved;\n'
    '\t\t\t}\n'
    '\t\t\tEnhancedSoundRouteDiagnostic::Record(\n'
    '\t\t\t\t"samples_addr_unrouted", static_cast<uint32>(vpb->index), 1u, enhancedSampleBase,\n'
    '\t\t\t\ts_enhancedSoundDrcState[(sint32)vpb->index].applied, source.has_value(),\n'
    '\t\t\t\tsource ? std::string_view(source->path) : std::string_view{},\n'
    '\t\t\t\tsource ? std::string_view(source->trackName) : std::string_view{},\n'
    '\t\t\t\troute.has_value(), route ? static_cast<uint32>(route->mode) : 0u,\n'
    '\t\t\t\troute ? route->gain : 0u);\n'
    '\t\t}\n'
    '\t\tAXGetVoiceOffsets(vpb, &vpb->offsets);\n'
    '\t}\n',
    "samples address observer",
)

header = r'''#pragma once

#include <chrono>
#include <cstdint>
#include <fstream>
#include <mutex>
#include <string>
#include <string_view>

namespace EnhancedSoundRouteDiagnostic
{
    inline std::mutex s_mutex;
    inline std::ofstream s_csv;
    inline uint64_t s_sequence = 0;
    inline uint32_t s_linesSinceFlush = 0;

    inline std::string CsvQuote(std::string_view value)
    {
        std::string out = "\"";
        for (const char c : value)
        {
            if (c == '"')
                out += "\"\"";
            else if (c == '\r' || c == '\n')
                out += ' ';
            else
                out += c;
        }
        out += '"';
        return out;
    }

    inline void EnsureOpenLocked()
    {
        if (s_csv.is_open())
            return;

        bool hasData = false;
        {
            std::ifstream existing("enhanced_sound_route_diag.csv", std::ios::binary | std::ios::ate);
            if (existing)
                hasData = existing.tellg() > 0;
        }
        s_csv.open("enhanced_sound_route_diag.csv", std::ios::out | std::ios::app);
        if (!hasData && s_csv)
        {
            s_csv << "sequence,time_us,trigger,voice,playback,sample_base,state_applied,source_found,source_path,track_name,route_match,route_mode,gain\n";
            s_csv.flush();
        }
    }

    inline void Record(std::string_view trigger, uint32_t voiceIndex, uint32_t playbackState,
        uint32_t sampleBase, bool stateApplied, bool sourceFound, std::string_view sourcePath,
        std::string_view trackName, bool routeMatched, uint32_t routeMode, uint32_t gain)
    {
        std::scoped_lock lock(s_mutex);
        EnsureOpenLocked();
        if (!s_csv)
            return;

        const auto nowUs = std::chrono::duration_cast<std::chrono::microseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count();
        const char* modeName = "none";
        if (routeMatched)
        {
            if (routeMode == 1)
                modeName = "add_drc";
            else if (routeMode == 2)
                modeName = "spatial_drc";
            else
                modeName = "other";
        }

        s_csv << ++s_sequence << ',' << nowUs << ',' << CsvQuote(trigger) << ','
              << voiceIndex << ',' << playbackState << ',' << sampleBase << ','
              << (stateApplied ? 1 : 0) << ',' << (sourceFound ? 1 : 0) << ','
              << CsvQuote(sourcePath) << ',' << CsvQuote(trackName) << ','
              << (routeMatched ? 1 : 0) << ',' << modeName << ',' << gain << '\n';

        if (++s_linesSinceFlush >= 16 || routeMatched || trigger == "samples_addr_unrouted")
        {
            s_csv.flush();
            s_linesSinceFlush = 0;
        }
    }
}
'''

DIAG_HEADER_PATH.write_text(header, encoding="utf-8")
AX_PATH.write_text(text, encoding="utf-8")
print("Enhanced Sound route-loss diagnostic instrumentation applied")
