from pathlib import Path

CATALOG = Path("src/Cafe/OS/common/BotWSoundFingerprintCatalog.h")

text = CATALOG.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    text = text.replace(old, new, 1)


# Parse AMTA using its real section offsets/version instead of assuming a fixed
# DATA -> MARK -> EXT_ -> STRG physical layout. This also reads the asset-name
# offset from DATA, so a STRG table containing more than one string is safe.
start = text.find("\tinline std::string ParseTrackName(")
end = text.find("\n\tinline uint32 CalculateRawChannelSize", start)
if start < 0 or end < 0:
    raise RuntimeError("ParseTrackName function bounds not found")

parse_track_name = r'''	inline std::string ParseTrackName(const uint8* base, uint32 archiveSize, bool barsBigEndian,
		uint32 count, uint32 index)
	{
		if (index >= count)
			return {};
		const uint32 pairsOffset = 16 + count * 4;
		const uint32 amtaOffset = ReadU32(base + pairsOffset + index * 8, barsBigEndian);
		if (amtaOffset > archiveSize || archiveSize - amtaOffset < 24)
			return {};

		const uint8* amta = base + amtaOffset;
		if (!HasMagic(amta, "AMTA"))
			return {};
		const bool amtaBigEndian = amta[4] == 0xFE;
		if (!amtaBigEndian && amta[4] != 0xFF)
			return {};

		const uint16 version = ReadU16(amta + 6, amtaBigEndian);
		const uint32 amtaSize = ReadU32(amta + 8, amtaBigEndian);
		if (amtaSize < 24 || amtaSize > archiveSize - amtaOffset)
			return {};

		uint32 strgOffsetField = 0;
		if (version == 0x0100)
			strgOffsetField = 0x14;
		else if (version == 0x0300 || version == 0x0400)
			strgOffsetField = 0x18;
		else
			return {};
		if (strgOffsetField + 4 > amtaSize)
			return {};

		const uint32 dataRel = ReadU32(amta + 0x0C, amtaBigEndian);
		const uint32 strgRel = ReadU32(amta + strgOffsetField, amtaBigEndian);
		auto withinAmta = [amtaSize](uint64 pos, uint64 length) {
			return pos <= amtaSize && length <= amtaSize - pos;
		};

		if (!withinAmta(dataRel, 12) || !HasMagic(amta + dataRel, "DATA"))
			return {};
		const uint32 dataBodySize = ReadU32(amta + dataRel + 4, amtaBigEndian);
		if (dataBodySize < 4 || !withinAmta(static_cast<uint64>(dataRel) + 8, dataBodySize))
			return {};
		const uint32 assetNameOffset = ReadU32(amta + dataRel + 8, amtaBigEndian);

		if (!withinAmta(strgRel, 8) || !HasMagic(amta + strgRel, "STRG"))
			return {};
		const uint32 stringBodySize = ReadU32(amta + strgRel + 4, amtaBigEndian);
		if (stringBodySize == 0 || !withinAmta(static_cast<uint64>(strgRel) + 8, stringBodySize) ||
			assetNameOffset >= stringBodySize)
			return {};

		const char* name = reinterpret_cast<const char*>(amta + strgRel + 8 + assetNameOffset);
		const uint32 maxLength = stringBodySize - assetNameOffset;
		uint32 length = 0;
		while (length < maxLength && name[length] != '\0')
			++length;
		if (length == 0 || length == maxLength)
			return {};
		return std::string(name, length);
	}
'''

text = text[:start] + parse_track_name + text[end:]

# Nintendo DSP ADPCM stores one predictor/scale byte per 14 samples and one
# nibble per sample. The previous +1 byte overestimated every stream.
replace_once(
    "\t\t\tconst uint64 size = static_cast<uint64>((numSamples + 13) / 14) +\n"
    "\t\t\t\tstatic_cast<uint64>((numSamples + 1) / 2) + 1ull;\n",
    "\t\t\tconst uint64 size = static_cast<uint64>((numSamples + 13) / 14) +\n"
    "\t\t\t\tstatic_cast<uint64>((numSamples + 1) / 2);\n",
    "DSP ADPCM raw-size calculation",
)

# A missing AMTA asset name must not discard the audio fingerprint. Source-only
# policies (for example source + track=*) can still make a safe routing decision.
replace_once(
    "\t\t\tconst std::string trackName = ParseTrackName(base, archiveSize, barsBigEndian, count, i);\n"
    "\t\t\tif (trackName.empty())\n"
    "\t\t\t\tcontinue;\n\n",
    "\t\t\tconst std::string trackName = ParseTrackName(base, archiveSize, barsBigEndian, count, i);\n\n",
    "preserve unnamed fingerprint entries",
)

CATALOG.write_text(text, encoding="utf-8")
print("Enhanced Sound fingerprint catalog v2 fix applied")
