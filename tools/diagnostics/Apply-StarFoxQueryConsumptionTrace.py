from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


# -----------------------------------------------------------------------------
# Star Fox Zero JP query-consumption comparison extension.
#
# Observation-only. The existing Bayo2/XCX QUERY_COMPARE instrumentation has
# already been applied when this script runs. Add only Star Fox Zero JP
# (00050000-101AFF00) to the same title gates so the exact same API/core markers
# can be compared without changing query behavior, values, readiness or order.
# -----------------------------------------------------------------------------
starfox_id = "0x00050000101AFF00ULL"

# GX2 API-side gate.
gx2_path = Path("src/Cafe/OS/libs/gx2/GX2_Query.cpp")
gx2 = gx2_path.read_text(encoding="utf-8")
old_gate = "\t\t\ttitleId == 0x0005000010116100ULL;   // XCX JP\n"
new_gate = (
    "\t\t\ttitleId == 0x0005000010116100ULL || // XCX JP\n"
    "\t\t\ttitleId == 0x00050000101AFF00ULL;   // Star Fox Zero JP\n"
)
gx2 = replace_once(gx2, old_gate, new_gate, "GX2 Star Fox query-compare title gate")
if starfox_id not in gx2 or "[QUERY_COMPARE]" not in gx2:
    raise RuntimeError("Star Fox GX2 query-consumption extension validation failed")
gx2_path.write_text(gx2, encoding="utf-8", newline="\n")

# Latte renderer-result-side gate.
core_path = Path("src/Cafe/HW/Latte/Core/LatteQuery.cpp")
core = core_path.read_text(encoding="utf-8")
old_core_gate = "\t\ttitleId == 0x0005000010116100ULL;\n"
new_core_gate = (
    "\t\ttitleId == 0x0005000010116100ULL ||\n"
    "\t\ttitleId == 0x00050000101AFF00ULL;\n"
)
core = replace_once(core, old_core_gate, new_core_gate, "Latte Star Fox query-compare title gate")
if starfox_id not in core or "[QUERY_COMPARE]" not in core:
    raise RuntimeError("Star Fox Latte query-consumption extension validation failed")
core_path.write_text(core, encoding="utf-8", newline="\n")

# Chain the focused, unsampled observation for recurring query 0x460f9fc8.
focus_path = Path("tools/diagnostics/Apply-StarFoxFocusedQueryTrace.py")
exec(compile(focus_path.read_text(encoding="utf-8"), str(focus_path), "exec"))

print("Star Fox Zero JP added to existing QUERY_COMPARE observation trace; behavior unchanged")
