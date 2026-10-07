"""Compile the actual ImGui upload/replay function against CPU-only Vulkan spies.

This checks host buffer writes and last-reader tracking, not Vulkan execution.
"""
from pathlib import Path

root = Path(__file__).resolve().parent
source = root.parent.parent / "LSFG-Release/source/src/imgui/imgui_impl_vulkan.cpp"
text = source.read_text(encoding="utf-8-sig")
structures = text[text.index("struct ImGui_ImplVulkanH_FrameRenderBuffers"):text.index("// Vulkan data")]
functions = text[text.index("static void ImGui_ImplVulkan_RenderDrawDataInternal"):text.index("void ImGui_ImplVulkan_DestroyFontsTexture()\n{")]
stub = r'''
#define VK_NO_PROTOTYPES
#include <vulkan/vulkan.h>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <vector>
#include <string>
using uint32=uint32_t;
struct ImVec2 {float x{},y{};};
struct ImVec4 {float x{},y{},z{},w{};};
struct ImDrawVert {float value[5];};
using ImDrawIdx=uint16_t;
template<class T> struct BufferData {int Size{};T* Data{};T& operator[](int i) const{return Data[i];}};
struct ImDrawList;struct ImDrawCmd;
using Callback=void(*)(const ImDrawList*,const ImDrawCmd*);
void resetState(const ImDrawList*,const ImDrawCmd*) {}
const Callback ImDrawCallback_ResetRenderState=resetState;
struct ImDrawCmd {Callback UserCallback{};ImVec4 ClipRect;void* TextureId{};unsigned ElemCount{};};
struct ImDrawList {BufferData<ImDrawVert> VtxBuffer;BufferData<ImDrawIdx> IdxBuffer;BufferData<ImDrawCmd> CmdBuffer;};
struct ImDrawData {ImVec2 DisplaySize{640,480},FramebufferScale{1,1},DisplayPos{};int TotalVtxCount{3},TotalIdxCount{3},CmdListsCount{};ImDrawList** CmdLists{};};
struct ImGuiTexture {VkDescriptorSet descriptor_set{};};
struct ImGui_ImplVulkan_InitInfo {VkDevice Device{};unsigned ImageCount{2};void* UploadUser{};uint64_t(*UploadCommandId)(void*){};void(*WaitUploadCommand)(void*,uint64_t){};};
#define IM_ALLOC std::malloc
#define IM_ASSERT(x) do{if(!(x))throw std::runtime_error("assertion");}while(0)
#define cemu_assert_debug IM_ASSERT
'''
spies = r'''
ImGui_ImplVulkan_InitInfo g_VulkanInitInfo;
ImGui_ImplVulkanH_WindowRenderBuffers g_MainWindowRenderBuffers{};
const ImDrawData* g_LastUploadedDrawData=nullptr;
int g_LastUploadedVertices=0,g_LastUploadedIndices=0;
VkPipelineLayout g_PipelineLayout{};
unsigned maps=0,flushes=0,allocations=0,checks=0;
uint64_t commandId=0;
std::vector<uint64_t> waited;
std::vector<std::string> events;
std::vector<VkBuffer> drawnBuffers;
void require(bool value,const char* reason){++checks;if(!value)throw std::runtime_error(reason);}
void check_vk_result(VkResult r){require(r==VK_SUCCESS,"mock Vulkan result");}
void CreateOrResizeBuffer(VkBuffer& b,VkDeviceMemory& m,VkDeviceSize& size,size_t count,VkBufferUsageFlagBits) {
    ++allocations; b=reinterpret_cast<VkBuffer>(uintptr_t(allocations));m=reinterpret_cast<VkDeviceMemory>(uintptr_t(allocations));size=count;events.push_back("allocate");
}
VkResult vkMapMemory(VkDevice,VkDeviceMemory,VkDeviceSize,VkDeviceSize,VkMemoryMapFlags,void** pointer) {
    static char memory[4096]{};*pointer=memory;++maps;events.push_back("map");return VK_SUCCESS;
}
void vkUnmapMemory(VkDevice,VkDeviceMemory){}
VkResult vkFlushMappedMemoryRanges(VkDevice,uint32_t,const VkMappedMemoryRange*){++flushes;return VK_SUCCESS;}
void vkCmdSetScissor(VkCommandBuffer,uint32_t,uint32_t,const VkRect2D*){}
void vkCmdBindDescriptorSets(VkCommandBuffer,VkPipelineBindPoint,VkPipelineLayout,uint32_t,uint32_t,const VkDescriptorSet*,uint32_t,const uint32_t*){}
void vkCmdDrawIndexed(VkCommandBuffer,uint32_t,uint32_t,uint32_t,int32_t,uint32_t){}
void ImGui_ImplVulkan_SetupRenderState(ImDrawData*,VkCommandBuffer,ImGui_ImplVulkanH_FrameRenderBuffers* rb,int,int){drawnBuffers.push_back(rb->VertexBuffer);}
'''
tests = r'''
int main() {
 try {
    g_VulkanInitInfo.UploadCommandId=[](void*){return commandId;};
    g_VulkanInitInfo.WaitUploadCommand=[](void*,uint64_t id){waited.push_back(id);events.push_back("wait:"+std::to_string(id));};
    ImDrawData draw;
    bool rejected=false;
    try{ImGui_ImplVulkan_ReplayDrawData(&draw,nullptr);}catch(const std::exception&){rejected=true;}
    require(rejected && maps==0 && !g_MainWindowRenderBuffers.FrameRenderBuffers,"cold replay must not allocate/write");
    commandId=1;ImGui_ImplVulkan_RenderDrawData(&draw,nullptr);
    const auto index=g_MainWindowRenderBuffers.Index;
    const auto buffer=drawnBuffers.back();
    require(maps==2 && flushes==1 && waited.empty(),"first upload");
    commandId=2;ImGui_ImplVulkan_ReplayDrawData(&draw,nullptr);
    require(maps==2 && flushes==1 && allocations==2,"replay must not map, flush or allocate");
    require(g_MainWindowRenderBuffers.Index==index && drawnBuffers.back()==buffer,"same immutable buffer is drawn twice");
    require(g_MainWindowRenderBuffers.FrameRenderBuffers[index].LastReadCommand==2,"replay extends last reader");
    commandId=3;ImGui_ImplVulkan_RenderDrawData(&draw,nullptr);
    require(waited.empty() && g_MainWindowRenderBuffers.Index!=index,"second ring slot independent");
    commandId=4;ImGui_ImplVulkan_ReplayDrawData(&draw,nullptr);
    events.clear();commandId=5;ImGui_ImplVulkan_RenderDrawData(&draw,nullptr);
    require(waited.size()==1 && waited.back()==2,"ring wrap waits for real replay, not generated draw");
    require(events.front()=="wait:2" && events[1]=="map","wait happens before host overwrite");
    ImDrawData changed;rejected=false;const auto before=maps;
    try{ImGui_ImplVulkan_ReplayDrawData(&changed,nullptr);}catch(const std::exception&){rejected=true;}
    require(rejected && maps==before,"different draw data cannot replay or overwrite");
    changed=draw;changed.TotalVtxCount=0;
    ImGui_ImplVulkan_RenderDrawData(&changed,nullptr);ImGui_ImplVulkan_ReplayDrawData(&changed,nullptr);
    require(maps==before,"empty overlay does not write");
    // Many source frames with intermittent generation and pad-like extra draws.
    // Every reused slot must wait on its most recent normal or replay reader.
    for(int frame=0;frame<100;++frame) {
        const auto next=(g_MainWindowRenderBuffers.Index+1)%g_MainWindowRenderBuffers.Count;
        const auto previous=g_MainWindowRenderBuffers.FrameRenderBuffers[next].LastReadCommand;
        ++commandId;ImGui_ImplVulkan_RenderDrawData(&draw,nullptr);
        require(waited.back()==previous,"long-run wrap respects latest reader");
        if(frame%3) {
            const auto written=maps;const auto oldIndex=g_MainWindowRenderBuffers.Index;
            ++commandId;ImGui_ImplVulkan_ReplayDrawData(&draw,nullptr);
            require(maps==written && g_MainWindowRenderBuffers.Index==oldIndex,"long-run replay immutable");
        }
    }
    std::free(g_MainWindowRenderBuffers.FrameRenderBuffers);
    std::cout<<"{\"status\":\"OVERLAY_CPU_CONTRACT_PASSED\",\"checks\":"<<checks<<",\"gpu_npu_executed\":false}\n";
    return 0;
 } catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
'''
(root / "build/test_overlay_contract.cpp").write_text(stub+structures+spies+functions+tests,encoding="utf-8")
print("Extracted production upload/replay function for CPU spies; no GPU/NPU execution")
