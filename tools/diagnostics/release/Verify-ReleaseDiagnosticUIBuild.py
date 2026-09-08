from pathlib import Path
import argparse
import hashlib

ROOT = Path(__file__).resolve().parents[3]
MAIN_REL = Path("src/gui/wxgui/MainWindow.cpp")
CMAKE_REL = Path("src/gui/wxgui/CMakeLists.txt")
SENTINEL = "CEMU_ARM64_DIAGNOSTICS_UI_SENTINEL_20260908"
REQUIRED = (
    "ARM64 Diagnostics",
    "Adreno Triage",
    "Disable all",
    SENTINEL,
)


def fail(message: str):
    raise RuntimeError(message)


def verify_bytes(data: bytes, label: str):
    missing = [text for text in REQUIRED if text.encode("ascii") not in data]
    if missing:
        fail(f"{label}: missing diagnostics UI markers: {missing}")
    print(f"[release-diag-ui-verify] PASS {label}: {', '.join(REQUIRED)}")


def stamp_and_verify_source(stamp: bool):
    main = ROOT / MAIN_REL
    text = main.read_text(encoding="utf-8")

    if stamp and SENTINEL not in text:
        old = '''    {
#if defined(__aarch64__)
        cemuLog_log(LogType::Force, "[CEMU_DIAG] UI_OPEN Architecture=ARM64");
'''
        new = '''    {
        cemuLog_log(LogType::Force, "[CEMU_DIAG] UI_SENTINEL CEMU_ARM64_DIAGNOSTICS_UI_SENTINEL_20260908");
#if defined(__aarch64__)
        cemuLog_log(LogType::Force, "[CEMU_DIAG] UI_OPEN Architecture=ARM64");
'''
        count = text.count(old)
        if count != 1:
            fail(f"UI sentinel stamp anchor count changed: expected 1, found {count}")
        text = text.replace(old, new, 1)
        main.write_text(text, encoding="utf-8", newline="\n")
        print(f"[release-diag-ui-verify] stamped {SENTINEL} into unconditional UI-open path")

    text = main.read_text(encoding="utf-8")
    missing = [item for item in REQUIRED if item not in text]
    if missing:
        fail(f"{MAIN_REL}: missing diagnostics UI source markers: {missing}")

    cmake = (ROOT / CMAKE_REL).read_text(encoding="utf-8")
    if "MainWindow.cpp" not in cmake:
        fail(f"{CMAKE_REL}: MainWindow.cpp is not part of CemuWxGui")

    digest = hashlib.sha256(main.read_bytes()).hexdigest()
    print(f"[release-diag-ui-verify] PASS source sha256={digest}")
    return digest


def verify_object_tree(build_dir: Path):
    if not build_dir.is_absolute():
        build_dir = ROOT / build_dir
    candidates = []
    for path in build_dir.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        if "mainwindow" in name and (name.endswith(".obj") or name.endswith(".o")):
            candidates.append(path)

    if not candidates:
        fail(f"no MainWindow object found under {build_dir}")

    matched = []
    for path in candidates:
        data = path.read_bytes()
        if b"Open logging window" in data:
            matched.append((path, data))

    if not matched:
        fail(
            "MainWindow object candidates exist but none contain the known-good "
            f"'Open logging window' marker: {[str(p) for p in candidates]}"
        )

    failures = []
    for path, data in matched:
        missing = [text for text in REQUIRED if text.encode("ascii") not in data]
        if missing:
            failures.append(f"{path}: {missing}")
        else:
            print(f"[release-diag-ui-verify] PASS object {path}")

    if failures:
        fail("compiled MainWindow object lost diagnostics UI markers: " + "; ".join(failures))

    libraries = [
        p for p in build_dir.rglob("*")
        if p.is_file()
        and "cemuwxgui" in p.name.lower()
        and (p.suffix.lower() in (".lib", ".a"))
    ]
    if not libraries:
        fail(f"CemuWxGui static library not found under {build_dir}")

    library_ok = False
    library_failures = []
    for path in libraries:
        data = path.read_bytes()
        missing = [text for text in REQUIRED if text.encode("ascii") not in data]
        if missing:
            library_failures.append(f"{path}: {missing}")
        else:
            print(f"[release-diag-ui-verify] PASS library {path}")
            library_ok = True
    if not library_ok:
        fail("CemuWxGui library lost diagnostics UI markers: " + "; ".join(library_failures))


def verify_binary(path: Path):
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file():
        fail(f"binary not found: {path}")
    data = path.read_bytes()
    verify_bytes(data, f"binary {path}")

    for known in ("Open logging window", "Accurate barriers (Vulkan)", "CEMU_DIAG"):
        if known.encode("ascii") not in data:
            fail(f"binary {path}: known-good marker unexpectedly missing: {known}")
    print(f"[release-diag-ui-verify] PASS known-good binary controls {path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=("source", "object", "binary"))
    parser.add_argument("--stamp-source", action="store_true")
    parser.add_argument("--path")
    args = parser.parse_args()

    if args.stage == "source":
        stamp_and_verify_source(args.stamp_source)
    elif args.stage == "object":
        if not args.path:
            fail("--path build directory is required for object stage")
        verify_object_tree(Path(args.path))
    else:
        if not args.path:
            fail("--path executable is required for binary stage")
        verify_binary(Path(args.path))


if __name__ == "__main__":
    main()
