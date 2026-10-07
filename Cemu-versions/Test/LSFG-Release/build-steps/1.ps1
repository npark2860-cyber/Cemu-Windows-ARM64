$ErrorActionPreference = 'Stop'
$swap = 'src/Cafe/HW/Latte/Renderer/Vulkan/SwapchainInfoVk.cpp'
$s = Get-Content $swap -Raw
$oldLoad = 'colorAttachment.loadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE;'
$newLoad = 'colorAttachment.loadOp = VK_ATTACHMENT_LOAD_OP_LOAD;'
if (-not $s.Contains($oldLoad)) { throw 'Swapchain loadOp pattern not found' }
$s = $s.Replace($oldLoad, $newLoad)
Set-Content -Path $swap -Value $s -NoNewline

$vr = 'src/Cafe/HW/Latte/Renderer/Vulkan/VulkanRenderer.cpp'
$v = Get-Content $vr -Raw

$oldFlag = 'beginInfo.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT;'
$newFlag = 'beginInfo.flags = VK_COMMAND_BUFFER_USAGE_SIMULTANEOUS_USE_BIT;'
$flagCount = ([regex]::Matches($v, [regex]::Escape($oldFlag))).Count
if ($flagCount -ne 2) { throw "Expected 2 ONE_TIME_SUBMIT flags, found $flagCount" }
$v = $v.Replace($oldFlag, $newFlag)

$anchorLF = "LatteTextureViewVk* texViewVk = (LatteTextureViewVk*)texView;`n`tdraw_endRenderPass();`n"
$anchorCRLF = "LatteTextureViewVk* texViewVk = (LatteTextureViewVk*)texView;`r`n`tdraw_endRenderPass();`r`n"
if ($v.Contains($anchorCRLF)) {
  $v = $v.Replace($anchorCRLF, $anchorCRLF + "`r`n`tif (clearBackground)`r`n`t`tClearColorbuffer(padView);`r`n")
} elseif ($v.Contains($anchorLF)) {
  $v = $v.Replace($anchorLF, $anchorLF + "`n`tif (clearBackground)`n`t`tClearColorbuffer(padView);`n")
} else {
  throw 'DrawBackbufferQuad anchor not found'
}

$clearPattern = '(?ms)\r?\n\tif \(clearBackground\)\r?\n\t\{\r?\n\t\tVkClearAttachment clearAttachment\{\};.*?\r?\n\t\}\r?\n\r?\n\tvkCmdBindPipeline'
if (-not [regex]::IsMatch($v, $clearPattern)) { throw 'vkCmdClearAttachments block not found' }
$v = [regex]::Replace($v, $clearPattern, "`n`tvkCmdBindPipeline", 1)
Set-Content -Path $vr -Value $v -NoNewline

git diff -- $swap $vr
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
