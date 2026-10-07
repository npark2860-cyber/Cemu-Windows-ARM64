$ErrorActionPreference = 'Stop'
& 'C:\Users\angel\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools/graphics/Apply-FidelityFXFSRExperiment.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& 'C:\Users\angel\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools/graphics/Apply-FidelityFXFSRFullExperiment.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
git diff --check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
git diff -- src/config/CemuConfig.h src/config/CemuConfig.cpp src/gui/wxgui/GeneralSettings2.h src/gui/wxgui/GeneralSettings2.cpp src/Cafe/HW/Latte/Renderer/RendererOuputShader.h src/Cafe/HW/Latte/Renderer/RendererOuputShader.cpp src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp src/Cafe/HW/Latte/Core/LatteRenderTarget.cpp
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
