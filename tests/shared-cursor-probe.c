/* SPDX-License-Identifier: MIT */
/* A WebView child selects a cursor that the native-window owner must read. */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int child(HCURSOR cursor, unsigned int resource, int destroyed)
{
    ICONINFOEXA info = { .cbSize = sizeof(info) };
    BITMAP bitmap;
    BYTE bits[256];
    BOOL ok = GetIconInfoExA(cursor, &info);
    if (destroyed) return ok ? 1 : 0;
    if (!ok || info.fIcon || !info.hbmMask || info.wResID != resource) return 2;
    if (resource)
    {
        if (!info.szModName[0] || !info.hbmColor) return 3;
    }
    else
    {
        if (info.hbmColor || info.szModName[0] || info.szResName[0] ||
            info.xHotspot != 3 || info.yHotspot != 5) return 4;
        if (!GetObjectA(info.hbmMask, sizeof(bitmap), &bitmap) ||
            bitmap.bmWidth != 32 || bitmap.bmHeight != 64) return 5;
        if (GetBitmapBits(info.hbmMask, sizeof(bits), bits) != sizeof(bits)) return 6;
        for (unsigned int i = 0; i < sizeof(bits); ++i)
            if (bits[i] != (i < 128 ? 0xff : 0)) return 7;
    }
    DeleteObject(info.hbmColor);
    DeleteObject(info.hbmMask);
    return 0;
}

static int check_child(HCURSOR cursor, unsigned int resource, int destroyed)
{
    char executable[MAX_PATH], command[MAX_PATH + 100];
    STARTUPINFOA startup = { .cb = sizeof(startup) };
    PROCESS_INFORMATION process;
    DWORD code = 1;
    GetModuleFileNameA(NULL, executable, sizeof(executable));
    snprintf(command, sizeof(command), "\"%s\" child %llu %u %d", executable,
             (unsigned long long)(ULONG_PTR)cursor, resource, destroyed);
    if (!CreateProcessA(NULL, command, NULL, NULL, FALSE, 0, NULL, NULL, &startup, &process)) return 8;
    if (WaitForSingleObject(process.hProcess, 10000) != WAIT_OBJECT_0)
        TerminateProcess(process.hProcess, 9);
    else GetExitCodeProcess(process.hProcess, &code);
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    if (code) fprintf(stderr, "cross-process cursor %u failed: %lu\n", resource, code);
    return code;
}

int main(int argc, char **argv)
{
    static const WORD resources[] = {32512, 32513, 32649};
    BYTE bits[256];
    ICONINFO info = { .xHotspot = 3, .yHotspot = 5 };
    HCURSOR cursor;
    int result;
    if (argc == 5 && !strcmp(argv[1], "child"))
        return child((HCURSOR)(ULONG_PTR)strtoull(argv[2], NULL, 10), atoi(argv[3]), atoi(argv[4]));
    for (unsigned int i = 0; i < sizeof(resources) / sizeof(resources[0]); ++i)
    {
        cursor = LoadCursorA(NULL, MAKEINTRESOURCEA(resources[i]));
        if (!cursor) return 10;
        SetCursor(cursor);
        if ((result = check_child(cursor, resources[i], 0))) return result;
    }
    memset(bits, 0xff, 128);
    memset(bits + 128, 0, 128);
    info.hbmMask = CreateBitmap(32, 64, 1, 1, bits);
    cursor = CreateIconIndirect(&info);
    DeleteObject(info.hbmMask);
    if (!cursor) return 11;
    SetCursor(cursor);
    if ((result = check_child(cursor, 0, 0))) return result;
    SetCursor(NULL);
    DestroyCursor(cursor);
    if ((result = check_child(cursor, 0, 1))) return result;
    puts("PASS: shared arrow, text, hand, monochrome hotspot/bitmap and destroyed cursor");
    return 0;
}
