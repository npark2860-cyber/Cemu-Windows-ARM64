"""Create the separate motion/worker probe from the frozen 1080p revision-2 baseline."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
code=(root/'src/anvil1080_pipeline_probe.cpp').read_text(encoding='utf-8-sig')
def change(old,new):
    global code
    if old not in code: raise RuntimeError('Missing source anchor: '+old[:100])
    code=code.replace(old,new)

support=(root/'src/anvil1080_vulkan_support.h').read_text(encoding='utf-8-sig')
support=support.replace('void create(size_t size, Ort::Allocator* allocator)', 'void create(size_t size, Ort::Allocator* allocator, VkBufferUsageFlags extraUsage = 0)')
support=support.replace('allocator ? sharedUsage : VK_BUFFER_USAGE_TRANSFER_DST_BIT;', 'allocator ? sharedUsage : (VK_BUFFER_USAGE_TRANSFER_DST_BIT | extraUsage);')
(root/'src/motion1080_vulkan_support.h').write_text(support,encoding='utf-8')
change('#include "anvil1080_vulkan_support.h"','#include "motion1080_vulkan_support.h"\n#include "anvil_async_worker.h"\n#include <memory>')
change('constexpr size_t diagnosticBytes = inputBytes + outputBytes + rgbaBytes;',
       'constexpr size_t flowBytes = 120 * 68 * 16;\nconstexpr size_t diagnosticBytes = inputBytes + outputBytes + rgbaBytes * 2 + flowBytes * 2;')
change('void create() {','void create(uint32_t imageWidth = width, uint32_t imageHeight = height) {')
change('info.extent = {width, height, 1};','info.extent = {imageWidth, imageHeight, 1};')
change('std::array<VkShaderModule, 3>','std::array<VkShaderModule, 5>')
change('std::array<VkPipeline, 3>','std::array<VkPipeline, 5>')
change('GpuImage& composed, const fs::path& shaderDirectory)', 'GpuImage& composed, Buffer& forward, Buffer& backward, GpuImage& quarterA, GpuImage& quarterB, GpuImage& warpedA, GpuImage& warpedB, const fs::path& shaderDirectory)')
change('std::array<VkDescriptorSetLayoutBinding, 5>','std::array<VkDescriptorSetLayoutBinding, 11>')
change('(i == 2 || i == 3)', '(i == 2 || i == 3 || i == 5 || i == 6)')
change('{VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, 3}, {VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 2}', '{VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, 7}, {VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, 4}')
start=code.index('        const std::array<VkDescriptorImageInfo, 3> images')
end=code.index('        vk.vkUpdateDescriptorSets',start)
code=code[:start]+'''        std::array<VkDescriptorImageInfo, 11> images{};
        std::array<VkDescriptorBufferInfo, 11> buffers{};
        const std::array<std::pair<unsigned,GpuImage*>,7> imageBindings{{{0,&a},{1,&b},{4,&composed},{7,&quarterA},{8,&quarterB},{9,&warpedA},{10,&warpedB}}};
        for(auto [binding,image]:imageBindings) images[binding]={VK_NULL_HANDLE,image->view,VK_IMAGE_LAYOUT_GENERAL};
        buffers[2]={input.buffer,0,inputBytes}; buffers[3]={output.buffer,0,outputBytes};
        buffers[5]={forward.buffer,0,flowBytes}; buffers[6]={backward.buffer,0,flowBytes};
        std::array<VkWriteDescriptorSet, 11> writes{};
        for (uint32_t i = 0; i < writes.size(); ++i) {
            writes[i].sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET; writes[i].dstSet = set; writes[i].dstBinding = i;
            writes[i].descriptorCount = 1; writes[i].descriptorType = bindings[i].descriptorType;
            if (i==2 || i==3 || i==5 || i==6) writes[i].pBufferInfo=&buffers[i];
            else writes[i].pImageInfo=&images[i];
        }
'''+code[end:]
change('const std::array<const wchar_t*, 3> shaderNames{L"anvil1080-generate.spv", L"anvil1080-pack.spv", L"anvil1080-compose.spv"};',
       'const std::array<const wchar_t*, 5> shaderNames{L"motion1080-generate.spv", L"motion1080-pack.spv", L"motion1080-compose.spv", L"motion1080-downsample.spv", L"motion1080-flow.spv"};')
change('qi.queryCount = 6','qi.queryCount = 12')
change('std::array<VkImageMemoryBarrier, 3>','std::array<VkImageMemoryBarrier, 7>')
change('const std::array<VkImage, 3> handles{a.image, b.image, composed.image};','const std::array<VkImage, 7> handles{a.image, b.image, composed.image, quarterA.image, quarterB.image, warpedA.image, warpedB.image};')
change('else vk.vkCmdDispatch(vk.command, (width + 15) / 16, (height + 15) / 16, 1);',
       'else if (pipeline == 3) vk.vkCmdDispatch(vk.command, 30, 17, 1);\n        else if (pipeline == 4) vk.vkCmdDispatch(vk.command, 15, 9, 2);\n        else vk.vkCmdDispatch(vk.command, (width + 15) / 16, (height + 15) / 16, 1);')
change('std::array<double, 3> times()', 'std::array<double, 6> times()')
change('std::array<uint64_t, 6> ticks', 'std::array<uint64_t, 12> ticks')
change('queries, 0, 6, sizeof(ticks)', 'queries, 0, 12, sizeof(ticks)')
change('std::array<double, 3> values', 'std::array<double, 6> values')
change('i < 3; ++i) values', 'i < 6; ++i) values')
change('GpuImage& composed, Buffer& diagnostic)', 'GpuImage& composed, Buffer& diagnostic, GpuImage& warpedA, Buffer& forward, Buffer& backward)')
anchor='    vk.vkCmdCopyImageToBuffer(vk.command, composed.image, VK_IMAGE_LAYOUT_GENERAL, diagnostic.buffer, 1, &imageCopy);'
change(anchor,anchor+'''
    imageCopy.bufferOffset += rgbaBytes;
    vk.vkCmdCopyImageToBuffer(vk.command, warpedA.image, VK_IMAGE_LAYOUT_GENERAL, diagnostic.buffer, 1, &imageCopy);
    const VkBufferCopy cf{0,inputBytes+outputBytes+rgbaBytes*2,flowBytes}, cb{0,inputBytes+outputBytes+rgbaBytes*2+flowBytes,flowBytes};
    vk.vkCmdCopyBuffer(vk.command,forward.buffer,diagnostic.buffer,1,&cf);
    vk.vkCmdCopyBuffer(vk.command,backward.buffer,diagnostic.buffer,1,&cb);''')
start=code.index('// CPU oracle uses logical channel indices')
end=code.index('int wmain(',start)
code=code[:start]+'''// Native consumption oracle. Full motion/input oracle is in the independent CPU reader.
void validateReadback(const uint8_t* bytes, unsigned phase, Report& report) {
    unsigned maximum{}; const auto* warped=bytes+inputBytes+outputBytes+rgbaBytes;
    for(size_t p=0;p<pixels;++p) {
        const auto mask=warped[p*4+3]; if(mask!=0 && mask!=255) throw std::runtime_error("Invalid confidence mask");
        for(unsigned c=0;c<3;++c) {
            if(warped[p*4+c]!=bytes[p*6+c]) throw std::runtime_error("Warped image and tensor disagree");
            const double mean=(double(bytes[p*6+c])+bytes[p*6+c+3])/2.0;
            const double residual=mask?(int(bytes[inputBytes+p*3+c])-128)*residualScale*255.0:0.0;
            const int expected=int(std::lround(std::clamp(mean+residual,0.0,255.0)));
            const unsigned error=unsigned(std::abs(int(bytes[inputBytes+outputBytes+p*4+c])-expected));
            maximum=std::max(maximum,error); if(error>1) throw std::runtime_error("Motion compose mismatch");
        }
        if(bytes[inputBytes+outputBytes+p*4+3]!=255) throw std::runtime_error("Composed alpha mismatch");
    }
    report.number("last_phase",phase); report.number("last_compose_max_error",maximum);
}

'''+code[end:]
change('anvil1080-pipeline-probe','motion1080-pipeline-probe')
change('Buffer input(vk), output(vk), diagnostic(vk);','Buffer input(vk), output(vk), diagnostic(vk), forward(vk), backward(vk);')
change('report.number("input_import_bytes", input.allocationSize);',
       'forward.create(flowBytes,nullptr,VK_BUFFER_USAGE_STORAGE_BUFFER_BIT|VK_BUFFER_USAGE_TRANSFER_SRC_BIT); backward.create(flowBytes,nullptr,VK_BUFFER_USAGE_STORAGE_BUFFER_BIT|VK_BUFFER_USAGE_TRANSFER_SRC_BIT);\n        report.number("input_import_bytes", input.allocationSize);')
change('GpuImage a(vk), b(vk), composed(vk); a.create(); b.create(); composed.create();',
       'GpuImage a(vk), b(vk), composed(vk), quarterA(vk), quarterB(vk), warpedA(vk), warpedB(vk); a.create(); b.create(); composed.create(); quarterA.create(480,270); quarterB.create(480,270); warpedA.create(); warpedB.create();')
change('compute.create(input, output, a, b, composed, shaderDirectory);','compute.create(input, output, a, b, composed, forward, backward, quarterA, quarterB, warpedA, warpedB, shaderDirectory);')
change('const unsigned count = verify ? 3 : 34;', 'cemu::npu::AsyncWorker worker(3);\n        const unsigned count = verify ? 4 : 34;')
change('const unsigned phase = round % 3;', 'const unsigned phase = round % 4;')
change('compute.queries, 0, 6', 'compute.queries, 0, 12')
change('compute.stamp(2, false); compute.dispatch(1, phase); compute.stamp(3, true);', '''compute.stamp(2, false); compute.dispatch(3, phase); compute.stamp(3, true);
            vk.barrier(VK_ACCESS_SHADER_WRITE_BIT,VK_ACCESS_SHADER_READ_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT);
            compute.stamp(4,false); compute.dispatch(4,phase); compute.stamp(5,true);
            vk.barrier(VK_ACCESS_SHADER_WRITE_BIT,VK_ACCESS_SHADER_READ_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT);
            compute.stamp(6,false); compute.dispatch(1,phase); compute.stamp(7,true);''')
old='''            const auto npuStart = Clock::now();
            session.Run(Ort::RunOptions{nullptr}, inputNames.data(), &inputTensor, 1, outputNames.data(), &outputTensor, 1);
            const double npuMs = elapsed(npuStart);'''
new='''            struct InferenceTiming { Clock::time_point start{},end{}; };
            // Own per-job timing even if a GPU error unwinds this loop before Run ends.
            const auto inference=std::make_shared<InferenceTiming>();
            cemu::npu::FramePair ticket{worker.epoch(),round,round+1,0,width,height,Clock::now()+std::chrono::seconds(5)};
            const auto enqueueStart=Clock::now();
            auto execute=[&,inference](const cemu::npu::AsyncWorker::StillCurrent& current) {
                // Producer fence is complete in this standalone harness. In Cemu the
                // callback must retire the slot's input fence before this check.
                if(!current()) return false;
                inference->start=Clock::now();
                session.Run(Ort::RunOptions{nullptr},inputNames.data(),&inputTensor,1,outputNames.data(),&outputTensor,1);
                inference->end=Clock::now(); return true;
            };
            while(!worker.submit(ticket,execute)) {
                if(elapsed(enqueueStart)>10) throw std::runtime_error("Worker submission unexpectedly unavailable");
                std::this_thread::yield();
            }
            const double enqueueMs=elapsed(enqueueStart);
            // Independent producer work touches only source images; all in-flight
            // NPU tensors and warped images remain unchanged until consumption ends.
            const auto producerStart=Clock::now(); vk.begin();
            vk.barrier(VK_ACCESS_MEMORY_READ_BIT|VK_ACCESS_MEMORY_WRITE_BIT,VK_ACCESS_SHADER_WRITE_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT);
            compute.stamp(10,false); compute.dispatch(0,(phase+1)%4); compute.stamp(11,true); vk.submitAndWait();
            const auto producerEnd=Clock::now(); const auto pollStart=Clock::now();
            std::optional<cemu::npu::Completion> completion;
            while(!(completion=worker.take())) std::this_thread::sleep_for(std::chrono::milliseconds(1));
            const double harnessPollMs=elapsed(pollStart);
            if(completion->error) std::rethrow_exception(completion->error);
            if(completion->stale || !completion->executed) throw std::runtime_error("Worker result expired or was invalidated");
            const double npuMs=std::chrono::duration<double,std::milli>(inference->end-inference->start).count();
            const double overlapMs=std::max(0.0,std::chrono::duration<double,std::milli>(std::min(producerEnd,inference->end)-std::max(producerStart,inference->start)).count());'''
change(old,new)
change('compute.stamp(4, false); compute.dispatch(2, phase); compute.stamp(5, true);','compute.stamp(8, false); compute.dispatch(2, phase); compute.stamp(9, true);')
change('<< gpu[1] << ",\\\"compose_gpu_ms\\\":" << gpu[2]', '<< gpu[3] << ",\\\"compose_gpu_ms\\\":" << gpu[4]')
change('<< ",\\\"post_submit_ms\\\":" << post.submitMs << ",\\\"post_fence_ms\\\":" << post.waitMs << \'}\';',
       '<< ",\\\"post_submit_ms\\\":" << post.submitMs << ",\\\"post_fence_ms\\\":" << post.waitMs\n                << ",\\\"downsample_gpu_ms\\\":" << gpu[1] << ",\\\"motion_gpu_ms\\\":" << gpu[2] << ",\\\"lookahead_gpu_ms\\\":" << gpu[5]\n                << ",\\\"worker_submit_wall_ms\\\":" << enqueueMs << ",\\\"producer_overlap_ms\\\":" << overlapMs << ",\\\"harness_completion_poll_ms\\\":" << harnessPollMs << \'}\';')
change('readback(vk, input, output, composed, diagnostic)', 'readback(vk, input, output, composed, diagnostic, warpedA, forward, backward)')
change('for (size_t p = 0; p < pixels; ++p) for (unsigned c = 0; c < 6; ++c) referenceInput[p * 6 + c] = expectedInput(p, c, phase);',
       'std::copy(bytes,bytes+inputBytes,referenceInput.begin()); // CPU reader independently verifies this aligned input before accepting the run.')
change('report.boolean("gpu_texture_input_and_compose", true);', 'report.boolean("async_worker",true); report.boolean("motion_alignment",true); report.number("phase_cycle",4); report.boolean("gpu_texture_input_and_compose", true);')
change('Serialized GPU synthetic-image generation, RGBA8-to-NHWC pack, direct shared-tensor NPU Run and GPU residual compose; includes two host fence waits and output poison. Excludes initialization, disk I/O, diagnostic readback, CPU oracle, ordinary-memory references, motion estimation/warp, Cemu rendering and present. GPU timestamps are nested within wall times; do not add them to wall totals.',
       'Standalone synthetic image generation, quarter-resolution bidirectional block matching, midpoint warp/NHWC pack, worker-thread QNN Run and GPU residual compose. Independent next-image generation overlaps the host NPU call. Includes benchmark completion polling and serialized GPU fences. Excludes real Cemu rendering, present, game quality and sustained contention. Host-call overlap is not proof of simultaneous device execution.')
change('ANVIL1080_COMPLETED_VERIFICATION_PENDING','MOTION1080_COMPLETED_VERIFICATION_PENDING')
(root/'src/motion1080_pipeline_probe.cpp').write_text(code,encoding='utf-8')
print('Prepared separate motion/worker source; baseline left unchanged.')
