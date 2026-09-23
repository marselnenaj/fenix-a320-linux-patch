/* SPDX-License-Identifier: MIT */
#include <windows.h>
#include <stdio.h>
#include <wchar.h>
#include <intrin.h>
int main(void)
{
    BYTE *peb=(BYTE *)__readgsqword(0x60);
    BYTE *ldr=*(BYTE **)(peb+0x18);
    LIST_ENTRY *head=(LIST_ENTRY *)(ldr+0x10);
    for (LIST_ENTRY *entry=head->Flink;entry!=head;entry=entry->Flink) {
        BYTE *module=(BYTE *)entry;
        const WCHAR *name=*(const WCHAR **)(module+0x60);
        if (!_wcsicmp(name,L"kernel32.dll") || !_wcsicmp(name,L"kernelbase.dll")) wprintf(L"%ls\n",name);
    }
    return 0;
}
