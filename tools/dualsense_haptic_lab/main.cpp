#include <windows.h>
#include <commctrl.h>

#include <array>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "test_utils.h"
#include "GCore/Types/Structs/Context/DeviceContext.h"

namespace
{
constexpr UINT_PTR kTimerId = 1;
constexpr int kPollMs = 16;

enum ControlId
{
    ID_STATUS = 100,
    ID_DETECT,
    ID_LEFT_RUMBLE,
    ID_RIGHT_RUMBLE,
    ID_APPLY_RUMBLE,
    ID_BOW,
    ID_GALLOP,
    ID_WEAPON,
    ID_MACHINE,
    ID_STOP_ALL,
};

std::unique_ptr<IPlatformHardware> gHardware;
std::unique_ptr<test_utils::test_device_registry> gRegistry;
HWND gStatus = nullptr;
HWND gLeftRumble = nullptr;
HWND gRightRumble = nullptr;
bool gWasConnected = false;

IGamepadBase* CurrentGamepad()
{
    return gRegistry ? gRegistry->GetLibrary(0) : nullptr;
}

const wchar_t* ConnectionName(EDSDeviceConnection type)
{
    switch (type)
    {
    case EDSDeviceConnection::Usb:
        return L"USB";
    case EDSDeviceConnection::Bluetooth:
        return L"Bluetooth";
    default:
        return L"Unknown";
    }
}

const wchar_t* DeviceName(EDSDeviceType type)
{
    switch (type)
    {
    case EDSDeviceType::DualSense:
        return L"DualSense";
    case EDSDeviceType::DualSenseEdge:
        return L"DualSense Edge";
    case EDSDeviceType::DualShock4:
        return L"DualShock 4";
    default:
        return L"Unknown device";
    }
}

void SetStatus(const std::wstring& text)
{
    if (gStatus)
        SetWindowTextW(gStatus, text.c_str());
}

void RefreshController()
{
    if (!gRegistry)
        return;

    gRegistry->PlugAndPlay(0.016f);
    auto* gamepad = CurrentGamepad();
    const bool connected = gamepad && gamepad->IsConnected();

    if (!connected)
    {
        if (gWasConnected)
            SetStatus(L"Disconnected - waiting for DualSense...");
        else
            SetStatus(L"Searching for DualSense...");
        gWasConnected = false;
        return;
    }

    gamepad->UpdateInput(0.016f);
    auto* ctx = gamepad->GetMutableDeviceContext();
    if (!ctx)
    {
        SetStatus(L"Connected, but device context is unavailable.");
        return;
    }

    std::wstring status = L"Connected: ";
    status += DeviceName(ctx->DeviceType);
    status += L"  |  ";
    status += ConnectionName(ctx->ConnectionType);
    SetStatus(status);
    gWasConnected = true;
}

bool ApplyTrigger(const std::array<uint8_t, 10>& bytes, EDSGamepadHand hand)
{
    auto* gamepad = CurrentGamepad();
    if (!gamepad || !gamepad->IsConnected())
    {
        SetStatus(L"No connected DualSense.");
        return false;
    }

    auto* trigger = gamepad->GetIGamepadTrigger();
    if (!trigger)
    {
        SetStatus(L"Adaptive trigger interface unavailable.");
        return false;
    }

    std::vector<uint8_t> data(bytes.begin(), bytes.end());
    trigger->SetCustomTrigger(hand, data);
    gamepad->UpdateOutput();
    return true;
}

void ApplyRumble()
{
    auto* gamepad = CurrentGamepad();
    if (!gamepad || !gamepad->IsConnected())
    {
        SetStatus(L"No connected DualSense.");
        return;
    }

    auto* rumble = gamepad->GetIGamepadRumbles();
    if (!rumble)
    {
        SetStatus(L"Rumble interface unavailable.");
        return;
    }

    const auto left = static_cast<uint8_t>(SendMessageW(gLeftRumble, TBM_GETPOS, 0, 0));
    const auto right = static_cast<uint8_t>(SendMessageW(gRightRumble, TBM_GETPOS, 0, 0));
    rumble->SetVibration(left, right);
    gamepad->UpdateOutput();
}

void StopAll()
{
    auto* gamepad = CurrentGamepad();
    if (!gamepad || !gamepad->IsConnected())
        return;

    if (auto* rumble = gamepad->GetIGamepadRumbles())
        rumble->SetVibration(0, 0);

    if (auto* trigger = gamepad->GetIGamepadTrigger())
    {
        trigger->StopTrigger(EDSGamepadHand::Left);
        trigger->StopTrigger(EDSGamepadHand::Right);
    }

    gamepad->UpdateOutput();
}

HWND AddText(HWND parent, const wchar_t* text, int x, int y, int w, int h, int id = 0)
{
    return CreateWindowExW(0, L"STATIC", text, WS_CHILD | WS_VISIBLE,
                           x, y, w, h, parent, reinterpret_cast<HMENU>(static_cast<INT_PTR>(id)),
                           GetModuleHandleW(nullptr), nullptr);
}

HWND AddButton(HWND parent, const wchar_t* text, int x, int y, int w, int h, int id)
{
    return CreateWindowExW(0, L"BUTTON", text,
                           WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
                           x, y, w, h, parent,
                           reinterpret_cast<HMENU>(static_cast<INT_PTR>(id)),
                           GetModuleHandleW(nullptr), nullptr);
}

LRESULT CALLBACK WindowProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam)
{
    switch (msg)
    {
    case WM_CREATE:
    {
        gStatus = AddText(hwnd, L"Initializing Gamepad-Core...", 20, 20, 520, 28, ID_STATUS);
        AddButton(hwnd, L"Detect now", 555, 16, 110, 30, ID_DETECT);

        AddText(hwnd, L"Rumble", 20, 68, 100, 24);
        AddText(hwnd, L"Left", 20, 103, 50, 22);
        gLeftRumble = CreateWindowExW(0, TRACKBAR_CLASSW, L"",
                                      WS_CHILD | WS_VISIBLE | TBS_AUTOTICKS,
                                      75, 98, 430, 32, hwnd,
                                      reinterpret_cast<HMENU>(static_cast<INT_PTR>(ID_LEFT_RUMBLE)),
                                      GetModuleHandleW(nullptr), nullptr);
        SendMessageW(gLeftRumble, TBM_SETRANGE, TRUE, MAKELONG(0, 255));
        SendMessageW(gLeftRumble, TBM_SETPOS, TRUE, 100);

        AddText(hwnd, L"Right", 20, 143, 50, 22);
        gRightRumble = CreateWindowExW(0, TRACKBAR_CLASSW, L"",
                                       WS_CHILD | WS_VISIBLE | TBS_AUTOTICKS,
                                       75, 138, 430, 32, hwnd,
                                       reinterpret_cast<HMENU>(static_cast<INT_PTR>(ID_RIGHT_RUMBLE)),
                                       GetModuleHandleW(nullptr), nullptr);
        SendMessageW(gRightRumble, TBM_SETRANGE, TRUE, MAKELONG(0, 255));
        SendMessageW(gRightRumble, TBM_SETPOS, TRUE, 100);
        AddButton(hwnd, L"Apply rumble", 520, 105, 145, 44, ID_APPLY_RUMBLE);

        AddText(hwnd, L"Adaptive Trigger Presets", 20, 198, 220, 24);
        AddButton(hwnd, L"Bow  R2", 20, 230, 145, 48, ID_BOW);
        AddButton(hwnd, L"Gallop  L2", 180, 230, 145, 48, ID_GALLOP);
        AddButton(hwnd, L"Weapon  R2", 340, 230, 145, 48, ID_WEAPON);
        AddButton(hwnd, L"Machine  R2", 500, 230, 165, 48, ID_MACHINE);

        AddButton(hwnd, L"STOP ALL", 20, 304, 645, 50, ID_STOP_ALL);
        AddText(hwnd,
                L"Native ARM64 / direct Gamepad-Core HID path. DSX is not required.",
                20, 372, 645, 24);

        try
        {
            test_utils::initialize_test_environment(gHardware, gRegistry);
            gRegistry->RequestImmediateDetection();
            SetStatus(L"Searching for DualSense...");
        }
        catch (...)
        {
            SetStatus(L"Gamepad-Core initialization failed.");
        }

        SetTimer(hwnd, kTimerId, kPollMs, nullptr);
        return 0;
    }

    case WM_TIMER:
        if (wParam == kTimerId)
            RefreshController();
        return 0;

    case WM_COMMAND:
        switch (LOWORD(wParam))
        {
        case ID_DETECT:
            if (gRegistry)
                gRegistry->RequestImmediateDetection();
            SetStatus(L"Detection requested...");
            return 0;

        case ID_APPLY_RUMBLE:
            ApplyRumble();
            return 0;

        case ID_BOW:
            ApplyTrigger({0x22, 0x02, 0x01, 0x3f, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00}, EDSGamepadHand::Right);
            return 0;

        case ID_GALLOP:
            ApplyTrigger({0x23, 0x82, 0x00, 0xf7, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00}, EDSGamepadHand::Left);
            return 0;

        case ID_WEAPON:
            ApplyTrigger({0x25, 0x08, 0x01, 0x07, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00}, EDSGamepadHand::Right);
            return 0;

        case ID_MACHINE:
            ApplyTrigger({0x27, 0x80, 0x02, 0x3a, 0x0a, 0x04, 0x00, 0x00, 0x00, 0x00}, EDSGamepadHand::Right);
            return 0;

        case ID_STOP_ALL:
            StopAll();
            return 0;
        }
        break;

    case WM_DESTROY:
        KillTimer(hwnd, kTimerId);
        StopAll();
        gRegistry.reset();
        PostQuitMessage(0);
        return 0;
    }

    return DefWindowProcW(hwnd, msg, wParam, lParam);
}
} // namespace

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE, PWSTR, int show)
{
    INITCOMMONCONTROLSEX controls{sizeof(controls), ICC_BAR_CLASSES};
    InitCommonControlsEx(&controls);

    const wchar_t* className = L"CemuDualSenseHapticLabWindow";

    WNDCLASSEXW wc{};
    wc.cbSize = sizeof(wc);
    wc.lpfnWndProc = WindowProc;
    wc.hInstance = instance;
    wc.hCursor = LoadCursorW(nullptr, IDC_ARROW);
    wc.hbrBackground = reinterpret_cast<HBRUSH>(COLOR_WINDOW + 1);
    wc.lpszClassName = className;
    wc.style = CS_HREDRAW | CS_VREDRAW;

    if (!RegisterClassExW(&wc))
        return 1;

    HWND hwnd = CreateWindowExW(
        0, className, L"Cemu DualSense Haptic Lab - ARM64",
        WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX,
        CW_USEDEFAULT, CW_USEDEFAULT, 705, 455,
        nullptr, nullptr, instance, nullptr);

    if (!hwnd)
        return 1;

    ShowWindow(hwnd, show);
    UpdateWindow(hwnd);

    MSG msg{};
    while (GetMessageW(&msg, nullptr, 0, 0) > 0)
    {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }

    return static_cast<int>(msg.wParam);
}
