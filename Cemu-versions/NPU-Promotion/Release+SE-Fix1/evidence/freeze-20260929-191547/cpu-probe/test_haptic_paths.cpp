#define NOMINMAX
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <iostream>
#include "path_helpers.h"
#include "../../../source/src/Cafe/OS/common/EnhancedHapticEngine.h"

int wmain(int argc, wchar_t** argv)
{
    try {
        if (argc != 2) throw std::runtime_error("Expected existing haptic directory");
        const fs::path directory = fs::absolute(argv[1]);
        unsigned files = 0, oldThrows = 0, oldFailed = 0, checks = 0;
        auto check = [&](bool value) { if (!value) throw std::runtime_error("Path regression failed"); ++checks; };
        for (const auto& entry : fs::directory_iterator(directory)) {
            if (entry.path().extension() != L".bnvib") continue;
            const auto utf8 = _pathToUtf8(entry.path());
            bool oldLoaded = false;
            try {
                EnhancedHapticEngine::Clip clip;
                // Same implicit std::string -> fs::path conversion as the old
                // PlayBnvib call. Reads bytes only; no device or worker is used.
                oldLoaded = EnhancedHapticEngine::LoadBnvib(utf8, clip);
            } catch (const std::exception& error) {
                ++oldThrows;
                if (oldThrows == 1) std::cout << "old_exception=" << error.what() << '\n';
            }
            if (!oldLoaded) ++oldFailed;
            const auto fixed = _utf8ToPath(utf8);
            check(fixed == entry.path());
            EnhancedHapticEngine::Clip actual, reference;
            check(EnhancedHapticEngine::LoadBnvib(fixed, actual));
            check(EnhancedHapticEngine::LoadBnvib(entry.path(), reference));
            check(actual.sampleRateHz == reference.sampleRateHz && actual.samples.size() == reference.samples.size());
            check(actual.loop.has_value() == reference.loop.has_value());
            if (actual.loop) check(actual.loop->startSample == reference.loop->startSample && actual.loop->endSample == reference.loop->endSample && actual.loop->intervalSamples == reference.loop->intervalSamples);
            for (size_t i = 0; i < actual.samples.size(); ++i) {
                const auto a=actual.samples[i], b=reference.samples[i];
                check(a.amplitudeLow==b.amplitudeLow && a.frequencyLow==b.frequencyLow && a.amplitudeHigh==b.amplitudeHigh && a.frequencyHigh==b.frequencyHigh);
            }
            ++files;
        }
        check(files >= 12);
        if (GetACP() == 949) check(oldFailed == files);
        std::cout << "HAPTIC_PATH_CPU_VERIFIED acp=" << GetACP() << " files=" << files
                  << " old_throws=" << oldThrows << " old_failed=" << oldFailed
                  << " checks=" << checks << " gpu_npu_controller_cemu_executed=false\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
