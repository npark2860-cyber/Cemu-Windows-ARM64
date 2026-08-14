from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8", newline="\n")


def replace_exact(text: str, old: str, new: str, label: str, expected: int = 1) -> str:
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{label}: expected {expected} match(es), found {count}")
    return text.replace(old, new)


# 1) Restore the pre-#1443 renderer index interface.
path = "src/Cafe/HW/Latte/Renderer/Renderer.h"
text = read(path)
text = replace_exact(
    text,
    """\t// index
\tstruct IndexAllocation
\t{
\t\tvoid* mem; // pointer to index data inside buffer
\t\tvoid* rendererInternal; // for renderer use
\t};

\tvirtual IndexAllocation indexData_reserveIndexMemory(uint32 size) = 0;
\tvirtual void indexData_releaseIndexMemory(IndexAllocation& allocation) = 0;
\tvirtual void indexData_uploadIndexMemory(IndexAllocation& allocation) = 0;
""",
    """\t// index
\tvirtual void* indexData_reserveIndexMemory(uint32 size, uint32& offset, uint32& bufferIndex) = 0;
\tvirtual void indexData_uploadIndexMemory(uint32 offset, uint32 size) = 0;
""",
    "Renderer index interface",
)
write(path, text)

# 2) Keep the non-Vulkan renderer declarations compatible with the restored interface.
path = "src/Cafe/HW/Latte/Renderer/OpenGL/OpenGLRenderer.h"
text = read(path)
text = replace_exact(
    text,
    """\t// index (not used by OpenGL renderer yet)
\tIndexAllocation indexData_reserveIndexMemory(uint32 size) override
\t{
\t\tcemu_assert_unimplemented();
\t\treturn {};
\t}

\tvoid indexData_releaseIndexMemory(IndexAllocation& allocation) override
\t{
\t\tcemu_assert_unimplemented();
\t}

\tvoid indexData_uploadIndexMemory(IndexAllocation& allocation) override
\t{
\t\tcemu_assert_unimplemented();
\t}
""",
    """\t// index (not used by OpenGL renderer yet)
\tvoid* indexData_reserveIndexMemory(uint32 size, uint32& offset, uint32& bufferIndex) override
\t{
\t\tcemu_assert_unimplemented();
\t\treturn nullptr;
\t}

\tvoid indexData_uploadIndexMemory(uint32 offset, uint32 size) override
\t{
\t\tcemu_assert_unimplemented();
\t}
""",
    "OpenGL index interface",
)
write(path, text)

path = "src/Cafe/HW/Latte/Renderer/Metal/MetalRenderer.h"
text = read(path)
text = replace_exact(
    text,
    """\t// index
\tIndexAllocation indexData_reserveIndexMemory(uint32 size) override;
\tvoid indexData_releaseIndexMemory(IndexAllocation& allocation) override;
\tvoid indexData_uploadIndexMemory(IndexAllocation& allocation) override;
""",
    """\t// index
\tvoid* indexData_reserveIndexMemory(uint32 size, uint32& offset, uint32& bufferIndex) override;
\tvoid indexData_uploadIndexMemory(uint32 offset, uint32 size) override;
""",
    "Metal header index interface",
)
write(path, text)

# 3) Vulkan declaration and memory manager: use the existing ring allocator for indices.
path = "src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.h"
text = read(path)
text = replace_exact(
    text,
    """\tIndexAllocation indexData_reserveIndexMemory(uint32 size) override;
\tvoid indexData_releaseIndexMemory(IndexAllocation& allocation) override;
\tvoid indexData_uploadIndexMemory(IndexAllocation& allocation) override;
""",
    """\tvoid* indexData_reserveIndexMemory(uint32 size, uint32& offset, uint32& bufferIndex) override;
\tvoid indexData_uploadIndexMemory(uint32 offset, uint32 size) override;
""",
    "Vulkan header index interface",
)
write(path, text)

path = "src/Cafe/HW/Latte/Renderer/Vulkan/VKRMemoryManager.h"
text = read(path)
text = replace_exact(
    text,
    "m_indexBuffer(this, VKR_BUFFER_TYPE::INDEX, 4u * 1024 * 1024),",
    "m_indexBuffer(renderer, this, VKR_BUFFER_TYPE::INDEX, 4u * 1024 * 1024),",
    "Vulkan index allocator constructor",
)
text = replace_exact(
    text,
    "VKRSynchronizedHeapAllocator& GetIndexAllocator() { return m_indexBuffer; };",
    "VKRSynchronizedRingAllocator& GetIndexAllocator() { return m_indexBuffer; };",
    "Vulkan index allocator getter",
)
text = replace_exact(
    text,
    "VKRSynchronizedHeapAllocator m_indexBuffer;",
    "VKRSynchronizedRingAllocator m_indexBuffer;",
    "Vulkan index allocator member",
)
write(path, text)

