/* SPDX-License-Identifier: MIT */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc, char **argv)
{
    WNDCLASSW cls = {0}; MSG msg; HWND window;
    int expected = argc > 1 ? atoi(argv[1]) : 1;
    cls.lpfnWndProc = DefWindowProcW;
    cls.hInstance = GetModuleHandleW(NULL);
    cls.lpszClassName = L"FlightdeckSyntheticGuardTest";
    RegisterClassW(&cls);
    window = CreateWindowW(cls.lpszClassName, L"ProSimA322 Display", WS_OVERLAPPEDWINDOW,
                           -32000, -32000, 40, 40, NULL, NULL, cls.hInstance, NULL);
    if (!window) return 2;
    ShowWindow(window, SW_SHOWNOACTIVATE);
    for (int i = 0; i < 30; ++i)
    {
        while (PeekMessageW(&msg, NULL, 0, 0, PM_REMOVE)) { TranslateMessage(&msg); DispatchMessageW(&msg); }
        Sleep(100);
    }
    int visible = !!IsWindowVisible(window);
    printf("window_visible=%d expected=%d\n", visible, expected);
    DestroyWindow(window);
    return visible != expected;
}
