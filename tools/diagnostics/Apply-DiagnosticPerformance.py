from pathlib import Path

base = Path(__file__).with_name("Apply-DiagnosticPerformanceBase.py")
extra = Path(__file__).with_name("Apply-ARM64CompareReuse.py")
root_cause = Path(__file__).with_name("Apply-ARM64JitRootCause.py")
exec(compile(base.read_text(encoding="utf-8"), str(base), "exec"))
exec(compile(extra.read_text(encoding="utf-8"), str(extra), "exec"))
exec(compile(root_cause.read_text(encoding="utf-8"), str(root_cause), "exec"))
