/* SPDX-License-Identifier: MIT */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc, char **argv)
{
    WNDCLASSW cls = {0}; MSG msg; HWND window;
    WCHAR title[256] = L"ProSimA322 Display";
    int expected = argc > 1 ? atoi(argv[1]) : 1;
    if (argc > 2 && !MultiByteToWideChar(CP_UTF8, 0, argv[2], -1, title, 256)) return 2;
    cls.lpfnWndProc = DefWindowProcW;
    cls.hInstance = GetModuleHandleW(NULL);
    cls.lpszClassName = L"FlightdeckSyntheticGuardTest";
    RegisterClassW(&cls);
    window = CreateWindowW(cls.lpszClassName, title, WS_OVERLAPPEDWINDOW,
                           64, 64, 120, 80, NULL, NULL, cls.hInstance, NULL);
    if (!window) return 2;
    ShowWindow(window, SW_SHOWNOACTIVATE);
    for (int i = 0; i < 30; ++i)
    {
        /* Reappearing helpers must remain hidden after their title changes. */
        if (i == 15 && argc > 3)
        {
            if (!MultiByteToWideChar(CP_UTF8, 0, argv[3], -1, title, 256)) return 2;
            SetWindowTextW(window, title);
            ShowWindow(window, SW_SHOWNOACTIVATE);
        }
        while (PeekMessageW(&msg, NULL, 0, 0, PM_REMOVE)) { TranslateMessage(&msg); DispatchMessageW(&msg); }
        if (i == 10 || i == 25)
        {
            printf("host xid=%llu helper=%d logical_visible=%d\n",
                   (unsigned long long)(ULONG_PTR)GetPropW(window, L"__wine_x11_whole_window"),
                   !!GetPropW(window, L"__wine_fenix_helper_window"), !!IsWindowVisible(window));
            fflush(stdout);
        }
        Sleep(100);
    }
    int visible = !!IsWindowVisible(window);
    printf("window_visible=%d expected=%d title=%ls\n", visible, expected, title);
    DestroyWindow(window);
    return visible != expected;
}
