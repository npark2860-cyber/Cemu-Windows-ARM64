from pathlib import Path


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


def replace_count(text, old, new, expected, label):
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected} anchors, found {count}")
    return text.replace(old, new)


# Explicit utility include for std::move/std::pair used by the final incident
# layer. Keep dependencies self-contained rather than relying on transitive STL
# includes from the precompiled header.
header_path = Path("src/diagnostics/RuntimeDiagnostics.h")
header = header_path.read_text(encoding="utf-8")
if "#include <utility>\n" not in header:
    header = replace_once(
        header,
        "#include <unordered_map>\n",
        "#include <unordered_map>\n#include <utility>\n",
        "diagnostic utility include",
    )
header_path.write_text(header, encoding="utf-8", newline="\n")


# GLSL/glslang failures happen before the final cache-store block. Compute the
# stable precompiled-cache key only when incident diagnostics are active, then
# attach it to every shader-phase incident. OFF therefore does not add this
# work to ordinary shader compilation.
shader_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/RendererShaderVk.cpp")
shader = shader_path.read_text(encoding="utf-8")
compile_anchor = '''\tconst bool compileWithDebugInfo = ((VulkanRenderer*)g_renderer.get())->IsTracingToolEnabled();
'''
compile_new = compile_anchor + '''\tuint64 diagnosticIncidentCacheH1 = 0;
\tuint64 diagnosticIncidentCacheH2 = 0;
\tif (RuntimeDiagnostics::IncidentContextEnabled() && m_isGameShader && !m_isGfxPackShader)
\t\tGenerateShaderPrecompiledCacheFilename(m_type, m_baseHash, m_auxHash, diagnosticIncidentCacheH1, diagnosticIncidentCacheH2);
'''
shader = replace_once(shader, compile_anchor, compile_new, "early shader incident cache key")

for reason in ("glsl_preprocess_failure", "glsl_parse_failure", "spirv_empty_output"):
    shader = replace_once(
        shader,
        f'VulkanRenderer::GetInstance()->LogDiagnosticIncidentContext("{reason}");',
        f'VulkanRenderer::GetInstance()->LogDiagnosticIncidentContext("{reason}", m_baseHash, m_auxHash, this, "fresh_compile", diagnosticIncidentCacheH1, diagnosticIncidentCacheH2, isRenderThread);',
        f"{reason} shader subject",
    )
shader = replace_count(
    shader,
    'VulkanRenderer::GetInstance()->LogDiagnosticIncidentContext("glsl_link_or_mapio_failure");',
    'VulkanRenderer::GetInstance()->LogDiagnosticIncidentContext("glsl_link_or_mapio_failure", m_baseHash, m_auxHash, this, "fresh_compile", diagnosticIncidentCacheH1, diagnosticIncidentCacheH2, isRenderThread);',
    2,
    "link/mapIO shader subjects",
)
shader_path.write_text(shader, encoding="utf-8", newline="\n")


# Resource paths should be canonical Wii U virtual paths when possible. Do the
# translation only while diagnostics are ON; OFF does not add path work.
fsa_path = Path("src/Cafe/IOSU/fsa/iosu_fsa.cpp")
fsa = fsa_path.read_text(encoding="utf-8")
fsa = replace_once(
    fsa,
    '''\t\t\tif (RuntimeDiagnostics::IncidentContextEnabled())
\t\t\t\tRuntimeDiagnostics::RecordResourceOpen((uint32)*fileHandle, path);
''',
    '''\t\t\tif (RuntimeDiagnostics::IncidentContextEnabled())
\t\t\t{
\t\t\t\tconst std::string diagVirtualPath = __FSATranslatePath(client, path);
\t\t\t\tRuntimeDiagnostics::RecordResourceOpen((uint32)*fileHandle, diagVirtualPath);
\t\t\t}
''',
    "canonical resource path",
)
fsa_path.write_text(fsa, encoding="utf-8", newline="\n")


# Keep the in-memory history deep, but make each incident compact enough to be
# readable. Users can still enable the dedicated heavy per-event diagnostics if
# they need the full stream.
renderer_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp")
renderer = renderer_path.read_text(encoding="utf-8")
renderer = replace_once(
    renderer,
    '''\tRuntimeDiagnostics::ForEachRecentResourceBreadcrumb([&](const RuntimeDiagnostics::ResourceBreadcrumb& b, size_t age)
\t{
\t\tconst double ageMs = nowNs >= b.timestampNs ? (double)(nowNs - b.timestampNs) / 1000000.0 : 0.0;
''',
    '''\tRuntimeDiagnostics::ForEachRecentResourceBreadcrumb([&](const RuntimeDiagnostics::ResourceBreadcrumb& b, size_t age)
\t{
\t\tif (age >= 12)
\t\t\treturn;
\t\tconst double ageMs = nowNs >= b.timestampNs ? (double)(nowNs - b.timestampNs) / 1000000.0 : 0.0;
''',
    "compact resource incident output",
)
renderer = replace_once(
    renderer,
    '''\tRuntimeDiagnostics::ForEachRecentImageLayoutBreadcrumb([&](const RuntimeDiagnostics::ImageLayoutBreadcrumb& b, size_t age)
\t{
\t\tconst double ageMs = nowNs >= b.timestampNs ? (double)(nowNs - b.timestampNs) / 1000000.0 : 0.0;
''',
    '''\tRuntimeDiagnostics::ForEachRecentImageLayoutBreadcrumb([&](const RuntimeDiagnostics::ImageLayoutBreadcrumb& b, size_t age)
\t{
\t\tif (age >= 24)
\t\t\treturn;
\t\tconst double ageMs = nowNs >= b.timestampNs ? (double)(nowNs - b.timestampNs) / 1000000.0 : 0.0;
''',
    "compact layout incident output",
)
renderer = replace_once(
    renderer,
    '''\tRuntimeDiagnostics::ForEachRecentDrawBreadcrumb([&](const RuntimeDiagnostics::DrawBreadcrumb& b, size_t age)
\t{
\t\tcemuLog_log(LogType::Force,
''',
    '''\tRuntimeDiagnostics::ForEachRecentDrawBreadcrumb([&](const RuntimeDiagnostics::DrawBreadcrumb& b, size_t age)
\t{
\t\tif (age >= 24)
\t\t\treturn;
\t\tcemuLog_log(LogType::Force,
''',
    "compact draw incident output",
)

# The subject replacements in the previous pass must have landed. Fail here
# instead of silently producing dedupe collisions for queue/fence errors.
if 'LogDiagnosticIncidentContext(result == VK_ERROR_DEVICE_LOST ? "queue_submit_device_lost" : "queue_submit_error");' in renderer:
    raise RuntimeError("queue-submit incident subject was not installed")
if 'LogDiagnosticIncidentContext(fenceStatus == VK_ERROR_DEVICE_LOST ? "fence_device_lost" : "fence_error");' in renderer:
    raise RuntimeError("fence incident subject was not installed")

renderer_path.write_text(renderer, encoding="utf-8", newline="\n")
print("[adreno-final-polish] all shader phases carry provenance; incident output bounded to recent context")
