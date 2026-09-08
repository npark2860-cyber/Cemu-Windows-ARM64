from pathlib import Path


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected 1 anchor, found {count}")
    return text.replace(old, new, 1)


# Extend the in-memory breadcrumb with compact descriptor/FBO/synchronization
# facts. These are populated only when IncidentContextEnabled() is already true.
header_path = Path("src/diagnostics/RuntimeDiagnostics.h")
header = header_path.read_text(encoding="utf-8")
header = replace_once(
    header,
    '''    uint64_t geometryDescriptor{};
    uint32_t commandBufferSlot{};
''',
    '''    uint64_t geometryDescriptor{};
    uint64_t flushIndex{};
    uint32_t descriptorTextures{};
    uint32_t descriptorUniformBuffers{};
    uint32_t descriptorStorageBuffers{};
    uint32_t descriptorViews{};
    uint32_t descriptorFboCandidates{};
    uint32_t fboWidth{};
    uint32_t fboHeight{};
    uint32_t fboColorCount{};
    uint32_t fboHasDepth{};
    uint32_t feedbackAspect{};
    uint32_t primitiveMode{};
    uint32_t commandBufferSlot{};
''',
    "incident detail fields",
)
header_path.write_text(header, encoding="utf-8", newline="\n")

core_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp")
core = core_path.read_text(encoding="utf-8")
core = replace_once(
    core,
    '''\t\tb.vertexDescriptor = vertexDS ? vertexDS->stateHash : 0;
\t\tb.pixelDescriptor = pixelDS ? pixelDS->stateHash : 0;
\t\tb.geometryDescriptor = geometryDS ? geometryDS->stateHash : 0;
\t\tb.indexCount = count;
''',
    '''\t\tb.vertexDescriptor = vertexDS ? vertexDS->stateHash : 0;
\t\tb.pixelDescriptor = pixelDS ? pixelDS->stateHash : 0;
\t\tb.geometryDescriptor = geometryDS ? geometryDS->stateHash : 0;
\t\tb.flushIndex = m_state.currentFlushIndex;
\t\tb.feedbackAspect = (uint32_t)m_state.feedbackLoopImageAspect;
\t\tb.primitiveMode = pipeline_info ? (uint32_t)pipeline_info->primitiveMode : 0;
\t\tauto addDescriptorFacts = [&b](VkDescriptorSetInfo* ds)
\t\t{
\t\t\tif (!ds) return;
\t\t\tb.descriptorTextures += ds->statsNumSamplerTextures;
\t\t\tb.descriptorUniformBuffers += ds->statsNumDynUniformBuffers;
\t\t\tb.descriptorStorageBuffers += ds->statsNumStorageBuffers;
\t\t\tb.descriptorViews += (uint32_t)ds->list_referencedViews.size();
\t\t\tb.descriptorFboCandidates += (uint32_t)ds->list_fboCandidates.size();
\t\t};
\t\taddDescriptorFacts(vertexDS);
\t\taddDescriptorFacts(pixelDS);
\t\taddDescriptorFacts(geometryDS);
\t\tif (m_state.activeFBO)
\t\t{
\t\t\tconst auto extent = m_state.activeFBO->GetExtend();
\t\t\tb.fboWidth = extent.width;
\t\t\tb.fboHeight = extent.height;
\t\t\tb.fboColorCount = m_state.activeFBO->calculateNumColorBuffers();
\t\t\tb.fboHasDepth = m_state.activeFBO->hasDepthBuffer() ? 1u : 0u;
\t\t}
\t\tb.indexCount = count;
''',
    "incident descriptor/FBO capture",
)
core_path.write_text(core, encoding="utf-8", newline="\n")

renderer_path = Path("src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp")
renderer = renderer_path.read_text(encoding="utf-8")
renderer = replace_once(
    renderer,
    '''\t\t\t"[ADRENO_DRAW] age={} seq={} frame={} draw={} cmd={} pipe={:016x} fbo={:016x} vs={:016x}_{:016x} ps={:016x}_{:016x} gs={:016x}_{:016x} vds={:016x} pds={:016x} gds={:016x} indices={} instances={}",
\t\t\tage, b.seq, b.frame, b.draw, b.commandBufferSlot, b.pipeline, b.fbo,
\t\t\tb.vsBase, b.vsAux, b.psBase, b.psAux, b.gsBase, b.gsAux,
\t\t\tb.vertexDescriptor, b.pixelDescriptor, b.geometryDescriptor, b.indexCount, b.instanceCount);
''',
    '''\t\t\t"[ADRENO_DRAW] age={} seq={} frame={} draw={} cmd={} pipe={:016x} fbo={:016x} fboSize={}x{} colors={} depth={} prim={} flush={} feedback=0x{:x} vsId=VS-{:08x} vs={:016x}_{:016x} psId=PS-{:08x} ps={:016x}_{:016x} gsId=GS-{:08x} gs={:016x}_{:016x} vds={:016x} pds={:016x} gds={:016x} descTex={} descUBO={} descSSBO={} descViews={} descFboCandidates={} indices={} instances={}",
\t\t\tage, b.seq, b.frame, b.draw, b.commandBufferSlot, b.pipeline, b.fbo,
\t\t\tb.fboWidth, b.fboHeight, b.fboColorCount, b.fboHasDepth, b.primitiveMode, b.flushIndex, b.feedbackAspect,
\t\t\t(uint32_t)b.vsBase, b.vsBase, b.vsAux, (uint32_t)b.psBase, b.psBase, b.psAux, (uint32_t)b.gsBase, b.gsBase, b.gsAux,
\t\t\tb.vertexDescriptor, b.pixelDescriptor, b.geometryDescriptor,
\t\t\tb.descriptorTextures, b.descriptorUniformBuffers, b.descriptorStorageBuffers, b.descriptorViews, b.descriptorFboCandidates,
\t\t\tb.indexCount, b.instanceCount);
''',
    "incident detail log format",
)
renderer_path.write_text(renderer, encoding="utf-8", newline="\n")

print("[adreno-incident-details] descriptor/FBO/sync/short-shader-ID context installed")
