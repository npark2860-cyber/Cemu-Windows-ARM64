from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "src/Cafe/OS/libs/coreinit/coreinit_FS.cpp"

text = PATH.read_text(encoding="utf-8-sig")

replacements = [
    (
        "\t\t\tif (GetConfig().enhanced_sound_experience)\n"
        "\t\t\t\tEnhancedSoundSourceTracker::RegisterFileOpen((uint32)fsCmdBlockBody->fsaShimBuffer.response.cmdOpenFile.fileHandleOutput, reinterpret_cast<const char*>(fsCmdBlockBody->fsaShimBuffer.request.cmdOpenFile.path));",
        "\t\t\tEnhancedSoundSourceTracker::RegisterFileOpen((uint32)fsCmdBlockBody->fsaShimBuffer.response.cmdOpenFile.fileHandleOutput, reinterpret_cast<const char*>(fsCmdBlockBody->fsaShimBuffer.request.cmdOpenFile.path));",
        "open hook",
    ),
    (
        "\t\t\tif (GetConfig().enhanced_sound_experience && static_cast<sint32>(result) >= 0)",
        "\t\t\tif (static_cast<sint32>(result) >= 0)",
        "read-complete hook",
    ),
    (
        "\t\tif (GetConfig().enhanced_sound_experience)\n"
        "\t\t\tEnhancedSoundSourceTracker::RegisterRead(fileHandle, memory_getVirtualOffsetFromPointer(dest), static_cast<uint32>(transferSizeS64));",
        "\t\tEnhancedSoundSourceTracker::RegisterRead(fileHandle, memory_getVirtualOffsetFromPointer(dest), static_cast<uint32>(transferSizeS64));",
        "read-start hook",
    ),
]

for old, new, label in replacements:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one source anchor, found {count}")
    text = text.replace(old, new, 1)

PATH.write_text(text, encoding="utf-8")
print("Enabled Enhanced Sound source collection for diagnostic build only")
