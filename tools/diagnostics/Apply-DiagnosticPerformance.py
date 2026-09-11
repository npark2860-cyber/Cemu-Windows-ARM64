from pathlib import Path

base = Path(__file__).with_name("Apply-DiagnosticPerformanceBase.py")
extra = Path(__file__).with_name("Apply-ARM64CompareReuse.py")
exec(compile(base.read_text(encoding="utf-8"), str(base), "exec"))
exec(compile(extra.read_text(encoding="utf-8"), str(extra), "exec"))
