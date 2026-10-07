import collections
import json
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
tags = collections.Counter()
shader_results = collections.Counter()
critical = []
metadata = []
first = last = None
lines = 0
for lines, line in enumerate(path.open(encoding="utf-8", errors="replace"), 1):
    stamp = re.match(r"\[([0-9:.]+)\]", line)
    if stamp:
        first = first or stamp[1]
        last = stamp[1]
    match = re.match(r"\[[0-9:.]+\] \[([^]]+)\]", line)
    if match:
        tags[match[1]] += 1
    if "[SHADER_CREATE]" in line:
        result = re.search(r"result=(-?\d+)", line)
        shader_results[result[1] if result else "missing"] += 1
    if any(x in line for x in ("TitleId:", "CPU-Mode:", "Activate graphic pack:", "Init Cemu", "Strict shader mul:", "Full sync at GX2DrawDone:")):
        metadata.append(line.strip())
    if "[CEMU_DIAG]" not in line and re.search(r"\[(?:GLSL_FAIL|SPIRV_FAIL|PIPE_FAIL|PIPE_FAILURE|VK_ERROR|DEVICE_LOST)\]|Failed to create|Shader error|result=-\d+|out.of.bounds|suspicious|invalid shader|mismatch", line, re.I):
        if len(critical) < 60:
            critical.append({"line": lines, "text": line.strip()})

result = {"path": str(path.resolve()), "bytes": path.stat().st_size, "lines": lines,
          "time_range": [first, last], "metadata": metadata, "tags": dict(tags.most_common()),
          "shader_module_results": dict(shader_results), "critical_samples": critical}
out = path.with_suffix(".analysis.json")
out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
