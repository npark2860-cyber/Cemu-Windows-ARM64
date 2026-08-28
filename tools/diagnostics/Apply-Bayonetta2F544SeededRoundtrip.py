from pathlib import Path


path = Path("src/Cafe/HW/Latte/Core/LatteRenderTarget.cpp")
text = path.read_text(encoding="utf-8")

signature = "static void Bayo2F544SyncBeforeMainBind(LatteTexture* mainTexture)"
start = text.find(signature)
if start < 0:
    raise RuntimeError("Bayo2F544SyncBeforeMainBind not found")
brace = text.find("{", start)
if brace < 0:
    raise RuntimeError("function opening brace not found")

depth = 0
end = None
for i in range(brace, len(text)):
    ch = text[i]
    if ch == "{":
        depth += 1
    elif ch == "}":
        depth -= 1
        if depth == 0:
            end = i + 1
            break
if end is None:
    raise RuntimeError("function closing brace not found")

replacement = r'''static void Bayo2F544SyncBeforeMainBind(LatteTexture* mainTexture)
{
	if (!Bayo2F544GuestRoundtripEnabled() || !mainTexture || mainTexture->physAddress != 0xF5442800u ||
		!mainTexture->isDepth || mainTexture->format != Latte::E_GX2SURFFMT::D24_S8_UNORM ||
		mainTexture->width != 1280 || mainTexture->height != 720 || mainTexture->pitch != 1280)
		return;

	sint32 effectiveWidth = 0;
	sint32 effectiveHeight = 0;
	mainTexture->GetEffectiveSize(effectiveWidth, effectiveHeight, 0);
	if (effectiveWidth != 1280 || effectiveHeight != 720)
	{
		static uint64 s_skipResized = 0;
		const uint64 n = ++s_skipResized;
		if (n <= 8 || (n % 1000) == 0)
			cemuLog_log(LogType::Force, "[BAYO2_F544_SEEDED] phase=skip-resized n={} guest=1280x720 effective={}x{}", n, effectiveWidth, effectiveHeight);
		return;
	}

	auto* mainInfo = mainTexture->sliceMipInfo + mainTexture->GetSliceMipArrayIndex(0, 0);
	std::vector<std::pair<uint64, LatteTexture*>> pending;
	std::vector<LatteTexture*> aliases;
	LatteTC_LookupTexturesByPhysAddr(mainTexture->physAddress, aliases);
	for (auto* alias : aliases)
	{
		if (!alias || alias == mainTexture || !alias->isDepth || alias->format != mainTexture->format ||
			alias->tileMode != mainTexture->tileMode || alias->swizzle != mainTexture->swizzle || !alias->baseView)
			continue;
		const bool expectedSmall =
			(alias->width == 256 && alias->height == 256 && alias->pitch == 256) ||
			(alias->width == 64 && alias->height == 64 && alias->pitch == 64);
		if (!expectedSmall)
			continue;
		auto* aliasInfo = alias->sliceMipInfo + alias->GetSliceMipArrayIndex(0, 0);
		if (aliasInfo->lastDynamicUpdate > mainInfo->lastDynamicUpdate)
			pending.emplace_back(aliasInfo->lastDynamicUpdate, alias);
	}
	if (pending.empty())
		return;

	std::sort(pending.begin(), pending.end(), [](const auto& a, const auto& b) { return a.first < b.first; });
	const uint64 newestEvent = pending.back().first;
	static uint64 s_seededCount = 0;
	const uint64 n = ++s_seededCount;
	cemuLog_log(LogType::Force, "[BAYO2_F544_SEEDED] phase=begin n={} mainEvent={} pending={} newestEvent={}",
		n, mainInfo->lastDynamicUpdate, pending.size(), newestEvent);

	// Preserve every byte represented by the current main host image first.
	// The previous invalid experiment skipped this step and therefore reloaded
	// untouched main regions from stale guest RAM.
	if (!Bayo2F544WriteAliasToGuest(mainTexture))
	{
		cemuLog_log(LogType::Force, "[BAYO2_F544_SEEDED] phase=abort-main-seed n={}", n);
		return;
	}
	cemuLog_log(LogType::Force, "[BAYO2_F544_SEEDED] phase=seed-main n={} event={} size=1280x720 pitch=1280",
		n, mainInfo->lastDynamicUpdate);

	// Overlay only aliases that are newer than the main representation, in GPU
	// write-event order. Each writer uses that alias' own GX2 pitch/tile mapping.
	for (const auto& item : pending)
	{
		if (!Bayo2F544WriteAliasToGuest(item.second))
		{
			cemuLog_log(LogType::Force, "[BAYO2_F544_SEEDED] phase=abort-overlay n={} event={} size={}x{} pitch={}",
				n, item.first, item.second->width, item.second->height, item.second->pitch);
			return;
		}
		cemuLog_log(LogType::Force, "[BAYO2_F544_SEEDED] phase=overlay n={} event={} size={}x{} pitch={}",
			n, item.first, item.second->width, item.second->height, item.second->pitch);
	}

	// Reload the main representation from the seeded + overlaid guest image.
	// If a same-size graphics rule exists, temporarily disable only the overwrite
	// flag because LatteTexture_ReloadData() otherwise clears overwritten targets.
	const bool hadResolutionOverwrite = mainTexture->overwriteInfo.hasResolutionOverwrite;
	mainTexture->overwriteInfo.hasResolutionOverwrite = false;
	g_bayo2F544GuestRoundtripUpload = true;
	LatteTexture_ReloadData(mainTexture);
	g_bayo2F544GuestRoundtripUpload = false;
	mainTexture->overwriteInfo.hasResolutionOverwrite = hadResolutionOverwrite;
	mainInfo->lastDynamicUpdate = newestEvent;
	cemuLog_log(LogType::Force, "[BAYO2_F544_SEEDED] phase=main-reload n={} syncedEvent={} effective={}x{}",
		n, newestEvent, effectiveWidth, effectiveHeight);
}'''

text = text[:start] + replacement + text[end:]

required = [
    "[BAYO2_F544_SEEDED] phase=seed-main",
    "[BAYO2_F544_SEEDED] phase=overlay",
    "[BAYO2_F544_SEEDED] phase=main-reload",
    "Bayo2F544WriteAliasToGuest(mainTexture)",
    "aliasInfo->lastDynamicUpdate > mainInfo->lastDynamicUpdate",
]
for marker in required:
    if marker not in text:
        raise RuntimeError(f"missing generated marker/guard: {marker}")

# Ensure the dangerous old implementation was actually replaced rather than duplicated.
if text.count(signature) != 1:
    raise RuntimeError(f"expected one sync function, found {text.count(signature)}")
if "[BAYO2_F544_ROUNDTRIP] phase=begin" in replacement or "[BAYO2_F544_ROUNDTRIP] phase=main-reload" in replacement:
    raise RuntimeError("old unseeded main roundtrip body survived replacement")

path.write_text(text, encoding="utf-8", newline="\n")
print("Bayonetta 2 f544 seeded guest-memory roundtrip applied")
