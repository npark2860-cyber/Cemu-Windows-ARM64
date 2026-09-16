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
        block = """\t{\n\t\tauto box = new wxStaticBox(audio_panel, wxID_ANY, _(\"Enhanced Sound\"));\n\t\tauto box_sizer = new wxStaticBoxSizer(box, wxVERTICAL);\n\t\tm_enhanced_sound_experience = new wxCheckBox(box, wxID_ANY, _(\"Enhanced Sound Experience\"));\n\t\tm_enhanced_sound_experience->SetToolTip(_(\"Enable data-driven enhanced audio routing. Native Wii U GamePad audio remains authoritative and unchanged.\"));\n\t\tbox_sizer->Add(m_enhanced_sound_experience, 0, wxALL, 5);\n\t\taudio_panel_sizer->Add(box_sizer, 0, wxEXPAND | wxALL, 5);\n\t}\n\n"""
        text = replace_once(text, end_audio, block + end_audio, "GeneralSettings2 audio checkbox")
    store_anchor = "\tconfig.pad_volume = m_pad_volume->GetValue();\n"
    if "config.enhanced_sound_experience =" not in text:
        text = replace_once(text, store_anchor, store_anchor + "\tconfig.enhanced_sound_experience = m_enhanced_sound_experience->GetValue();\n", "GeneralSettings2 store checkbox")
    apply_anchor = "\tSendSliderEvent(m_pad_volume, config.pad_volume);\n"
    if "m_enhanced_sound_experience->SetValue" not in text:
        text = replace_once(text, apply_anchor, "\tm_enhanced_sound_experience->SetValue(config.enhanced_sound_experience);\n" + apply_anchor, "GeneralSettings2 apply checkbox")
    write(path, text)


