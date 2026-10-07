from pathlib import Path
import json
import re

lab = Path(__file__).resolve().parent.parent
source = lab / "evidence/cemu-npu-v2-game-20260929-105954.log"
lines = source.read_text(encoding="utf-8-sig").splitlines()
selected = [s for s in lines if "10:58:22.000" <= s[1:13] <= "10:59:09.999"]
perf = [s for s in selected if "[NPU-PERF] ON eligible=true" in s]
prof = [s for s in selected if "[NPU-PROFILE]" in s]
def get(s, name):
    return float(re.search(rf"\b{re.escape(name)}=([\d.]+)", s)[1])
def span(name):
    values = [get(s, name) for s in perf]
    return {"min": min(values), "max": max(values), "mean_of_intervals": sum(values)/len(values)}
runs = sum(get(s,"runs") for s in prof)
samples = sum(get(s,"pre_samples") for s in prof)
result = {
    "source_log": source.name,
    "selection": "10:58:22.000 through 10:59:09.999, second fullscreen segment; not a controlled identical-scene A/B",
    "intervals": len(perf),
    "real_present_fps": span("real_present_fps"),
    "accepted_present_fps": span("accepted_present_fps"),
    "npu_runs": int(runs),
    "npu_run_weighted_ms": sum(get(s,"NPU_Run_avg_ms")*get(s,"runs") for s in prof)/runs,
    "motion_gpu_weighted_ms": sum(get(s,"motion_avg_ms")*get(s,"pre_samples") for s in prof)/samples,
    "worker_input_wait_ms_per_completed_prepass_approx": sum(get(s,"input_fence_wait_sum_ms") for s in prof)/samples,
    "stale": int(sum(get(s,"stale") for s in perf)),
    "no_slot": int(sum(get(s,"no_slot") for s in perf)),
    "user_observed_npu_utilization_percent": [70,80],
    "limitations": "Run wall time and OS utilization are different measurements; no NPU saturation/headroom conclusion. Existing real-GPU spans include idle/dependencies. Input waits overlap main-thread work. v2 lacks isolated overlay/present-throttle timings.",
}
(lab / "evidence/cemu-npu-v2-game-summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(result,ensure_ascii=False,indent=2))
