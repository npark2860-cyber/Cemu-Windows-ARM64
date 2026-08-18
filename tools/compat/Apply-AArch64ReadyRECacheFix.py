from pathlib import Path

path = Path("src/Cafe/HW/Espresso/Recompiler/BackendAArch64/BackendAArch64.cpp")
text = path.read_text(encoding="utf-8")

if "const size_t codeSize = aarch64GenContext.getSize();" in text and "aarch64GenContext.setSize(codeSize);" in text:
    print("[aarch64-readyre] already applied")
    raise SystemExit(0)

old_start = "\n\tif (!aarch64GenContext.processAllJumps())\n"
new_start = "\n\tconst size_t codeSize = aarch64GenContext.getSize();\n\tif (!aarch64GenContext.processAllJumps())\n"
if old_start not in text:
    raise RuntimeError("AArch64 processAllJumps anchor not found")
text = text.replace(old_start, new_start, 1)

old_end = "\t\treturn false;\n\t}\n\n\taarch64GenContext.readyRE();"
new_end = "\t\treturn false;\n\t}\n\taarch64GenContext.setSize(codeSize);\n\n\taarch64GenContext.readyRE();"
if old_end not in text:
    raise RuntimeError("AArch64 readyRE anchor not found")
text = text.replace(old_end, new_end, 1)

path.write_text(text, encoding="utf-8", newline="\n")
print("[aarch64-readyre] applied upstream functional fix from Cemu PR #2027")