def patch_graphic_pack() -> None:
    path = "src/Cafe/GraphicPack/GraphicPack2.h"
    text = read(path)
    public_anchor = "\tusing PresetPtr = std::shared_ptr<Preset>;\n"
    if "EnhancedSoundRoute" not in text:
        public_block = r'''

	enum class EnhancedSoundRoute : uint8
	{
		DuplicateToDRC = 1,
	};

	struct EnhancedSoundPolicy
	{
		EnhancedSoundRoute route = EnhancedSoundRoute::DuplicateToDRC;
		uint16 gain = 0x6000;
		std::string destination{ "drc" };
	};
'''
        text = replace_once(text, public_anchor, public_anchor + public_block, "GraphicPack2 enhanced sound public types")
    static_anchor = "\tstatic void Reset();\n"
    if "ResolveEnhancedSoundPolicy" not in text:
        text = replace_once(text, static_anchor, static_anchor + "\tstatic std::optional<EnhancedSoundPolicy> ResolveEnhancedSoundPolicy(std::string_view semantic, std::string_view sourcePath, std::string_view trackName);\n", "GraphicPack2 resolver declaration")
    private_anchor = "\tstd::vector<CustomShader> m_custom_shaders;\n"
    if "EnhancedSoundRule" not in text:
        private_block = r'''
	struct EnhancedSoundRule
	{
		std::string semantic;
		std::string source_prefix;
		std::string track;
		EnhancedSoundPolicy policy;
	};
	std::vector<EnhancedSoundRule> m_enhanced_sound_rules;
'''
        text = replace_once(text, private_anchor, private_block + private_anchor, "GraphicPack2 enhanced sound private rules")
    write(path, text)

    path = "src/Cafe/GraphicPack/GraphicPack2.cpp"
    text = read(path)
    section_anchor = "\t\telse if (boost::iequals(currentSectionName, \"RAM\"))\n"
    if "currentSectionName, \"EnhancedSound\"" not in text:
        section = r'''		else if (boost::iequals(currentSectionName, "EnhancedSound"))
		{
			EnhancedSoundRule rule;
			if (const auto semantic = rules.FindOption("semantic"))
				rule.semantic = *semantic;
			if (const auto sourcePrefix = rules.FindOption("sourcePrefix"))
				rule.source_prefix = *sourcePrefix;
			if (const auto track = rules.FindOption("track"))
				rule.track = *track;

			const auto route = rules.FindOption("route");
			if (!route || !(boost::iequals(*route, "duplicate_drc") || boost::iequals(*route, "duplicate_to_drc")))
			{
				cemuLog_log(LogType::Force, "Graphic pack \"{}\": [EnhancedSound] in line {} skipped because route must be duplicate_drc", GetNormalizedPathString(), rules.GetCurrentSectionLineNumber());
				continue;
			}

			if (const auto destination = rules.FindOption("destination"))
			{
				if (!boost::iequals(*destination, "drc"))
				{
					cemuLog_log(LogType::Force, "Graphic pack \"{}\": [EnhancedSound] in line {} skipped because Stage A only supports destination=drc", GetNormalizedPathString(), rules.GetCurrentSectionLineNumber());
					continue;
				}
				rule.policy.destination = *destination;
			}

			if (const auto gain = rules.FindOption("gain"))
			{
				try
				{
					const auto parsed = std::stoul(std::string(*gain), nullptr, 0);
					if (parsed > 0xFFFFu)
						throw std::out_of_range("gain");
					rule.policy.gain = static_cast<uint16>(parsed);
				}
				catch (const std::exception&)
				{
					cemuLog_log(LogType::Force, "Graphic pack \"{}\": [EnhancedSound] in line {} skipped because gain is invalid", GetNormalizedPathString(), rules.GetCurrentSectionLineNumber());
					continue;
				}
			}

			if (rule.semantic.empty() && rule.source_prefix.empty() && rule.track.empty())
			{
				cemuLog_log(LogType::Force, "Graphic pack \"{}\": [EnhancedSound] in line {} skipped because it has no identity selector", GetNormalizedPathString(), rules.GetCurrentSectionLineNumber());
				continue;
			}

			m_enhanced_sound_rules.emplace_back(std::move(rule));
		}
'''
        text = replace_once(text, section_anchor, section + section_anchor, "GraphicPack2 enhanced sound section parser")

    resolver_anchor = "void GraphicPack2::WaitUntilReady()\n{\n"
    if "GraphicPack2::ResolveEnhancedSoundPolicy" not in text:
        resolver = r'''std::optional<GraphicPack2::EnhancedSoundPolicy> GraphicPack2::ResolveEnhancedSoundPolicy(std::string_view semantic, std::string_view sourcePath, std::string_view trackName)
{
	if (!s_isReady.load())
		return std::nullopt;

	auto find_match = [&](int priority) -> std::optional<EnhancedSoundPolicy>
	{
		for (const auto& pack : s_active_graphic_packs)
		{
			for (const auto& rule : pack->m_enhanced_sound_rules)
			{
				bool matched = false;
				if (priority == 0 && !semantic.empty() && !rule.semantic.empty())
					matched = boost::iequals(semantic, rule.semantic);
				else if (priority == 1 && !sourcePath.empty() && !rule.source_prefix.empty())
					matched = boost::istarts_with(sourcePath, rule.source_prefix);
				else if (priority == 2 && !trackName.empty() && !rule.track.empty())
					matched = trackName == rule.track;

				if (matched)
					return rule.policy;
			}
		}
		return std::nullopt;
	};

	// Stable priority contract: semantic/category first, then path/prefix, exact track only as fallback.
	for (int priority = 0; priority < 3; ++priority)
	{
		if (auto policy = find_match(priority))
			return policy;
	}
	return std::nullopt;
}

'''
        text = replace_once(text, resolver_anchor, resolver + resolver_anchor, "GraphicPack2 enhanced sound resolver")
    write(path, text)


def write_source_tracker() -> None:
    path = "src/Cafe/OS/common/EnhancedSoundSourceTracker.h"
    content = r'''#pragma once

// Stage A production adapter around the physically validated BARS/fingerprint
// correlation path. The public API is game-agnostic; game-specific selection
// lives in GraphicPack2 [EnhancedSound] data rules.
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
'''
    write(path, content)


def write_dualsense_service() -> None:
    path = "src/Cafe/OS/common/EnhancedSoundDualSenseService.h"
    content = r'''#pragma once

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

		// Physically validated native speaker route initialization. Deliberately do
		// not clear or rewrite rumble/adaptive-trigger state here.
		settings->DualSenseSettings(
			0,   // mic state
			0,   // headset disabled
			1,   // internal speaker enabled
			0,   // mic volume
			180, // speaker/audio volume
			255, // preserve Gamepad-Core native DualSense output mode
			0,   // rumble reduction
			0);  // trigger reduction
		gamepad->UpdateOutput();
		return true;
	}

	inline void Worker(std::stop_token stopToken)
	{
		try
		{
			auto hardware = std::make_unique<windows_platform::windows_hardware>();
			IPlatformHardware::SetInstance(std::move(hardware));
			Registry registry;
			registry.RequestImmediateDetection();

			bool speakerInitializedForConnection = false;
			while (!stopToken.stop_requested())
			{
				registry.PlugAndPlay(0.1f);
				auto* gamepad = registry.GetLibrary(0);
				const bool eligible = IsEligibleUsbDualSense(gamepad);

				if (!GetConfig().enhanced_sound_experience)
				{
					speakerInitializedForConnection = false;
				}
				else if (eligible)
				{
					gamepad->UpdateInput(0.1f);
					if (!speakerInitializedForConnection)
						speakerInitializedForConnection = InitializeSpeakerRoute(gamepad);
				}
				else
				{
					// A disconnect arms the next physical connection for exactly one init.
					speakerInitializedForConnection = false;
					registry.RequestImmediateDetection();
				}

				std::this_thread::sleep_for(std::chrono::milliseconds(100));
			}
		}
		catch (...)
		{
			// Enhanced Sound must never make Cemu startup/runtime fatal if the native
			// controller helper cannot initialize on a particular machine.
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
'''
    write(path, content)


