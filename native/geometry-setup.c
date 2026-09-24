/* SPDX-License-Identifier: MIT
 * Extract only explicitly named cabinet members and apply Microsoft's delta
 * format. The installer verifies the packages, msdelta library, intermediate
 * files and final DLL before installing anything. No vendor binary is bundled.
 */
#ifndef UNICODE
#define UNICODE
#endif
#define _UNICODE
#include <windows.h>
#include <setupapi.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>

#define MAX_DATA (32 * 1024 * 1024)
typedef struct { void *data; SIZE_T size; BOOL editable; } DeltaInput;
typedef struct { void *data; SIZE_T size; } DeltaOutput;
struct extraction { const WCHAR *member, *target; BOOL found; };

static UINT CALLBACK cabinet_callback(void *context, UINT notification, UINT_PTR a, UINT_PTR b)
{
    struct extraction *job = context;
    (void)b;
    if (notification == SPFILENOTIFY_FILEINCABINET)
    {
        FILE_IN_CABINET_INFO_W *info = (void *)a;
        if (wcscmp(info->NameInCabinet, job->member)) return FILEOP_SKIP;
        if (job->found || info->FileSize > MAX_DATA) return FILEOP_ABORT;
        wcscpy(info->FullTargetName, job->target);
        job->found = TRUE;
        return FILEOP_DOIT;
    }
    if (notification == SPFILENOTIFY_FILEEXTRACTED)
        return ((FILEPATHS_W *)a)->Win32Error;
    if (notification == SPFILENOTIFY_NEEDNEWCABINET) return ERROR_NOT_SUPPORTED;
    return NO_ERROR;
}

static BOOL read_file(const WCHAR *path, DeltaInput *input)
{
    LARGE_INTEGER size;
    DWORD read;
    BOOL ok = FALSE;
    HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (file == INVALID_HANDLE_VALUE) return FALSE;
    if (GetFileSizeEx(file, &size) && size.QuadPart > 0 && size.QuadPart <= MAX_DATA)
    {
        input->size = size.QuadPart;
        input->data = malloc(input->size);
        ok = input->data && ReadFile(file, input->data, input->size, &read, NULL) && read == input->size;
    }
    CloseHandle(file);
    return ok;
}

int wmain(int argc, WCHAR **argv)
{
    if (argc == 5 && !wcscmp(argv[1], L"extract"))
    {
        struct extraction job = {argv[3], argv[4], FALSE};
        if (wcslen(job.target) >= MAX_PATH || GetFileAttributesW(job.target) != INVALID_FILE_ATTRIBUTES)
            return 2;
        if (!SetupIterateCabinetW(argv[2], 0, cabinet_callback, &job) || !job.found)
        {
            fwprintf(stderr, L"Cabinet extraction failed: %lu\n", GetLastError());
            return 3;
        }
        return 0;
    }
    if (argc == 6 && !wcscmp(argv[1], L"delta"))
    {
        DeltaInput source = {0}, patch = {0};
        DeltaOutput result = {0};
        BOOL (WINAPI *apply)(LONGLONG, DeltaInput, DeltaInput, DeltaOutput *);
        BOOL (WINAPI *release)(void *);
        HMODULE library;
        HANDLE output = INVALID_HANDLE_VALUE;
        DWORD written;
        int status = 4;
        /* An absolute, separately checksum-verified library path is required. */
        if (wcslen(argv[2]) < 3 || argv[2][1] != L':' || argv[2][2] != L'\\') return 2;
        library = LoadLibraryExW(argv[2], NULL, LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_SYSTEM32);
        if (!library) return 3;
        apply = (void *)GetProcAddress(library, "ApplyDeltaB");
        release = (void *)GetProcAddress(library, "DeltaFree");
        if (!apply || !release) goto done;
        if (wcscmp(argv[3], L"-") && !read_file(argv[3], &source)) goto done;
        if (!read_file(argv[4], &patch) || !apply(0, source, patch, &result)) goto done;
        if (!result.size || result.size > MAX_DATA) goto done;
        output = CreateFileW(argv[5], GENERIC_WRITE, 0, NULL, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, NULL);
        if (output == INVALID_HANDLE_VALUE) goto done;
        if (!WriteFile(output, result.data, result.size, &written, NULL) || written != result.size ||
            !FlushFileBuffers(output)) goto done;
        status = 0;
done:
        if (status) fwprintf(stderr, L"Delta extraction failed: %lu\n", GetLastError());
        if (output != INVALID_HANDLE_VALUE) CloseHandle(output);
        if (result.data) release(result.data);
        free(source.data);
        free(patch.data);
        FreeLibrary(library);
        return status;
    }
    fputs("Expected extract CAB MEMBER OUTPUT or delta LIBRARY SOURCE|- PATCH OUTPUT\n", stderr);
    return 2;
}
