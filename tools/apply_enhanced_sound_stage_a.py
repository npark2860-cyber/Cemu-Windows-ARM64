from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


def write(path: str, text: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def patch_config() -> None:
    path = "src/config/CemuConfig.h"
    text = read(path)
    anchor = "\tsint32 tv_volume = 50, pad_volume = 0, input_volume = 50, portal_volume = 50;\n"
    if "enhanced_sound_experience" not in text:
        text = replace_once(text, anchor, anchor + "\tbool enhanced_sound_experience = false;\n", "CemuConfig audio bool")
    write(path, text)

    path = "src/config/CemuConfig.cpp"
    text = read(path)
    load_anchor = "\tpad_volume = audio.get(\"PadVolume\", 0);\n"
    if 'audio.get("EnhancedSoundExperience"' not in text:
        text = replace_once(text, load_anchor, load_anchor + "\tenhanced_sound_experience = audio.get(\"EnhancedSoundExperience\", false);\n", "CemuConfig load")
    save_anchor = "\taudio.set(\"PadVolume\", pad_volume);\n"
    if 'audio.set("EnhancedSoundExperience"' not in text:
        text = replace_once(text, save_anchor, save_anchor + "\taudio.set(\"EnhancedSoundExperience\", enhanced_sound_experience);\n", "CemuConfig save")
    write(path, text)


def patch_ui() -> None:
    path = "src/gui/wxgui/GeneralSettings2.h"
    text = read(path)
    anchor = "\twxSlider *m_tv_volume, *m_pad_volume, *m_input_volume, *m_portal_volume;\n"
    if "m_enhanced_sound_experience" not in text:
        text = replace_once(text, anchor, anchor + "\twxCheckBox* m_enhanced_sound_experience;\n", "GeneralSettings2 checkbox member")
    write(path, text)

    path = "src/gui/wxgui/GeneralSettings2.cpp"
    text = read(path)
    end_audio = "\taudio_panel->SetSizerAndFit(audio_panel_sizer);\n\treturn audio_panel;\n}"
    if '_("Enhanced Sound Experience")' not in text:
        block = """\t{\n\t\tauto box = new wxStaticBox(audio_panel, wxID_ANY, _(\"Enhanced Sound\"));\n\t\tauto box_sizer = new wxStaticBoxSizer(box, wxVERTICAL);\n\t\tm_enhanced_sound_experience = new wxCheckBox(box, wxID_ANY, _(\"Enhanced Sound Experience\"));\n\t\tm_enhanced_sound_experience->SetToolTip(_(\"Enable additive sound routes supplied by active graphic packs. Native TV and Wii U GamePad audio remain authoritative.\"));\n\t\tbox_sizer->Add(m_enhanced_sound_experience, 0, wxALL, 5);\n\t\taudio_panel_sizer->Add(box_sizer, 0, wxEXPAND | wxALL, 5);\n\t}\n\n"""
        text = replace_once(text, end_audio, block + end_audio, "GeneralSettings2 audio checkbox")
    store_anchor = "\tconfig.pad_volume = m_pad_volume->GetValue();\n"
    if "config.enhanced_sound_experience =" not in text:
        text = replace_once(text, store_anchor, store_anchor + "\tconfig.enhanced_sound_experience = m_enhanced_sound_experience->GetValue();\n", "GeneralSettings2 store checkbox")
    apply_anchor = "\tSendSliderEvent(m_pad_volume, config.pad_volume);\n"
    if "m_enhanced_sound_experience->SetValue" not in text:
        text = replace_once(text, apply_anchor, "\tm_enhanced_sound_experience->SetValue(config.enhanced_sound_experience);\n" + apply_anchor, "GeneralSettings2 apply checkbox")
    write(path, text)


def write_router() -> None:
    write("src/Cafe/OS/common/EnhancedSoundRouter.h", r'''#pragma once

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <mutex>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace EnhancedSoundRouter
{
	enum class Mode : uint8_t
	{
		AddDRC = 1,
	};

	struct RouteRule
	{
		std::string sourcePattern;
		std::string trackPattern;
		Mode mode{ Mode::AddDRC };
		uint16_t gain{ 0x6000 };
	};

	struct RouteMatch
	{
		Mode mode{ Mode::AddDRC };
		uint16_t gain{ 0x6000 };
	};

	struct RouteTable
	{
		std::string owner;
		std::vector<RouteRule> rules;
	};

	inline std::mutex s_mutex;
	inline std::vector<RouteTable> s_tables;

	inline std::string Normalize(std::string_view value)
	{
		std::string out(value);
		std::transform(out.begin(), out.end(), out.begin(), [](unsigned char c) {
			if (c == '\\')
				return '/';
			return static_cast<char>(std::tolower(c));
		});
		return out;
	}

	inline bool GlobMatch(std::string_view patternValue, std::string_view textValue)
	{
		const std::string pattern = Normalize(patternValue);
		const std::string text = Normalize(textValue);
		size_t p = 0, t = 0, star = std::string::npos, retry = 0;
		while (t < text.size())
		{
			if (p < pattern.size() && pattern[p] == text[t])
			{
				++p;
				++t;
			}
			else if (p < pattern.size() && pattern[p] == '*')
			{
				star = p++;
				retry = t;
			}
			else if (star != std::string::npos)
			{
				p = star + 1;
				t = ++retry;
			}
			else
			{
				return false;
			}
		}
		while (p < pattern.size() && pattern[p] == '*')
			++p;
		return p == pattern.size();
	}

	inline std::string_view BaseName(std::string_view path)
	{
		const auto pos = path.find_last_of("/\\");
		return pos == std::string_view::npos ? path : path.substr(pos + 1);
	}

	inline bool MatchSource(std::string_view pattern, std::string_view sourcePath)
	{
		if (pattern.empty())
			return true;
		const bool hasPath = pattern.find('/') != std::string_view::npos || pattern.find('\\') != std::string_view::npos;
		return GlobMatch(pattern, hasPath ? sourcePath : BaseName(sourcePath));
	}

	inline bool MatchTrack(std::string_view pattern, std::string_view trackName)
	{
		if (pattern.empty())
			return true;
		if (trackName.empty())
			return false;
		return GlobMatch(pattern, trackName);
	}

	inline void RegisterRouteTable(std::string owner, std::vector<RouteRule> rules)
	{
		std::scoped_lock lock(s_mutex);
		s_tables.erase(std::remove_if(s_tables.begin(), s_tables.end(), [&](const RouteTable& table) {
			return table.owner == owner;
		}), s_tables.end());
		if (!rules.empty())
			s_tables.push_back({ std::move(owner), std::move(rules) });
	}

	inline void UnregisterRouteTable(std::string_view owner)
	{
		std::scoped_lock lock(s_mutex);
		s_tables.erase(std::remove_if(s_tables.begin(), s_tables.end(), [&](const RouteTable& table) {
			return table.owner == owner;
		}), s_tables.end());
	}

	inline std::optional<RouteMatch> Resolve(std::string_view sourcePath, std::string_view trackName)
	{
		std::scoped_lock lock(s_mutex);
		for (auto table = s_tables.rbegin(); table != s_tables.rend(); ++table)
		{
			for (const auto& rule : table->rules)
			{
				if (!MatchSource(rule.sourcePattern, sourcePath) || !MatchTrack(rule.trackPattern, trackName))
					continue;
				return RouteMatch{ rule.mode, rule.gain };
			}
		}
		return std::nullopt;
	}
}
''')


def patch_graphic_pack() -> None:
    path = "src/Cafe/GraphicPack/GraphicPack2.h"
    text = read(path)
    anchor = "\tvoid LoadReplacedFiles();\n"
    if "LoadEnhancedSoundRoutes" not in text:
        text = replace_once(text, anchor, anchor + "\tvoid LoadEnhancedSoundRoutes();\n", "GraphicPack2 route loader declaration")
    write(path, text)

    path = "src/Cafe/GraphicPack/GraphicPack2.cpp"
    text = read(path)
    include_anchor = '#include "Cafe/GraphicPack/GraphicPack2.h"\n'
    if "EnhancedSoundRouter.h" not in text:
        text = replace_once(text, include_anchor, include_anchor + '#include "Cafe/OS/common/EnhancedSoundRouter.h"\n', "GraphicPack2 router include")

    activate_anchor = "bool GraphicPack2::Activate()\n{\n"
    if "void GraphicPack2::LoadEnhancedSoundRoutes()" not in text:
        loader = r'''void GraphicPack2::LoadEnhancedSoundRoutes()
{
	const std::string owner = GetNormalizedPathString();
	EnhancedSoundRouter::UnregisterRouteTable(owner);

	fs::path routesPath = GetRulesPath();
	routesPath.replace_filename("sound_routes.ini");
	std::unique_ptr<FileStream> fsRoutes(FileStream::openFile2(routesPath));
	if (!fsRoutes)
		return;

	std::vector<uint8> routeData;
	fsRoutes->extract(routeData);
	IniParser routes(routeData, _pathToUtf8(routesPath));
	std::vector<EnhancedSoundRouter::RouteRule> routeRules;

	while (routes.NextSection())
	{
		const auto section = routes.GetCurrentSectionName();
		if (!boost::istarts_with(section, "Route"))
			continue;

		EnhancedSoundRouter::RouteRule rule;
		if (const auto source = routes.FindOption("source"))
			rule.sourcePattern = *source;
		if (const auto track = routes.FindOption("track"))
			rule.trackPattern = *track;

		const auto mode = routes.FindOption("mode");
		if (!mode || !boost::iequals(*mode, "add_drc"))
		{
			cemuLog_log(LogType::Force, "Graphic pack \"{}\": sound_routes.ini section \"{}\" skipped because Stage A mode must be add_drc", owner, section);
			continue;
		}

		if (const auto gain = routes.FindOption("gain"))
		{
			try
			{
				const auto parsed = std::stoul(std::string(*gain), nullptr, 0);
				if (parsed > 0xFFFFu)
					throw std::out_of_range("gain");
				rule.gain = static_cast<uint16_t>(parsed);
			}
			catch (const std::exception&)
			{
				cemuLog_log(LogType::Force, "Graphic pack \"{}\": sound_routes.ini section \"{}\" skipped because gain is invalid", owner, section);
				continue;
			}
		}

		if (rule.sourcePattern.empty() && rule.trackPattern.empty())
		{
			cemuLog_log(LogType::Force, "Graphic pack \"{}\": sound_routes.ini section \"{}\" skipped because source/track are both empty", owner, section);
			continue;
		}
		routeRules.emplace_back(std::move(rule));
	}

	EnhancedSoundRouter::RegisterRouteTable(owner, std::move(routeRules));
}

'''
        text = replace_once(text, activate_anchor, loader + activate_anchor, "GraphicPack2 route loader")

    activation_point = "\t// load replaced files\n\tLoadReplacedFiles();\n"
    if "\tLoadEnhancedSoundRoutes();\n" not in text:
        text = replace_once(text, activation_point, activation_point + "\n\t// Enhanced Sound policy is data owned by the active graphic pack.\n\tLoadEnhancedSoundRoutes();\n", "GraphicPack2 route activation")

    deactivate_anchor = "bool GraphicPack2::Deactivate()\n{\n\tif (!m_activated)\n\t\treturn false;\n\n"
    if "EnhancedSoundRouter::UnregisterRouteTable(GetNormalizedPathString())" not in text:
        text = replace_once(text, deactivate_anchor, deactivate_anchor + "\tEnhancedSoundRouter::UnregisterRouteTable(GetNormalizedPathString());\n\n", "GraphicPack2 route deactivation")
    write(path, text)


def write_source_tracker() -> None:
    write("src/Cafe/OS/common/EnhancedSoundSourceTracker.h", r'''#pragma once

// Stage A adapter around the physically validated BARS/FWAV correlation path.
// Route policy remains game-agnostic and lives in active graphic-pack data.
#include "Cafe/OS/common/BotWSoundSourceTracer.h"
#include "Cafe/OS/common/BotWSoundFingerprintCatalog.h"
#include "Cafe/OS/common/BotWSoundSourceTracerV3Support.h"

#include <optional>
#include <string>

namespace EnhancedSoundSourceTracker
{
	using SourceMatch = BotWSoundSourceTracer::SourceMatch;

	inline void RegisterFileOpen(uint32 fileHandle, const char* path)
	{
		BotWSoundSourceTracer::RegisterFileOpen(fileHandle, path);
	}

	inline void RegisterFileClose(uint32 fileHandle)
	{
		BotWSoundSourceTracer::RegisterFileClose(fileHandle);
	}

	inline void RegisterRead(uint32 fileHandle, uint32 destination, uint32 size)
	{
		BotWSoundSourceTracer::RegisterRead(fileHandle, destination, size);
	}

	inline void RegisterReadCompleted(uint32 fileHandle, uint32 destination, uint32 size)
	{
		if (destination == 0 || size == 0)
			return;

		std::string path;
		{
			std::scoped_lock lock(BotWSoundSourceTracer::s_mutex);
			auto it = BotWSoundSourceTracer::s_openSoundFiles.find(fileHandle);
			if (it == BotWSoundSourceTracer::s_openSoundFiles.end())
				return;
			path = it->second;
		}

		if (BotWSoundSourceTracer::ToLower(path).ends_with(".bars"))
			BotWSoundSourceTracerV3Support::RegisterBarsReadCompleted(path, destination, size);
	}

	inline std::optional<SourceMatch> ResolveSource(uint32 sampleBase)
	{
		if (sampleBase == 0)
			return std::nullopt;

		std::optional<SourceMatch> source;
		{
			std::scoped_lock lock(BotWSoundSourceTracer::s_mutex);
			source = BotWSoundSourceTracer::FindSourceLocked(sampleBase);
		}

		if (source && source->trackName.empty())
		{
			const auto fingerprint = BotWSoundSourceTracerV3Support::FindMatchForPath(sampleBase, source->path);
			if (fingerprint)
			{
				source->start = fingerprint->sourceStart;
				source->size = fingerprint->sourceSize;
				source->offset = fingerprint->dataOffset;
				source->path = fingerprint->path;
				source->trackName = fingerprint->trackName;
			}
		}

		if (!source)
		{
			const auto fingerprint = BotWSoundFingerprintCatalog::FindMatch(sampleBase);
			if (fingerprint)
			{
				SourceMatch match;
				match.start = fingerprint->sourceStart;
				match.size = fingerprint->sourceSize;
				match.offset = fingerprint->dataOffset;
				match.path = fingerprint->path;
				match.trackName = fingerprint->trackName;
				source = std::move(match);
			}
		}
		return source;
	}
}
''')


def write_dualsense_service() -> None:
    write("src/Cafe/OS/common/EnhancedSoundDualSenseService.h", r'''#pragma once

#ifdef _WIN32

#include "config/CemuConfig.h"
#include "GCore/Interfaces/IPlatformHardware.h"
#include "GCore/Templates/TBasicDeviceRegistry.h"
#include "GCore/Types/Structs/Context/DeviceContext.h"
#include "Platform/windows/windows_hardware_policy.h"

#include <chrono>
#include <cstdint>
#include <memory>
#include <mutex>
#include <thread>

namespace EnhancedSoundDualSenseService
{
	struct RegistryPolicy
	{
		using EngineIdType = uint32_t;
		struct Hasher
		{
			size_t operator()(const EngineIdType& id) const { return std::hash<EngineIdType>{}(id); }
		};
		static EngineIdType AllocEngineDevice()
		{
			static EngineIdType nextId = 0;
			return nextId++;
		}
		static void DisconnectDevice(EngineIdType) {}
		static void DispatchNewGamepad(EngineIdType) {}
	};

	class Registry : public GamepadCore::TBasicDeviceRegistry<RegistryPolicy>
	{
	public:
		using TBasicDeviceRegistry<RegistryPolicy>::TBasicDeviceRegistry;
		using TBasicDeviceRegistry<RegistryPolicy>::GetLibrary;
	};

	inline std::mutex s_startMutex;
	inline std::unique_ptr<std::jthread> s_worker;

	inline bool IsEligibleUsbDualSense(IGamepadBase* gamepad)
	{
		if (!gamepad || !gamepad->IsConnected())
			return false;
		auto* ctx = gamepad->GetMutableDeviceContext();
		if (!ctx || ctx->ConnectionType != EDSDeviceConnection::Usb)
			return false;
		return ctx->DeviceType == EDSDeviceType::DualSense || ctx->DeviceType == EDSDeviceType::DualSenseEdge;
	}

	inline bool InitializeSpeakerRoute(IGamepadBase* gamepad)
	{
		if (!IsEligibleUsbDualSense(gamepad))
			return false;
		auto* settings = gamepad->GetIGamepadSettings();
		if (!settings)
			return false;

		// Exact command from the physically PASSed native USB speaker-route test.
		// Test-only rumble/trigger clears are intentionally not carried into Cemu.
		settings->DualSenseSettings(
			0,   // mic state
			0,   // headset disabled
			1,   // internal speaker enabled
			0,   // mic volume
			180, // audio volume
			255, // native DualSense output mode
			0,   // rumble reduction
			0);  // trigger reduction
		gamepad->UpdateOutput();
		return true;
	}

	inline void Worker(std::stop_token stopToken)
	{
		try
		{
			IPlatformHardware::SetInstance(std::make_unique<windows_platform::windows_hardware>());
			Registry registry;
			registry.RequestImmediateDetection();
			bool initializedForConnection = false;

			while (!stopToken.stop_requested())
			{
				registry.PlugAndPlay(0.1f);
				auto* gamepad = registry.GetLibrary(0);
				const bool eligible = IsEligibleUsbDualSense(gamepad);

				if (!GetConfig().enhanced_sound_experience)
				{
					initializedForConnection = false;
				}
				else if (eligible)
				{
					gamepad->UpdateInput(0.1f);
					if (!initializedForConnection)
						initializedForConnection = InitializeSpeakerRoute(gamepad);
				}
				else
				{
					initializedForConnection = false;
					registry.RequestImmediateDetection();
				}
				std::this_thread::sleep_for(std::chrono::milliseconds(100));
			}
		}
		catch (...)
		{
			// Enhanced Sound is optional and must never make Cemu fatal.
		}
	}

	inline void EnsureRunning()
	{
		std::scoped_lock lock(s_startMutex);
		if (!s_worker)
			s_worker = std::make_unique<std::jthread>(Worker);
	}
}

#else
namespace EnhancedSoundDualSenseService
{
	inline void EnsureRunning() {}
}
#endif
''')


def patch_fs() -> None:
    path = "src/Cafe/OS/libs/coreinit/coreinit_FS.cpp"
    text = read(path)
    include_anchor = '#include "Cafe/OS/libs/coreinit/coreinit_FS.h"\n'
    if "EnhancedSoundSourceTracker.h" not in text:
        text = replace_once(text, include_anchor, include_anchor + '#include "Cafe/OS/common/EnhancedSoundSourceTracker.h"\n#include "config/CemuConfig.h"\n', "FS enhanced sound includes")

    open_anchor = "\t\t\t*fsCmdBlockBody->returnValues.cmdOpenFile.handlePtr = fsCmdBlockBody->fsaShimBuffer.response.cmdOpenFile.fileHandleOutput;\n\t\t\tbreak;"
    if "EnhancedSoundSourceTracker::RegisterFileOpen" not in text:
        replacement = "\t\t\t*fsCmdBlockBody->returnValues.cmdOpenFile.handlePtr = fsCmdBlockBody->fsaShimBuffer.response.cmdOpenFile.fileHandleOutput;\n\t\t\tif (GetConfig().enhanced_sound_experience)\n\t\t\t\tEnhancedSoundSourceTracker::RegisterFileOpen((uint32)fsCmdBlockBody->fsaShimBuffer.response.cmdOpenFile.fileHandleOutput, reinterpret_cast<const char*>(fsCmdBlockBody->fsaShimBuffer.request.cmdOpenFile.path));\n\t\t\tbreak;"
        text = replace_once(text, open_anchor, replacement, "FS enhanced sound open hook")

    read_anchor = "\t\tif (usePos)\n\t\t\tflag |= FSA_CMD_FLAG_SET_POS;\n\t\telse\n\t\t\tflag &= ~FSA_CMD_FLAG_SET_POS;"
    if "EnhancedSoundSourceTracker::RegisterRead(fileHandle" not in text:
        replacement = "\t\tif (GetConfig().enhanced_sound_experience)\n\t\t\tEnhancedSoundSourceTracker::RegisterRead(fileHandle, memory_getVirtualOffsetFromPointer(dest), static_cast<uint32>(transferSizeS64));\n\n" + read_anchor
        text = replace_once(text, read_anchor, replacement, "FS enhanced sound read hook")

    finish_anchor = "\t\tcase FSA_CMD_OPERATION_TYPE::READ:\n\t\tcase FSA_CMD_OPERATION_TYPE::WRITE:"
    if "EnhancedSoundSourceTracker::RegisterReadCompleted" not in text:
        replacement = r'''		case FSA_CMD_OPERATION_TYPE::READ:
		{
			if (GetConfig().enhanced_sound_experience && static_cast<sint32>(result) >= 0)
			{
				const auto& enhancedRead = fsCmdBlockBody->fsaShimBuffer.request.cmdReadFile;
				const uint64 enhancedSize64 = static_cast<uint64>((uint32)enhancedRead.size) * static_cast<uint64>((uint32)enhancedRead.count);
				if (enhancedSize64 <= 0xFFFFFFFFull)
					EnhancedSoundSourceTracker::RegisterReadCompleted((uint32)enhancedRead.fileHandle, enhancedRead.dest.GetMPTR(), static_cast<uint32>(enhancedSize64));
			}
			break;
		}
		case FSA_CMD_OPERATION_TYPE::WRITE:'''
        text = replace_once(text, finish_anchor, replacement, "FS enhanced sound read completion")

    close_anchor = "\tsint32 FSCloseFileAsync(FSClient_t* fsClient, FSCmdBlock_t* fsCmdBlock, uint32 fileHandle, uint32 errorMask, FSAsyncParams* fsAsyncParams)\n\t{\n\t\t_FSCmdIntro();"
    if "EnhancedSoundSourceTracker::RegisterFileClose" not in text:
        text = replace_once(text, close_anchor, close_anchor + "\n\t\tEnhancedSoundSourceTracker::RegisterFileClose(fileHandle);", "FS enhanced sound close hook")
    write(path, text)


def patch_ax() -> None:
    path = "src/Cafe/OS/libs/snd_core/ax_voice.cpp"
    text = read(path)
    include_anchor = '#include "Cafe/OS/libs/snd_core/ax_internal.h"\n'
    if "EnhancedSoundRouter.h" not in text:
        includes = '#include "Cafe/OS/common/EnhancedSoundRouter.h"\n#include "Cafe/OS/common/EnhancedSoundSourceTracker.h"\n#include "Cafe/OS/common/EnhancedSoundDualSenseService.h"\n#include "config/CemuConfig.h"\n'
        text = replace_once(text, include_anchor, include_anchor + includes, "AX enhanced sound includes")

    state_anchor = "\t\t\tAXSetSyncFlag(vpb, AX_SYNCFLAG_PLAYBACKSTATE);\n\t\t\tAXVoiceProtection_Acquire(vpb);\n\t\t\tif (voiceState == 0)"
    if "EnhancedSoundRouter::Resolve" not in text:
        hook = r'''			AXSetSyncFlag(vpb, AX_SYNCFLAG_PLAYBACKSTATE);
			AXVoiceProtection_Acquire(vpb);
			if (voiceState == 1 && GetConfig().enhanced_sound_experience)
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
							memcpy(enhancedDrcMix, internal->deviceMixDRC[0], sizeof(enhancedDrcMix));
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
			if (voiceState == 0)'''
        text = replace_once(text, state_anchor, hook, "AX additive enhanced sound routing")
    write(path, text)


def patch_cmake() -> None:
    path = "CMakeLists.txt"
    text = read(path)
    anchor = "add_subdirectory(\"dependencies/ih264d\" EXCLUDE_FROM_ALL)\n"
    if "CemuGamepadCoreWindowsSupport" not in text:
        block = r'''
if(WIN32)
	set(BUILD_TESTS OFF CACHE BOOL "Disable Gamepad-Core upstream tests in Cemu" FORCE)
	set(AUTOMATED_TESTS OFF CACHE BOOL "Disable Gamepad-Core automated tests in Cemu" FORCE)
	add_subdirectory("dependencies/Gamepad-Core" "${CMAKE_BINARY_DIR}/gamepad-core" EXCLUDE_FROM_ALL)
	add_library(CemuGamepadCoreWindowsSupport STATIC
		"dependencies/Gamepad-Core/Tests/Common/Platform/windows/windows_device_info.cpp"
	)
	target_include_directories(CemuGamepadCoreWindowsSupport PUBLIC
		"dependencies/Gamepad-Core/Source/Public"
		"dependencies/Gamepad-Core/Tests/Common"
	)
	target_compile_definitions(CemuGamepadCoreWindowsSupport PUBLIC
		BUILD_GAMEPAD_CORE_TESTS
		GAMEPAD_CORE_HAS_AUDIO=0
		UNICODE
		_UNICODE
	)
	target_link_libraries(CemuGamepadCoreWindowsSupport PUBLIC
		GamepadCore
		Setupapi
		Hid
		ole32
		oleaut32
		uuid
		winmm
	)
	set_property(TARGET CemuGamepadCoreWindowsSupport PROPERTY MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
endif()

'''
        text = replace_once(text, anchor, anchor + block, "root Gamepad-Core production integration")
    write(path, text)

    path = "src/Cafe/CMakeLists.txt"
    text = read(path)
    anchor = "if(WIN32)\n\ttarget_link_libraries(CemuCafe PRIVATE iphlpapi)\nendif()"
    if "CemuGamepadCoreWindowsSupport" not in text:
        text = replace_once(text, anchor, "if(WIN32)\n\ttarget_link_libraries(CemuCafe PRIVATE iphlpapi CemuGamepadCoreWindowsSupport)\nendif()", "CemuCafe Gamepad-Core link")
    write(path, text)


def write_botw_policy() -> None:
    base = "enhanced_sound_policies/BreathOfTheWild/EnhancedSoundExperience/"
    write(base + "rules.txt", r'''[Definition]
titleIds = 00050000101C9300,00050000101C9400,00050000101C9500
name = Enhanced Sound Experience
path = "The Legend of Zelda: Breath of the Wild/Enhancements/Enhanced Sound Experience"
description = "Adds selected player-local sounds to Wii U GamePad output without removing native TV or DRC audio."
version = 8
default = true
''')
    write(base + "sound_routes.ini", r'''[Route.PlayerVoice]
source = PlayerVoice.bars
track = *
mode = add_drc
gain = 0x6000

[Route.BowDraw]
track = Bow_Draw*
mode = add_drc
gain = 0x6000

[Route.BowRelease]
track = Bow_Release*
mode = add_drc
gain = 0x6000

[Route.SpearSwing]
track = Spear_Swing*
mode = add_drc
gain = 0x6000

[Route.LongSwordSwing]
track = LSword_Swing*
mode = add_drc
gain = 0x6000

[Route.SwordSwing]
track = Sword_Swing*
mode = add_drc
gain = 0x6000

[Route.LongSwordCharging]
track = LSword_AttackCharging*
mode = add_drc
gain = 0x6000

[Route.LongSwordDownSwingStart]
track = LSword_DownSwingAttackStart
mode = add_drc
gain = 0x6000

[Route.LongSwordDownSwingEnd]
track = LSword_DownSwingAttackEnd
mode = add_drc
gain = 0x6000
''')


def main() -> None:
    patch_config()
    patch_ui()
    write_router()
    patch_graphic_pack()
    write_source_tracker()
    write_dualsense_service()
    patch_fs()
    patch_ax()
    patch_cmake()
    write_botw_policy()
    print("Enhanced Sound Experience Stage A router architecture applied")


if __name__ == "__main__":
    main()
