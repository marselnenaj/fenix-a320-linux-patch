/* SPDX-License-Identifier: MIT
 * A bounded pair of normal MCDU brightness inputs through the simulator's
 * installed SimConnect library. No aircraft/page keys or vendor memory writes.
 */
#ifndef UNICODE
#define UNICODE
#endif
#define _UNICODE
#include <windows.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

typedef HRESULT (WINAPI *OPEN)(HANDLE*,LPCSTR,HWND,DWORD,HANDLE,DWORD);
typedef HRESULT (WINAPI *ADD)(HANDLE,DWORD,LPCSTR,LPCSTR,DWORD,float,DWORD);
typedef HRESULT (WINAPI *REQUEST)(HANDLE,DWORD,DWORD,DWORD,DWORD,DWORD,DWORD,DWORD,DWORD);
typedef HRESULT (WINAPI *GET)(HANDLE,void**,DWORD*);
typedef HRESULT (WINAPI *SET)(HANDLE,DWORD,DWORD,DWORD,DWORD,DWORD,void*);
typedef HRESULT (WINAPI *CLOSE)(HANDLE);
static REQUEST request;
static GET get;
static SET set;
static DWORD sequence;

static int sample(HANDLE client, double values[6])
{
    DWORD id = ++sequence;
    ULONGLONG deadline = GetTickCount64() + 2000;
    if (FAILED(request(client, id, 1, 0, 1, 0, 0, 0, 0))) return 0;
    while (GetTickCount64() < deadline)
    {
        void *packet = NULL;
        DWORD length = 0;
        if (SUCCEEDED(get(client, &packet, &length)) && length >= 12)
        {
            DWORD *words = packet;
            if (words[2] == 1 || words[2] == 3) return 0; /* exception / quit */
            if (words[2] == 8 && length >= 88 && words[3] == id)
            {
                memcpy(values, (char *)packet + 40, 48);
                for (unsigned i = 0; i < 6; ++i)
                    if (!isfinite(values[i]) || values[i] < 0 || values[i] > 1.001) return 0;
                return 1;
            }
        }
        Sleep(5);
    }
    return 0;
}

static int buttons(HANDLE client, const double values[4])
{
    return SUCCEEDED(set(client, 2, 0, 0, 0, sizeof(double) * 4, (void *)values));
}

static int same(double a, double b) { return fabs(a - b) < 0.000001; }

int wmain(int argc, WCHAR **argv)
{
    static const char *names[] = {"L:N_CDU1_BRIGHTNESS", "L:N_CDU2_BRIGHTNESS",
        "L:S_CDU1_BRIGHTNESS_DOWN", "L:S_CDU1_BRIGHTNESS_UP",
        "L:S_CDU2_BRIGHTNESS_DOWN", "L:S_CDU2_BRIGHTNESS_UP"};
    double before[6], current[6], press[4] = {0}, release[4] = {0}, reverse[4] = {0};
    int status = 1, changed[2] = {0}, initial[2], needed[2];
    HANDLE client = NULL;
    HMODULE library;
    OPEN open;
    ADD add;
    CLOSE close;
    if (argc != 3 || (wcscmp(argv[1], L"--probe") && wcscmp(argv[1], L"--refresh"))) return 2;
    /* The caller supplies the absolute path to the user's installed game DLL.
     * This patch never downloads or redistributes Microsoft SimConnect. */
    if (!(library = LoadLibraryExW(argv[2], NULL, LOAD_WITH_ALTERED_SEARCH_PATH))) return 3;
    open = (OPEN)GetProcAddress(library, "SimConnect_Open");
    add = (ADD)GetProcAddress(library, "SimConnect_AddToDataDefinition");
    request = (REQUEST)GetProcAddress(library, "SimConnect_RequestDataOnSimObject");
    get = (GET)GetProcAddress(library, "SimConnect_GetNextDispatch");
    set = (SET)GetProcAddress(library, "SimConnect_SetDataOnSimObject");
    close = (CLOSE)GetProcAddress(library, "SimConnect_Close");
    if (!open || !add || !request || !get || !set || !close) return 4;
    if (FAILED(open(&client, "Flightdeck MCDU display refresh", NULL, 0, NULL, 0))) return 5;
    for (unsigned i = 0; i < 6; ++i)
        if (FAILED(add(client, 1, names[i], "number", 4, 0, 0xffffffffu))) goto done;
    for (unsigned i = 0; i < 4; ++i)
        if (FAILED(add(client, 2, names[i + 2], "number", 4, 0, 0xffffffffu))) goto done;
    if (!sample(client, before)) goto done;
    /* Never compete with an already held pilot/hardware brightness button. */
    for (unsigned i = 2; i < 6; ++i) if (before[i] != 0) goto done;
    if (!wcscmp(argv[1], L"--probe")) { status = 0; goto done; }
    for (unsigned i = 0; i < 2; ++i)
    {
        /* A Home Cockpit Mode round-trip already redraws dimmed units. Only
         * near-maximum units can retain the same 255-valued display input. */
        needed[i] = before[i] > 0.95;
        if (!needed[i]) { changed[i] = 1; continue; }
        /* Move toward the middle to avoid clipping at either brightness limit. */
        initial[i] = before[i] <= 0.5 ? 1 : 0;
        press[i * 2 + initial[i]] = 1;
    }
    if (!needed[0] && !needed[1]) { status = 0; goto done; }
    if (!buttons(client, press)) goto reset;
    Sleep(150);
    if (!buttons(client, release)) goto reset;
    Sleep(150);
    if (!sample(client, current)) goto reset;
    for (unsigned i = 0; i < 2; ++i)
    {
        if (!needed[i]) continue;
        double delta = current[i] - before[i];
        /* One normal key step is 25 * 4 / 1023. Unexpected changes may be
         * pilot input: do not try to chase or overwrite an unknown setting. */
        if (fabs(delta - (initial[i] ? 1 : -1) * 100.0 / 1023.0) < 0.000001)
        {
            changed[i] = 1;
            reverse[i * 2 + !initial[i]] = 1;
        }
    }
    if (!buttons(client, reverse)) goto reset;
    Sleep(150);
    if (!buttons(client, release)) goto reset;
    Sleep(150);
    if (sample(client, current) && changed[0] && changed[1] &&
        same(before[0], current[0]) && same(before[1], current[1])) status = 0;
reset:
    buttons(client, release);
    Sleep(100); /* Let the simulator consume the releases before closing. */
done:
    close(client);
    FreeLibrary(library);
    puts(status ? "MCDU refresh unavailable; no page input sent" : "MCDU brightness verified");
    return status;
}
