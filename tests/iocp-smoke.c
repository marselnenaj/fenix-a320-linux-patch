/* SPDX-License-Identifier: MIT */
#include <windows.h>
#include <stdio.h>
static HANDLE port;
static volatile LONG received,failed;
static DWORD WINAPI worker(void *unused) {
 DWORD bytes;ULONG_PTR key;OVERLAPPED *over;
 for(;;) { if(!GetQueuedCompletionStatus(port,&bytes,&key,&over,15000)) {InterlockedIncrement(&failed);break;}
 if(key==9999)break;
 if(bytes!=17 || key!=123 || over!=(OVERLAPPED*)(ULONG_PTR)456)InterlockedIncrement(&failed);
 InterlockedIncrement(&received); }
 return 0;
}
int main(void) {
 HANDLE threads[32];
 for(int round=0;round<30;round++) {
  port=CreateIoCompletionPort(INVALID_HANDLE_VALUE,NULL,0,0);if(!port)return 2;
  for(int i=0;i<32;i++)threads[i]=CreateThread(NULL,0,worker,NULL,0,NULL);
  for(int i=0;i<1000;i++)if(!PostQueuedCompletionStatus(port,17,123,(OVERLAPPED*)(ULONG_PTR)456))return 3;
  for(int i=0;i<32;i++)PostQueuedCompletionStatus(port,0,9999,NULL);
  if(WaitForMultipleObjects(32,threads,TRUE,20000)!=WAIT_OBJECT_0)return 4;
  for(int i=0;i<32;i++)CloseHandle(threads[i]);
  CloseHandle(port);
 }
 printf("IOCP received=%ld expected=30000 failures=%ld threads=960\n",received,failed);
 return failed || received!=30000;
}