# 4) Vulkan reserve/upload functions: return raw pointer + buffer offset/index like pre-#1443.
path = "src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp"
text = read(path)
text = replace_exact(
    text,
    """Renderer::IndexAllocation VulkanRenderer::indexData_reserveIndexMemory(uint32 size)
{
\tVKRSynchronizedHeapAllocator::AllocatorReservation* resv = memoryManager->GetIndexAllocator().AllocateBufferMemory(size, 32);
\treturn { resv->memPtr, resv };
}

void VulkanRenderer::indexData_releaseIndexMemory(IndexAllocation& allocation)
{
\tmemoryManager->GetIndexAllocator().FreeReservation((VKRSynchronizedHeapAllocator::AllocatorReservation*)allocation.rendererInternal);
}

void VulkanRenderer::indexData_uploadIndexMemory(IndexAllocation& allocation)
{
\tmemoryManager->GetIndexAllocator().FlushReservation((VKRSynchronizedHeapAllocator::AllocatorReservation*)allocation.rendererInternal);
}
""",
    """void* VulkanRenderer::indexData_reserveIndexMemory(uint32 size, uint32& offset, uint32& bufferIndex)
{
\tauto& indexAllocator = memoryManager->GetIndexAllocator();
\tauto resv = indexAllocator.AllocateBufferMemory(size, 32);
\toffset = resv.bufferOffset;
\tbufferIndex = resv.bufferIndex;
\treturn resv.memPtr;
}

void VulkanRenderer::indexData_uploadIndexMemory(uint32 offset, uint32 size)
{
\t// pre-#1443 index ring memory is HOST_COHERENT
}
""",
    "Vulkan index reserve/upload implementation",
)

old_draw_prep = """\tRenderer::IndexAllocation indexAllocation;
\tLatteIndices_decode(memory_getPointerFromVirtualOffset(indexDataMPTR), indexType, count, primitiveMode, indexMax, hostIndexType, hostIndexCount, indexAllocation);
\tVKRSynchronizedHeapAllocator::AllocatorReservation* indexReservation = (VKRSynchronizedHeapAllocator::AllocatorReservation*)indexAllocation.rendererInternal;
"""
new_draw_prep = """\tuint32 indexBufferOffset = 0;
\tuint32 indexBufferIndex = 0;
\tLatteIndices_decode(memory_getPointerFromVirtualOffset(indexDataMPTR), indexType, count, primitiveMode, indexMax, hostIndexType, hostIndexCount, indexBufferOffset, indexBufferIndex);
"""
draw_count = text.count(old_draw_prep)
if draw_count < 1:
    raise RuntimeError("Vulkan draw index prep: no matches found")
text = text.replace(old_draw_prep, new_draw_prep)

inside_decl = """\t\tuint32 indexBufferIndex = indexReservation->bufferIndex;
\t\tuint32 indexBufferOffset = indexReservation->bufferOffset;
"""
inside_count = text.count(inside_decl)
if inside_count != draw_count:
    raise RuntimeError(f"Vulkan draw inner declarations: expected {draw_count}, found {inside_count}")
text = text.replace(inside_decl, "")

old_bind = "vkCmdBindIndexBuffer(m_state.currentCommandBuffer, indexReservation->vkBuffer, indexBufferOffset, vkType);"
new_bind = "vkCmdBindIndexBuffer(m_state.currentCommandBuffer, memoryManager->GetIndexAllocator().GetBufferByIndex(indexBufferIndex), indexBufferOffset, vkType);"
bind_count = text.count(old_bind)
if bind_count != draw_count:
    raise RuntimeError(f"Vulkan index bind: expected {draw_count}, found {bind_count}")
text = text.replace(old_bind, new_bind)
write(path, text)

# 5) LatteIndices public signature: return offset/index rather than a renderer-owned allocation object.
path = "src/Cafe/HW/Latte/Core/LatteIndices.h"
text = read(path)
text = replace_exact(
    text,
    "void LatteIndices_decode(const void* indexData, LatteIndexType indexType, uint32 count, LattePrimitiveMode primitiveMode, uint32& indexMax, Renderer::INDEX_TYPE& renderIndexType, uint32& outputCount, Renderer::IndexAllocation& indexAllocation);",
    "void LatteIndices_decode(const void* indexData, LatteIndexType indexType, uint32 count, LattePrimitiveMode primitiveMode, uint32& indexMax, Renderer::INDEX_TYPE& renderIndexType, uint32& outputCount, uint32& indexBufferOffset, uint32& indexBufferIndex);",
    "LatteIndices header signature",
)
write(path, text)

