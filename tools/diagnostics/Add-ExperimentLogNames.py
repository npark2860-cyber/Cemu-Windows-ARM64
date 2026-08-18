from pathlib import Path


def read(path):
    return Path(path).read_text(encoding="utf-8")


def write(path, text):
    Path(path).write_text(text, encoding="utf-8", newline="\n")


path = "src/Cemu/Logging/CemuLogging.cpp"
s = read(path)

include_anchor = "#include <chrono>"
if s.count(include_anchor) != 1:
    raise RuntimeError(f"CemuLogging include anchor count={s.count(include_anchor)}")
s = s.replace(include_anchor, include_anchor + "\n#include <cstdlib>", 1)

old = '''fs::path cemuLog_GetLogFilePath()\n{\n    return ActiveSettings::GetUserDataPath("log.txt");\n}'''
new = '''fs::path cemuLog_GetLogFilePath()\n{\n    if (const char* experimentLog = std::getenv("CEMU_EXPERIMENT_LOG"); experimentLog && experimentLog[0] != '\\0')\n        return ActiveSettings::GetUserDataPath(std::string_view(experimentLog));\n    return ActiveSettings::GetUserDataPath("log.txt");\n}'''

if s.count(old) != 1:
    raise RuntimeError(f"cemuLog_GetLogFilePath anchor count={s.count(old)}")
s = s.replace(old, new, 1)

write(path, s)
print("Runtime experiment-specific log filenames installed")
