from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 anchor, found {count}")
    return text.replace(old, new, 1)


path = Path("src/Cafe/HW/Latte/Core/LatteRenderTarget.cpp")
text = path.read_text(encoding="utf-8")

text = replace_once(
    text,
    '''\tif (!Bayo2F544GuestRoundtripEnabled() || !mainTexture || mainTexture->physAddress != 0xF5442800u ||
\t\t!mainTexture->isDepth || mainTexture->format != Latte::E_GX2SURFFMT::D24_S8_UNORM ||
\t\tmainTexture->width != 1280 || mainTexture->height != 720 || mainTexture->pitch != 1280)
\t\treturn;

\tauto* mainInfo = mainTexture->sliceMipInfo + mainTexture->GetSliceMipArrayIndex(0, 0);
''',
    '''\tif (!Bayo2F544GuestRoundtripEnabled() || !mainTexture || mainTexture->physAddress != 0xF5442800u ||
\t\t!mainTexture->isDepth || mainTexture->format != Latte::E_GX2SURFFMT::D24_S8_UNORM ||
\t\tmainTexture->width != 1280 || mainTexture->height != 720 || mainTexture->pitch != 1280)
\t\treturn;

\tconst bool nativeEffectiveSize = !mainTexture->overwriteInfo.hasResolutionOverwrite ||
\t\t(mainTexture->overwriteInfo.width == mainTexture->width && mainTexture->overwriteInfo.height == mainTexture->height);
\tif (!nativeEffectiveSize)
\t{
\t\tstatic bool loggedResizeSkip = false;
\t\tif (!loggedResizeSkip)
\t\t{
\t\t\tloggedResizeSkip = true;
\t\t\tcemuLog_log(LogType::Force,
\t\t\t\t"[BAYO2_F544_ROUNDTRIP] phase=skip-resized guest={}x{} effective={}x{}",
\t\t\t\tmainTexture->width, mainTexture->height, mainTexture->overwriteInfo.width, mainTexture->overwriteInfo.height);
\t\t}
\t\treturn;
\t}

\tauto* mainInfo = mainTexture->sliceMipInfo + mainTexture->GetSliceMipArrayIndex(0, 0);
''',
    "native-size roundtrip gate",
)

text = replace_once(
    text,
    '''\tg_bayo2F544GuestRoundtripUpload = true;
\tLatteTexture_ReloadData(mainTexture);
\tg_bayo2F544GuestRoundtripUpload = false;
\tmainInfo->lastDynamicUpdate = newestEvent;
''',
    '''\tconst bool savedResolutionOverwrite = mainTexture->overwriteInfo.hasResolutionOverwrite;
\tif (savedResolutionOverwrite)
\t\tmainTexture->overwriteInfo.hasResolutionOverwrite = false; // safe only because effective size == guest size above
\tg_bayo2F544GuestRoundtripUpload = true;
\tLatteTexture_ReloadData(mainTexture);
\tg_bayo2F544GuestRoundtripUpload = false;
\tmainTexture->overwriteInfo.hasResolutionOverwrite = savedResolutionOverwrite;
\tmainInfo->lastDynamicUpdate = newestEvent;
''',
    "native-size reload guard",
)

path.write_text(text, encoding="utf-8", newline="\n")
print("Bayonetta 2 f544 native-size roundtrip guard applied")