# 6) LatteIndices cache/data flow: restore one cached offset/index and no explicit allocation release.
path = "src/Cafe/HW/Latte/Core/LatteIndices.cpp"
text = read(path)
old_cache = """struct
{
\tstruct CacheEntry
\t{
\t\t// input data
\t\tconst void* lastPtr;
\t\tuint32 lastCount;
\t\tLattePrimitiveMode lastPrimitiveMode;
\t\tLatteIndexType lastIndexType;
\t\tuint64 lastUsed;
\t\t// output
\t\tuint32 indexMax;
\t\tRenderer::INDEX_TYPE renderIndexType;
\t\tuint32 outputCount;
\t\tRenderer::IndexAllocation indexAllocation;
\t};
\tstd::array<CacheEntry, 8> entry;
\tuint64 currentUsageCounter{0};
}LatteIndexCache{};

void LatteIndices_invalidate(const void* memPtr, uint32 size)
{
\tfor(auto& entry : LatteIndexCache.entry)
\t{
\t\tif (entry.lastPtr >= memPtr && (entry.lastPtr < ((uint8*)memPtr + size)) )
\t\t{
\t\t\tif(entry.lastPtr != nullptr)
\t\t\t\tg_renderer->indexData_releaseIndexMemory(entry.indexAllocation);
\t\t\tentry.lastPtr = nullptr;
\t\t\tentry.lastCount = 0;
\t\t}
\t}
}

void LatteIndices_invalidateAll()
{
\tfor(auto& entry : LatteIndexCache.entry)
\t{
\t\tif (entry.lastPtr != nullptr)
\t\t\tg_renderer->indexData_releaseIndexMemory(entry.indexAllocation);
\t\tentry.lastPtr = nullptr;
\t\tentry.lastCount = 0;
\t}
}

uint64 LatteIndices_GetNextUsageIndex()
{
\treturn LatteIndexCache.currentUsageCounter++;
}
"""
new_cache = """struct
{
\tconst void* lastPtr;
\tuint32 lastCount;
\tLattePrimitiveMode lastPrimitiveMode;
\tLatteIndexType lastIndexType;
\t// output
\tuint32 indexMax;
\tRenderer::INDEX_TYPE renderIndexType;
\tuint32 outputCount;
\tuint32 indexBufferOffset;
\tuint32 indexBufferIndex;
}LatteIndexCache{};

void LatteIndices_invalidate(const void* memPtr, uint32 size)
{
\tif (LatteIndexCache.lastPtr >= memPtr && (LatteIndexCache.lastPtr < ((uint8*)memPtr + size)) )
\t{
\t\tLatteIndexCache.lastPtr = nullptr;
\t\tLatteIndexCache.lastCount = 0;
\t}
}

void LatteIndices_invalidateAll()
{
\tLatteIndexCache.lastPtr = nullptr;
\tLatteIndexCache.lastCount = 0;
}
"""
text = replace_exact(text, old_cache, new_cache, "Latte index cache")

text = replace_exact(
    text,
    "void LatteIndices_decode(const void* indexData, LatteIndexType indexType, uint32 count, LattePrimitiveMode primitiveMode, uint32& indexMax, Renderer::INDEX_TYPE& renderIndexType, uint32& outputCount, Renderer::IndexAllocation& indexAllocation)",
    "void LatteIndices_decode(const void* indexData, LatteIndexType indexType, uint32 count, LattePrimitiveMode primitiveMode, uint32& indexMax, Renderer::INDEX_TYPE& renderIndexType, uint32& outputCount, uint32& indexBufferOffset, uint32& indexBufferIndex)",
    "Latte index decode signature",
)

