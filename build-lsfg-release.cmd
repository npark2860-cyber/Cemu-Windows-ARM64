@echo off
if not exist Q:\ subst Q: "%~dp0Cemu-versions\Test\LSFG-Release"
if not exist Q:\source\ROLE_GUARD_RELEASE.txt exit /b 1
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat" arm64 -vcvars_ver=14.51
if errorlevel 1 exit /b 1
set "PATH=Q:\toolchain;C:\Program Files\CMake\bin;C:\Program Files\Microsoft Visual Studio\18\Community\Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja;%PATH%"
cmake -S Q:/source -B Q:/build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=Q:/toolchain/clang-cl.exe -DCMAKE_CXX_COMPILER=Q:/toolchain/clang-cl.exe -DCMAKE_LINKER_TYPE=MSVC "-DCMAKE_EXE_LINKER_FLAGS=Q:/compiler-rt/clang_rt.builtins-aarch64.lib /DEBUG:FULL /OPT:REF /OPT:ICF" "-DCMAKE_CXX_FLAGS_RELEASE=/O2 /Ob2 /DNDEBUG /Z7" -DVCPKG_TARGET_TRIPLET=arm64-windows-static -DVCPKG_MANIFEST_INSTALL=OFF -DVCPKG_INSTALLED_DIR=Q:/vcpkg-installed -DCEMU_ENABLE_LSFG=ON -DLSFG_CEMU_BUILD_TESTS=ON
if errorlevel 1 exit /b 1
cmake --build Q:/build --parallel 4
exit /b %ERRORLEVEL%
