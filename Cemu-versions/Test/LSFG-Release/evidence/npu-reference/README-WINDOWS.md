# Windows 本地开发与测试

已在本机 Windows x64 / AMD Ryzen 7 5700X3D 上编译、测试通过。
这是增加了 Windows 开发适配的源码副本，原始来源为 https://github.com/drewano/hexscale 。

## 快速使用

打开 PowerShell，进入项目目录：

```powershell
cd <workspace>\outputs\hexscale-main
.\dev.cmd build    # 编译 C++ 守护进程、CLI、Vulkan DLL 和测试程序
.\dev.cmd test     # 执行三个自动测试
.\dev.cmd start    # 在后台启动开发守护进程
.\dev.cmd status   # 查看运行状态
.\dev.cmd bench    # 执行 50 次 CPU 图像缩放基准测试
.\dev.cmd stop     # 正常停止守护进程
.\dev.cmd decky    # 按 package-lock.json 安装依赖并构建 Decky 前端
.\dev.cmd all      # 编译、测试和构建前端
```

`dev.cmd` 只为它启动的 PowerShell 进程设置脚本执行选项，不修改系统执行策略。
重新编译前先停止后台守护进程，以免 Windows 锁定 EXE。

控制现有守护进程：

```powershell
.\build-win\cli\Release\hexscale-cli.exe --disable
.\build-win\cli\Release\hexscale-cli.exe --enable
.\build-win\cli\Release\hexscale-cli.exe --sharpness 0.75
```

## 已配置的环境

| 组件 | 版本 / 来源 |
| --- | --- |
| MSVC x64 / C++20 | 已安装的 Visual Studio 2022 Build Tools，编译器 19.44.35209 |
| CMake | Visual Studio 附带的 3.31.6-msvc6，由脚本自动定位 |
| Python | 本机 Python 3.9.13 |
| Node.js | 22.23.2，项目工作目录下的便携版本，官方 SHA-256 校验通过 |
| Vulkan headers | 1.4.361，位于相邻工作目录 `work/vulkan-headers/include` |

工具依赖位于 `<workspace>\work`。请保留其中的
`node-v22.23.2-win-x64`、`vulkan-headers`；只移动项目源码目录会使当前脚本找不到这些依赖。
没有修改系统 PATH，没有安装开机启动服务。

## 构建产物和日志

- 守护进程：`build-win/daemon/Release/hexscaled.exe`
- CLI：`build-win/cli/Release/hexscale-cli.exe`
- Vulkan 层：`build-win/layer/Release/VkLayer_hexscale.dll`
- Decky 前端：`decky/dist/index.js`
- 守护进程日志：`build-win/logs/daemon.log`、`daemon-error.log`
- 自动测试日志：`build-win/Testing/Temporary/LastTest.log`

## 实测范围

三个 CTest 测试全部通过：

1. CPU 缩放输出：检查 1920×1080 的全部 RGB 像素，以及空输入拒绝行为。
2. CPU 基准测试：运行实际的双线性插值代码。
3. IPC 集成：启动独立守护进程，验证状态、开关、锐度及限幅、性能档位、Decky Python 解析、正常关闭。

另外已验证 CLI 开关和锐度控制、后台启动与停止、DLL 加载与两个 Vulkan 入口导出、Decky Rollup 构建。
本机一次 50 次迭代的 CPU 基准测试：平均 22.76 ms，约 43.94 帧/秒；这是独立 CPU 算法耗时，
不代表游戏帧率或 NPU 性能。后续结果会受系统负载影响。

## Windows 适配说明

- Windows 通过 Winsock 使用 `127.0.0.1:47653` 通信，保持原有二进制协议；Linux 仍使用原来的 Unix socket。
- 如端口被占用，在启动和调用客户端前设置同一个环境变量，例如 `$env:HEXSCALE_DEV_PORT='47654'`。
- Windows FastRPC 后端明确返回硬件不可用，CPU 测试沿用原有双线性插值算法。
- Windows 状态显示 `Windows x64 / CPU-dev`，没有处理帧时延迟为 0；不会显示原有写死的 NPU 性能数据。
- 修复缺少 `<algorithm>` 头文件，以及 Decky 通信包大小和字段偏移错误；补齐固定长度响应接收。
- 增加自动测试和本地启动脚本。完整修改保存在上级目录的 `windows-dev.patch`。

这个仓库目前的游戏帧传递和 QNN 图执行仍有未实现部分。这里验证的是开发程序、CPU 运算、控制通信及构建产物；
没有在 Windows 游戏中验证 Vulkan 层，也没有启动 SteamOS 的 Decky 界面。项目本身不是网页服务，启动后没有浏览器页面。
