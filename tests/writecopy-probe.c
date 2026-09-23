/* SPDX-License-Identifier: MIT */
#include <windows.h>
#include <stdio.h>
static int failures;
static void query(void *p, DWORD expected, const char *stage) {
 MEMORY_BASIC_INFORMATION m;
 if(!VirtualQuery(p,&m,sizeof(m))) {failures++; return;}
 printf("%s protect=%lx expected=%lx type=%lx size=%llu\n",stage,m.Protect,expected,m.Type,(unsigned long long)m.RegionSize);
 if(m.Protect!=expected || m.Type!=MEM_MAPPED)failures++;
}
int main(void) {
 SYSTEM_INFO si;GetSystemInfo(&si);
 char temp[MAX_PATH],path[MAX_PATH];GetTempPathA(MAX_PATH,temp);GetTempFileNameA(temp,"cow",0,path);
 HANDLE f=CreateFileA(path,GENERIC_READ|GENERIC_WRITE,0,NULL,CREATE_ALWAYS,FILE_ATTRIBUTE_TEMPORARY|FILE_FLAG_DELETE_ON_CLOSE,NULL);
 if(f==INVALID_HANDLE_VALUE)return 2;
 SetFilePointer(f,si.dwPageSize*2,NULL,FILE_BEGIN);SetEndOfFile(f);
 HANDLE map=CreateFileMappingA(f,NULL,PAGE_READWRITE,0,0,NULL);
 volatile BYTE *p=MapViewOfFile(map,FILE_MAP_COPY,0,0,si.dwPageSize*2);
 if(!p)return 3;
 query((void*)p,PAGE_WRITECOPY,"before");p[0]=0x37;
 query((void*)p,PAGE_READWRITE,"written");query((void*)(p+si.dwPageSize),PAGE_WRITECOPY,"untouched");
 DWORD old;VirtualProtect((void*)p,si.dwPageSize,PAGE_WRITECOPY,&old);
 query((void*)p,PAGE_WRITECOPY,"rearmed");p[0]=0x38;query((void*)p,PAGE_READWRITE,"written-again");
 BYTE disk=0xff;DWORD n;SetFilePointer(f,0,NULL,FILE_BEGIN);ReadFile(f,&disk,1,&n,NULL);
 printf("file-byte=%u mapped-byte=%u\n",disk,p[0]);if(disk!=0 || p[0]!=0x38)failures++;
 UnmapViewOfFile((void*)p);CloseHandle(map);CloseHandle(f);
 printf("failures=%d\n",failures);return failures?1:0;
}
