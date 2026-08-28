from pathlib import Path


# Applied AFTER Apply-Bayonetta2F544GuestRoundtripExperiment.py.
# Keep that experiment's D24/S8 transfer implementation, but replace the
# dangerous cross-pitch main-bind function completely with a same-surface
# 64x64/pitch64 self-roundtrip validator.

rt_path = Path("src/Cafe/HW/Latte/Core/LatteRenderTarget.cpp")
rt = rt_path.read_text(encoding="utf-8")

signature = "static void Bayo2F544SyncBeforeMainBind(LatteTexture* mainTexture)\n{"
start = rt.find(signature)
if start < 0:
    raise RuntimeError("Bayo2F544SyncBeforeMainBind signature not found")
if rt.find(signature, start + 1) >= 0:
    raise RuntimeError("Bayo2F544SyncBeforeMainBind signature is not unique")

open_brace = rt.find("{", start)
if open_brace < 0:
    raise RuntimeError("Bayo2F544SyncBeforeMainBind opening brace not found")

depth = 0
end = None
i = open_brace
while i < len(rt):
    ch = rt[i]
    if ch == "{":
        depth += 1
    elif ch == "}":
        depth -= 1
        if depth == 0:
            end = i + 1
            break
    i += 1

if end is None:
    raise RuntimeError("Bayo2F544SyncBeforeMainBind matching closing brace not found")

replacement = r'''static void Bayo2F544SyncBeforeMainBind(LatteTexture* mainTexture)
{
	static bool s_bayo2F544D24SelfRoundtripDone = false;
	if (s_bayo2F544D24SelfRoundtripDone || !Bayo2F544GuestRoundtripEnabled() || !mainTexture ||
		mainTexture->physAddress != 0xF5442800u || !mainTexture->isDepth ||
		mainTexture->format != Latte::E_GX2SURFFMT::D24_S8_UNORM ||
		mainTexture->width != 1280 || mainTexture->height != 720 || mainTexture->pitch != 1280)
		return;

	LatteTexture* alias64 = nullptr;
	std::vector<LatteTexture*> aliases;
	LatteTC_LookupTexturesByPhysAddr(mainTexture->physAddress, aliases);
	for (auto* alias : aliases)
	{
		if (alias && alias != mainTexture && alias->isDepth &&
			alias->format == Latte::E_GX2SURFFMT::D24_S8_UNORM &&
			alias->width == 64 && alias->height == 64 && alias->pitch == 64 &&
			alias->baseView && alias->isUpdatedOnGPU)
		{
			alias64 = alias;
			break;
		}
	}
	if (!alias64)
		return;

	// Exactly one same-surface validation. No 256x256 data is touched and the
	// 1280x720 main depth is never reloaded or modified by this function.
	s_bayo2F544D24SelfRoundtripDone = true;
	std::vector<uint8> before(64u * 64u * 4u);
	std::vector<uint8> after(64u * 64u * 4u);

	if (!LatteTextureReadback_ReadbackToLinearBlocking(alias64->baseView, before.data(), 64, 64, 64))
	{
		cemuLog_log(LogType::Force, "[BAYO2_F544_D24_SELFTEST] result=read-before-failed");
		return;
	}

	LatteTextureDefinition def(alias64);
	LatteTextureLoader_writeReadbackTextureToMemory(&def, 0, 0, before.data());

	g_bayo2F544GuestRoundtripUpload = true;
	LatteTexture_ReloadData(alias64);
	g_bayo2F544GuestRoundtripUpload = false;

	if (!LatteTextureReadback_ReadbackToLinearBlocking(alias64->baseView, after.data(), 64, 64, 64))
	{
		cemuLog_log(LogType::Force, "[BAYO2_F544_D24_SELFTEST] result=read-after-failed");
		return;
	}

	uint32 mismatchPixels = 0;
	uint32 depthMismatchPixels = 0;
	uint32 stencilMismatchPixels = 0;
	uint32 firstMismatch = 0xFFFFFFFFu;
	uint32 beforeFirst = 0;
	uint32 afterFirst = 0;
	const uint32* before32 = reinterpret_cast<const uint32*>(before.data());
	const uint32* after32 = reinterpret_cast<const uint32*>(after.data());
	for (uint32 i = 0; i < 64u * 64u; i++)
	{
		if (before32[i] == after32[i])
			continue;
		mismatchPixels++;
		if ((before32[i] & 0x00FFFFFFu) != (after32[i] & 0x00FFFFFFu))
			depthMismatchPixels++;
		if ((before32[i] >> 24) != (after32[i] >> 24))
			stencilMismatchPixels++;
		if (firstMismatch == 0xFFFFFFFFu)
		{
			firstMismatch = i;
			beforeFirst = before32[i];
			afterFirst = after32[i];
		}
	}

	auto* info = alias64->sliceMipInfo + alias64->GetSliceMipArrayIndex(0, 0);
	cemuLog_log(LogType::Force,
		"[BAYO2_F544_D24_SELFTEST] result={} event={} pixels=4096 mismatch={} depthMismatch={} stencilMismatch={} first={} before=0x{:08x} after=0x{:08x}",
		mismatchPixels == 0 ? "exact" : "mismatch", info->lastDynamicUpdate,
		mismatchPixels, depthMismatchPixels, stencilMismatchPixels,
		firstMismatch, beforeFirst, afterFirst);
}'''

rt = rt[:start] + replacement + rt[end:]

# Validate the generated function itself, not just the full file.
check_start = rt.find(signature)
check_open = rt.find("{", check_start)
depth = 0
check_end = None
for i in range(check_open, len(rt)):
    if rt[i] == "{":
        depth += 1
    elif rt[i] == "}":
        depth -= 1
        if depth == 0:
            check_end = i + 1
            break
if check_end is None:
    raise RuntimeError("generated self-test function has unbalanced braces")
fn = rt[check_start:check_end]

required = [
    "[BAYO2_F544_D24_SELFTEST]",
    "alias->width == 64 && alias->height == 64 && alias->pitch == 64",
    "LatteTextureReadback_ReadbackToLinearBlocking(alias64->baseView, before.data(), 64, 64, 64)",
    "LatteTextureLoader_writeReadbackTextureToMemory(&def, 0, 0, before.data())",
    "LatteTexture_ReloadData(alias64)",
    "mismatchPixels == 0 ? \"exact\" : \"mismatch\"",
]
for item in required:
    if item not in fn:
        raise RuntimeError(f"self-test requirement missing: {item}")

for forbidden in [
    "std::vector<std::pair<uint64, LatteTexture*>> pending",
    "Bayo2F544WriteAliasToGuest(",
    "phase=alias-to-guest",
    "phase=main-reload",
    "LatteTexture_ReloadData(mainTexture)",
    "alias->width == 256",
]:
    if forbidden in fn:
        raise RuntimeError(f"cross-pitch behavior remains in generated self-test function: {forbidden}")

rt_path.write_text(rt, encoding="utf-8", newline="\n")
print("Bayonetta 2 f544 D24 same-surface self-roundtrip validation applied")
