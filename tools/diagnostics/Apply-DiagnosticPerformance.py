from pathlib import Path

base = Path(__file__).with_name("Apply-DiagnosticPerformanceBase.py")
extra = Path(__file__).with_name("Apply-ARM64CompareReuse.py")
root_cause = Path(__file__).with_name("Apply-ARM64JitRootCause.py")
rname_ldp = Path(__file__).with_name("Apply-ARM64RNameLdp.py")
cyclecheck_reuse = Path(__file__).with_name("Apply-ARM64CycleCheckReuse.py")
exec(compile(base.read_text(encoding="utf-8"), str(base), "exec"))
exec(compile(extra.read_text(encoding="utf-8"), str(extra), "exec"))
exec(compile(root_cause.read_text(encoding="utf-8"), str(root_cause), "exec"))
exec(compile(rname_ldp.read_text(encoding="utf-8"), str(rname_ldp), "exec"))
exec(compile(cyclecheck_reuse.read_text(encoding="utf-8"), str(cyclecheck_reuse), "exec"))
