#pragma once

#include "Cafe/CafeSystem.h"
#include "Cafe/HW/MMU/MMU.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>

namespace BotwBowAdaptiveTrigger
{
	struct BowProfile
	{
		std::string_view actorId;
		uint8_t baseAttack;
	};

	struct TriggerProfile
	{
		std::string actorId;
		uint8_t baseAttack{};
		uint8_t tensionPercent{};
		uint8_t hardwareStrength{};
		uint8_t startZoneMask{};
		uint8_t forcePair{};
	};

	inline constexpr std::array<BowProfile, 26> kBowProfiles{{
		{"Weapon_Bow_001", 5},
		{"Weapon_Bow_002", 14},
		{"Weapon_Bow_003", 12},
		{"Weapon_Bow_004", 4},
		{"Weapon_Bow_006", 14},
		{"Weapon_Bow_009", 10},
		{"Weapon_Bow_011", 25},
		{"Weapon_Bow_013", 15},
		{"Weapon_Bow_014", 15},
		{"Weapon_Bow_015", 14},
		{"Weapon_Bow_016", 9},
		{"Weapon_Bow_017", 20},
		{"Weapon_Bow_023", 44},
		{"Weapon_Bow_026", 20},
		{"Weapon_Bow_027", 24},
		{"Weapon_Bow_028", 28},
		{"Weapon_Bow_029", 10},
		{"Weapon_Bow_030", 36},
		{"Weapon_Bow_032", 32},
		{"Weapon_Bow_033", 50},
		{"Weapon_Bow_035", 26},
		{"Weapon_Bow_036", 38},
		{"Weapon_Bow_038", 4},
		{"Weapon_Bow_040", 14},
		{"Weapon_Bow_071", 100},
		{"Weapon_Bow_072", 30},
	}};

	inline bool IsSupportedBotwV208()
	{
		const uint64 titleId = CafeSystem::GetForegroundTitleId();
		const bool isBotw =
			titleId == 0x00050000101C9300ULL ||
			titleId == 0x00050000101C9400ULL ||
			titleId == 0x00050000101C9500ULL;
		return isBotw && CafeSystem::GetForegroundTitleVersion() == 208;
	}

	inline bool IsPlausibleGuestPointer(uint32_t address)
	{
		return address >= 0x10000000u && address < 0xA0000000u;
	}

	inline std::optional<std::string> ReadEquippedBowActorId()
	{
		if (!IsSupportedBotwV208())
			return std::nullopt;

		constexpr uint32_t kPauseMenuDataMgrInstancePtr = 0x10469978u;
		constexpr uint32_t kItemListHead = 0x4Cu;
		constexpr uint32_t kItemListFirst = 0x50u;
		constexpr uint32_t kItemListNodeOffset = 0x58u;
		constexpr uint32_t kItemType = 0x08u;
		constexpr uint32_t kItemEquipped = 0x14u;
		constexpr uint32_t kItemName = 0x18u;
		constexpr uint32_t kBowPouchType = 1u;
		constexpr uint32_t kMaxItemsWalked = 2048u;

		const uint32_t manager = memory_readU32(kPauseMenuDataMgrInstancePtr);
		if (!IsPlausibleGuestPointer(manager))
			return std::nullopt;

		const uint32_t nodeOffset = memory_readU32(manager + kItemListNodeOffset);
		if (nodeOffset > 0x1000u)
			return std::nullopt;

		if (manager + kItemListHead < nodeOffset)
			return std::nullopt;
		const uint32_t sentinel = manager + kItemListHead - nodeOffset;

		const uint32_t firstLink = memory_readU32(manager + kItemListFirst);
		if (firstLink < nodeOffset)
			return std::nullopt;
		uint32_t node = firstLink - nodeOffset;

		for (uint32_t walked = 0; walked < kMaxItemsWalked && node != sentinel; ++walked)
		{
			if (!IsPlausibleGuestPointer(node))
				break;

			if (memory_readU8(node + kItemEquipped) != 0 &&
				memory_readU32(node + kItemType) == kBowPouchType)
			{
				const uint32_t textPtr = memory_readU32(node + kItemName);
				if (!IsPlausibleGuestPointer(textPtr))
					return std::nullopt;

				std::string actorId;
				actorId.reserve(32);
				for (uint32_t i = 0; i < 63; ++i)
				{
					const uint8_t c = memory_readU8(textPtr + i);
					if (c == 0)
						break;
					if (c < 0x20 || c > 0x7E)
						return std::nullopt;
					actorId.push_back(static_cast<char>(c));
				}
				if (actorId.rfind("Weapon_Bow_", 0) == 0)
					return actorId;
				return std::nullopt;
			}

			const uint32_t nextLinkAddress = node + nodeOffset + 4u;
			if (!IsPlausibleGuestPointer(nextLinkAddress))
				break;
			const uint32_t nextLink = memory_readU32(nextLinkAddress);
			if (nextLink < nodeOffset)
				break;
			node = nextLink - nodeOffset;
		}

		return std::nullopt;
	}

	inline std::optional<uint8_t> FindBaseAttack(std::string_view actorId)
	{
		for (const auto& profile : kBowProfiles)
		{
			if (profile.actorId == actorId)
				return profile.baseAttack;
		}
		return std::nullopt;
	}

	inline std::optional<TriggerProfile> ResolveEquippedBow(
		uint8_t minTensionPercent = 40, uint8_t maxTensionPercent = 85, uint8_t startZone = 2)
	{
		const auto actorId = ReadEquippedBowActorId();
		if (!actorId)
			return std::nullopt;
		const auto baseAttack = FindBaseAttack(*actorId);
		if (!baseAttack)
			return std::nullopt;

		const float normalized = std::clamp(
			(static_cast<float>(*baseAttack) - 4.0f) / (50.0f - 4.0f), 0.0f, 1.0f);
		const float tension = static_cast<float>(minTensionPercent) +
			normalized * static_cast<float>(maxTensionPercent - minTensionPercent);
		const uint8_t tensionPercent = static_cast<uint8_t>(std::clamp(
			static_cast<int>(std::lround(tension)), 0, 100));

		const uint8_t hardwareStrength = static_cast<uint8_t>(std::clamp(
			static_cast<int>(std::lround((static_cast<float>(tensionPercent) / 100.0f) * 8.0f)), 1, 8));
		const uint8_t encodedForce = static_cast<uint8_t>(hardwareStrength - 1u);
		const uint8_t forcePair = static_cast<uint8_t>(encodedForce | (encodedForce << 3));
		const uint8_t safeStartZone = std::min<uint8_t>(startZone, 7u);
		const uint8_t startZoneMask = static_cast<uint8_t>(1u << safeStartZone);

		return TriggerProfile{
			*actorId,
			*baseAttack,
			tensionPercent,
			hardwareStrength,
			startZoneMask,
			forcePair,
		};
	}
}
