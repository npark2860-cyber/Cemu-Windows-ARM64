#pragma once
#include <cstdint>
#include <cstddef>
#include <stdexcept>

// Only complete, packaged model/shader pairs are selectable. Immutable once a
// context exists, so worker jobs and GPU buffers cannot cross resolutions.
struct ProcessingProfile {
    uint32_t width{}, height{}, flowWidth{}, flowHeight{};
    size_t pixels{}, inputBytes{}, outputBytes{}, flowBytes{};
    const wchar_t* label{};
    static ProcessingProfile fromHeight(uint32_t height) {
        if (height != 1080 && height != 720)
            throw std::invalid_argument("NPU processing height must be 1080 or 720");
        const uint32_t width = height == 1080 ? 1920 : 1280;
        const uint32_t flowWidth = (width + 15) / 16, flowHeight = (height + 15) / 16;
        const size_t pixels = size_t(width) * height;
        return {width, height, flowWidth, flowHeight, pixels, pixels * 6, pixels * 3,
                size_t(flowWidth) * flowHeight * 16, height == 1080 ? L"1080p" : L"720p"};
    }
};