old_hit = """\t// reuse from cache if data didn't change
\tauto cacheEntry = std::find_if(LatteIndexCache.entry.begin(), LatteIndexCache.entry.end(), [indexData, count, primitiveMode, indexType](const auto& entry)
\t{
\t\treturn entry.lastPtr == indexData && entry.lastCount == count && entry.lastPrimitiveMode == primitiveMode && entry.lastIndexType == indexType;
\t});
\tif (cacheEntry != LatteIndexCache.entry.end())
\t{
\t\tindexMax = cacheEntry->indexMax;
\t\trenderIndexType = cacheEntry->renderIndexType;
\t\toutputCount = cacheEntry->outputCount;
\t\tindexAllocation = cacheEntry->indexAllocation;
\t\tcacheEntry->lastUsed = LatteIndices_GetNextUsageIndex();
\t\treturn;
\t}
"""
new_hit = """\t// reuse from cache if data didn't change
\tif (LatteIndexCache.lastPtr == indexData &&
\t\tLatteIndexCache.lastCount == count &&
\t\tLatteIndexCache.lastPrimitiveMode == primitiveMode &&
\t\tLatteIndexCache.lastIndexType == indexType)
\t{
\t\tindexMax = LatteIndexCache.indexMax;
\t\trenderIndexType = LatteIndexCache.renderIndexType;
\t\toutputCount = LatteIndexCache.outputCount;
\t\tindexBufferOffset = LatteIndexCache.indexBufferOffset;
\t\tindexBufferIndex = LatteIndexCache.indexBufferIndex;
\t\treturn;
\t}
"""
text = replace_exact(text, old_hit, new_hit, "Latte index cache hit path")

text = replace_exact(
    text,
    """\t\trenderIndexType = Renderer::INDEX_TYPE::NONE;
\t\tindexAllocation = {};
\t\treturn; // no indices
""",
    """\t\trenderIndexType = Renderer::INDEX_TYPE::NONE;
\t\treturn; // no indices
""",
    "Latte no-index path",
)

text = replace_exact(
    text,
    """\t// query index buffer from renderer
\tindexAllocation = g_renderer->indexData_reserveIndexMemory(indexOutputSize);
\tvoid* indexOutputPtr = indexAllocation.mem;
""",
    """\t// query index buffer from renderer
\tvoid* indexOutputPtr = g_renderer->indexData_reserveIndexMemory(indexOutputSize, indexBufferOffset, indexBufferIndex);
""",
    "Latte reserve index memory",
)

old_tail = """\tg_renderer->indexData_uploadIndexMemory(indexAllocation);
\tperformanceMonitor.cycle[performanceMonitor.cycleIndex].indexDataUploaded += indexOutputSize;
\t// get least recently used cache entry
\tauto lruEntry = std::min_element(LatteIndexCache.entry.begin(), LatteIndexCache.entry.end(), [](const auto& a, const auto& b)
\t{
\t\treturn a.lastUsed < b.lastUsed;
\t});
\t// invalidate previous allocation
\tif(lruEntry->lastPtr != nullptr)
\t\tg_renderer->indexData_releaseIndexMemory(lruEntry->indexAllocation);
\t// update cache
\tlruEntry->lastPtr = indexData;
\tlruEntry->lastCount = count;
\tlruEntry->lastPrimitiveMode = primitiveMode;
\tlruEntry->lastIndexType = indexType;
\tlruEntry->indexMax = indexMax;
\tlruEntry->renderIndexType = renderIndexType;
\tlruEntry->outputCount = outputCount;
\tlruEntry->indexAllocation = indexAllocation;
\tlruEntry->lastUsed = LatteIndices_GetNextUsageIndex();
"""
new_tail = """\tg_renderer->indexData_uploadIndexMemory(indexBufferOffset, indexOutputSize);
\t// update cache
\tLatteIndexCache.lastPtr = indexData;
\tLatteIndexCache.lastCount = count;
\tLatteIndexCache.lastPrimitiveMode = primitiveMode;
\tLatteIndexCache.lastIndexType = indexType;
\tLatteIndexCache.indexMax = indexMax;
\tLatteIndexCache.renderIndexType = renderIndexType;
\tLatteIndexCache.outputCount = outputCount;
\tLatteIndexCache.indexBufferOffset = indexBufferOffset;
\tLatteIndexCache.indexBufferIndex = indexBufferIndex;
"""
text = replace_exact(text, old_tail, new_tail, "Latte index upload/cache tail")
write(path, text)

# Guardrails: the Windows Vulkan path must no longer contain the #1443 allocation object flow.
checks = {
    "src/Cafe/HW/Latte/Core/LatteIndices.cpp": ["Renderer::IndexAllocation", "indexData_releaseIndexMemory"],
    "src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRendererCore.cpp": ["VKRSynchronizedHeapAllocator::AllocatorReservation* indexReservation", "indexData_releaseIndexMemory"],
}
for file_path, forbidden in checks.items():
    data = read(file_path)
    for token in forbidden:
        if token in data:
            raise RuntimeError(f"Guardrail failed: {token!r} still present in {file_path}")

mm = read("src/Cafe/HW/Latte/Renderer/Vulkan/VKRMemoryManager.h")
if "VKRSynchronizedRingAllocator m_indexBuffer;" not in mm:
    raise RuntimeError("Guardrail failed: index allocator is not the ring allocator")

print(f"Legacy index dataflow patch applied; draw sites patched: {draw_count}")
