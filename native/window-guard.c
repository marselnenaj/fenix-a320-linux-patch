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

static BOOL system_title(const WCHAR *title)
{
    static const WCHAR prefix[] = L"FenixSim A320 System ";
    const WCHAR *version;
    if (!wcscmp(title, L"ProSimA322 System")) return TRUE;
    if (wcsncmp(title, prefix, (sizeof(prefix) / sizeof(*prefix)) - 1)) return FALSE;
    version = title + (sizeof(prefix) / sizeof(*prefix)) - 1;
    /* The running helper replaces its initial title with a versioned title.
     * Accept numeric version components only, never account/setup dialogs. */
    for (;;)
    {
        if (*version < L'0' || *version > L'9') return FALSE;
        do { ++version; } while (*version >= L'0' && *version <= L'9');
        if (!*version) return TRUE;
        if (*version++ != L'.') return FALSE;
    }
}

static BOOL CALLBACK hide_helper(HWND window, LPARAM unused)
{
    WCHAR title[256], image[1024], *name;
    DWORD pid, size = 1024;
    HANDLE process;
    const WCHAR *expected;
    (void)unused;
    if (!GetWindowTextW(window, title, 256)) return TRUE;
    if (system_title(title)) expected = L"FenixSystem.exe";
    else if (!wcscmp(title, L"ProSimA322 Display") || !wcscmp(title, L"Fenix Display")) expected = L"FenixDisplay.exe";
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
            /* Preserve WinForms visibility when the X11 driver owns hiding. */
            if (!GetPropW(window, L"__wine_fenix_helper_window") && IsWindowVisible(window))
                ShowWindow(window, SW_HIDE);
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
