/* SPDX-License-Identifier: MIT
 * Keep only Fenix's rendering/service windows out of the foreground.
 * Process identity AND the observed helper title must match. Main Fenix and
 * installer/account windows are intentionally interactive.
 */
#ifndef UNICODE
#define UNICODE
#endif
#define _UNICODE
#include <windows.h>
#include <wchar.h>

static BOOL CALLBACK hide_helper(HWND window, LPARAM unused)
{
    WCHAR title[256], image[1024], *name;
    DWORD pid, size = 1024;
    HANDLE process;
    const WCHAR *expected;
    (void)unused;
    if (!GetWindowTextW(window, title, 256)) return TRUE;
    if (!wcscmp(title, L"ProSimA322 System")) expected = L"FenixSystem.exe";
    else if (!wcscmp(title, L"ProSimA322 Display")) expected = L"FenixDisplay.exe";
    else if (!wcscmp(title, L"ProSimA322 MCDU")) expected = L"FenixCDU.exe";
    else return TRUE;
    GetWindowThreadProcessId(window, &pid);
    process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pid);
    if (!process) return TRUE;
    if (QueryFullProcessImageNameW(process, 0, image, &size))
    {
        name = wcsrchr(image, L'\\');
        if (name && !_wcsicmp(name + 1, expected))
        {
            SetWindowLongPtrW(window, GWL_EXSTYLE,
                GetWindowLongPtrW(window, GWL_EXSTYLE) | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW);
            if (IsWindowVisible(window)) ShowWindow(window, SW_HIDE);
        }
    }
    CloseHandle(process);
    return TRUE;
}

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, WCHAR *command, int show)
{
    HANDLE unique = CreateMutexW(NULL, TRUE, L"Local\\FlightdeckFenixWindowGuardV1");
    (void)instance; (void)previous; (void)command; (void)show;
    if (!unique || GetLastError() == ERROR_ALREADY_EXISTS) return 0;
    for (;;)
    {
        EnumWindows(hide_helper, 0);
        Sleep(150);
    }
}
