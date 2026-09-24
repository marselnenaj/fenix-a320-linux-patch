/* SPDX-License-Identifier: MIT
 * Synthetic SimConnect endpoint for brightness boundaries and pilot input.
 * Contains no Microsoft code and does not connect to a simulator.
 */
#include <windows.h>
#include <stdio.h>
#include <string.h>
static int brightness[2], original[2], inputs, held, pending, refused;
static DWORD request_id;
static double keys[4];
__declspec(dllexport) HRESULT WINAPI SimConnect_Open(HANDLE *client,LPCSTR name,HWND w,DWORD m,HANDLE e,DWORD c)
{
    char mode[32];
    GetEnvironmentVariableA("FENIX_TEST_CASE", mode, sizeof(mode));
    brightness[0] = brightness[1] = 255;
    if (!strcmp(mode,"near-max")) brightness[0] = brightness[1] = 250;
    if (!strcmp(mode,"mixed")) brightness[1] = 127;
    if (!strcmp(mode,"dim")) { brightness[0] = 0; brightness[1] = 127; }
    held = !strcmp(mode,"held");
    refused = !strcmp(mode,"refused");
    if (held) keys[0] = 1;
    original[0] = brightness[0]; original[1] = brightness[1];
    *client = (HANDLE)1;
    return S_OK;
}
__declspec(dllexport) HRESULT WINAPI SimConnect_AddToDataDefinition(HANDLE c,DWORD d,LPCSTR n,LPCSTR u,DWORD t,float e,DWORD i) { return S_OK; }
__declspec(dllexport) HRESULT WINAPI SimConnect_RequestDataOnSimObject(HANDLE c,DWORD r,DWORD d,DWORD o,DWORD p,DWORD f,DWORD a,DWORD i,DWORD l)
{ request_id = r; pending = 1; return S_OK; }
__declspec(dllexport) HRESULT WINAPI SimConnect_GetNextDispatch(HANDLE c,void **data,DWORD *size)
{
    static struct {DWORD header[10];double values[6];} packet;
    if (!pending) return E_FAIL;
    memset(&packet,0,sizeof(packet));
    packet.header[0] = sizeof(packet); packet.header[2] = 8; packet.header[3] = request_id;
    for (unsigned i=0;i<2;++i) packet.values[i] = brightness[i] * 4.0 / 1023.0;
    memcpy(packet.values+2,keys,sizeof(keys));
    *data = &packet; *size = sizeof(packet); pending = 0;
    return S_OK;
}
__declspec(dllexport) HRESULT WINAPI SimConnect_SetDataOnSimObject(HANDLE c,DWORD d,DWORD o,DWORD f,DWORD a,DWORD n,void *data)
{
    const double *values = data;
    if (n != sizeof(keys)) return E_FAIL;
    for(unsigned i=0;i<4;++i)
    {
        if (values[i] && !keys[i])
        {
            ++inputs;
            if (!refused)
            {
                int *value = &brightness[i/2];
                *value += i%2 ? 25 : -25;
                if (*value < 0) *value = 0;
                if (*value > 255) *value = 255;
            }
        }
        keys[i] = values[i];
    }
    return S_OK;
}
__declspec(dllexport) HRESULT WINAPI SimConnect_Close(HANDLE c)
{
    printf("fixture initial=%d,%d final=%d,%d inputs=%d released=%d\n",
        original[0],original[1],brightness[0],brightness[1],inputs,
        held || (keys[0]==0 && keys[1]==0 && keys[2]==0 && keys[3]==0));
    return S_OK;
}
