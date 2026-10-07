
#define VK_NO_PROTOTYPES
#include <vulkan/vulkan.h>
#include <algorithm>
#include <array>
#include <iostream>
#include <vector>
#include <stdexcept>
#include <cstdint>
struct VulkanNPUState {VkImage realImage;VkExtent2D realExtent;VkFormat realFormat;};
std::vector<uint8_t> sourcePixels,destPixels;
unsigned checks{},copies{},blits{},barriers{};
VkExtent2D expectedExtent{};
void require(bool ok,const char* why){++checks;if(!ok)throw std::runtime_error(why);}
void NpuBarrier(VkCommandBuffer,VkImage,VkImageLayout,VkImageLayout){++barriers;}
VKAPI_ATTR void VKAPI_CALL vkCmdCopyImage(VkCommandBuffer,VkImage,VkImageLayout a,VkImage,VkImageLayout b,uint32_t count,const VkImageCopy* regions){
    require(a==VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL && b==VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,"copy layouts");
    require(count==1 && regions[0].extent.depth==1,"one complete image");
    require(regions[0].extent.width==expectedExtent.width && regions[0].extent.height==expectedExtent.height,"original extent retained");
    require(regions[0].srcSubresource.aspectMask==VK_IMAGE_ASPECT_COLOR_BIT && regions[0].dstSubresource.aspectMask==VK_IMAGE_ASPECT_COLOR_BIT,"color aspect");
    require(sourcePixels.size()==destPixels.size(),"no resized destination");
    std::copy(sourcePixels.begin(),sourcePixels.end(),destPixels.begin());++copies;
}
void NpuBlit(VkCommandBuffer,VkImage,VkImageLayout,VkExtent2D size,VkImage,VkImageLayout,VkExtent2D){
    require(size.width==expectedExtent.width && size.height==expectedExtent.height,"resize preserves the old original extent");++blits;
}
void NpuCopyNative(VkCommandBuffer command,VkImage source,VkImageLayout beforeSource,
    VkImage destination,VkImageLayout beforeDestination,VkImageLayout afterDestination,VkExtent2D extent) {
    NpuBarrier(command,source,beforeSource,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL);
    NpuBarrier(command,destination,beforeDestination,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL);
    VkImageCopy copy{};copy.srcSubresource=copy.dstSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1};
    copy.extent={extent.width,extent.height,1};
    vkCmdCopyImage(command,source,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,destination,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,1,&copy);
    NpuBarrier(command,source,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,beforeSource);
    NpuBarrier(command,destination,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,afterDestination);
}
void NpuRestoreNative(VkCommandBuffer command,const VulkanNPUState& state,VkImage destination,
    VkImageLayout beforeDestination,VkExtent2D extent,VkFormat format) {
    if(extent.width==state.realExtent.width && extent.height==state.realExtent.height && format==state.realFormat)
        NpuCopyNative(command,state.realImage,VK_IMAGE_LAYOUT_GENERAL,destination,beforeDestination,VK_IMAGE_LAYOUT_PRESENT_SRC_KHR,extent);
    else // A resize during the generated present may still release the old pair.
        NpuBlit(command,state.realImage,VK_IMAGE_LAYOUT_GENERAL,state.realExtent,destination,beforeDestination,extent);
}
int main(){try{
    for(const auto size:std::array<VkExtent2D,3>{{{1280,720},{1920,1080},{1429,992}}})
    for(const auto format:{VK_FORMAT_R8G8B8A8_UNORM,VK_FORMAT_B8G8R8A8_UNORM}){
        expectedExtent=size;sourcePixels.resize(size_t(size.width)*size.height*4);destPixels.assign(sourcePixels.size(),0);
        for(size_t i=0;i<sourcePixels.size();++i)sourcePixels[i]=uint8_t((i*73u)^(i>>4)^(i>>15));
        const auto beforeCopies=copies,beforeBlits=blits,beforeBarriers=barriers;
        VulkanNPUState state{reinterpret_cast<VkImage>(uintptr_t(1)),size,format};
        NpuRestoreNative(VK_NULL_HANDLE,state,reinterpret_cast<VkImage>(uintptr_t(2)),VK_IMAGE_LAYOUT_PRESENT_SRC_KHR,size,format);
        require(copies==beforeCopies+1 && blits==beforeBlits,"normal original restoration never scales");
        require(barriers==beforeBarriers+4,"both images restored after transfer");
        require(sourcePixels==destPixels,"high frequency pixels and all four channels retained exactly");
        NpuRestoreNative(VK_NULL_HANDLE,state,reinterpret_cast<VkImage>(uintptr_t(2)),VK_IMAGE_LAYOUT_UNDEFINED,{size.width+100,size.height+50},format);
        require(blits==beforeBlits+1,"resize-only path scales previous original");
        const auto other=format==VK_FORMAT_R8G8B8A8_UNORM?VK_FORMAT_B8G8R8A8_UNORM:VK_FORMAT_R8G8B8A8_UNORM;
        NpuRestoreNative(VK_NULL_HANDLE,state,reinterpret_cast<VkImage>(uintptr_t(2)),VK_IMAGE_LAYOUT_UNDEFINED,size,other);
        require(blits==beforeBlits+2,"surface format change uses conversion instead of raw cross-format copy");
    }
    std::cout<<"NATIVE_RESTORE_CPU_CONTRACT_PASSED checks="<<checks<<" gpu_npu_executed=false; actual helper bodies with mocked Vulkan commands, not a driver test\n";
    return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