def patch_fs_and_ax() -> None:
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

    path = "src/Cafe/OS/libs/snd_core/ax_voice.cpp"
    text = read(path)
    include_anchor = '#include "Cafe/OS/libs/snd_core/ax_internal.h"\n'
    if "EnhancedSoundSourceTracker.h" not in text:
        includes = '#include "Cafe/OS/common/EnhancedSoundSourceTracker.h"\n#include "Cafe/OS/common/EnhancedSoundDualSenseService.h"\n#include "Cafe/GraphicPack/GraphicPack2.h"\n#include "config/CemuConfig.h"\n'
        text = replace_once(text, include_anchor, include_anchor + includes, "AX enhanced sound includes")

    state_anchor = "\t\t\tAXSetSyncFlag(vpb, AX_SYNCFLAG_PLAYBACKSTATE);\n\t\t\tAXVoiceProtection_Acquire(vpb);\n\t\t\tif (voiceState == 0)"
    if "ResolveEnhancedSoundPolicy" not in text:
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
						const auto policy = GraphicPack2::ResolveEnhancedSoundPolicy({}, source->path, source->trackName);
						if (policy && policy->route == GraphicPack2::EnhancedSoundRoute::DuplicateToDRC)
						{
							const bool drcAlreadyRouted =
								internal->deviceMixMaskDRC[0] != 0 || internal->deviceMixMaskDRC[1] != 0 ||
								internal->deviceMixMaskDRC[2] != 0 || internal->deviceMixMaskDRC[3] != 0;
							if (!drcAlreadyRouted)
							{
								AXCHMIX_DEPR enhancedDrcMix[AX_DRC_CHANNEL_COUNT * AX_BUS_COUNT] = {};
								enhancedDrcMix[0 * AX_BUS_COUNT + 0].vol = _swapEndianU16(policy->gain);
								enhancedDrcMix[1 * AX_BUS_COUNT + 0].vol = _swapEndianU16(policy->gain);
								AXSetVoiceDeviceMix(vpb, AX_DEV_DRC, 0, enhancedDrcMix);
							}
						}
					}
				}
			}
			if (voiceState == 0)'''
        text = replace_once(text, state_anchor, hook, "AX enhanced sound routing hook")
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
        replacement = "if(WIN32)\n\ttarget_link_libraries(CemuCafe PRIVATE iphlpapi CemuGamepadCoreWindowsSupport)\nendif()"
        text = replace_once(text, anchor, replacement, "CemuCafe Gamepad-Core link")
    write(path, text)


def write_botw_policy() -> None:
    path = "enhanced_sound_policies/BreathOfTheWild/EnhancedSoundExperience/rules.txt"
    content = r'''[Definition]
titleIds = 00050000101C9300,00050000101C9400,00050000101C9500
name = Enhanced Sound Experience
path = "The Legend of Zelda: Breath of the Wild/Enhancements/Enhanced Sound Experience"
description = "Stage A regression policy: duplicate only physically confirmed empty-air weapon swing cues to Wii U DRC output."
version = 8
default = true

[EnhancedSound]
track = Spear_Swing1
route = duplicate_drc

[EnhancedSound]
track = Spear_Swing2
route = duplicate_drc

[EnhancedSound]
track = Spear_SwingFast1
route = duplicate_drc

[EnhancedSound]
track = Spear_SwingFast2
route = duplicate_drc

[EnhancedSound]
track = LSword_Swing1
route = duplicate_drc

[EnhancedSound]
track = LSword_Swing3
route = duplicate_drc

[EnhancedSound]
track = LSword_Swing5
route = duplicate_drc
'''
    write(path, content)


def main() -> None:
    patch_config()
    patch_ui()
    patch_graphic_pack()
    write_source_tracker()
    write_dualsense_service()
    patch_fs_and_ax()
    patch_cmake()
    write_botw_policy()
    print("Enhanced Sound Experience Stage A source changes applied")


if __name__ == "__main__":
    main()
