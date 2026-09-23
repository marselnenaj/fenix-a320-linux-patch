/* SPDX-License-Identifier: MIT */
#define COBJMACROS
#define CONST_VTABLE
#include <windows.h>
#include <initguid.h>
#include <mmdeviceapi.h>
#include <audiopolicy.h>
#include <stdio.h>

struct notification {
    IAudioSessionNotification iface;
    LONG refs, calls;
    HANDLE event;
};
static HRESULT WINAPI query(IAudioSessionNotification *iface, REFIID iid, void **out)
{
    if (!out) return E_POINTER;
    *out = NULL;
    if (!IsEqualIID(iid, &IID_IUnknown) && !IsEqualIID(iid, &IID_IAudioSessionNotification)) return E_NOINTERFACE;
    *out = iface; IAudioSessionNotification_AddRef(iface); return S_OK;
}
static ULONG WINAPI addref(IAudioSessionNotification *iface)
{
    return InterlockedIncrement(&((struct notification *)iface)->refs);
}
static ULONG WINAPI release(IAudioSessionNotification *iface)
{
    return InterlockedDecrement(&((struct notification *)iface)->refs);
}
static HRESULT WINAPI created(IAudioSessionNotification *iface, IAudioSessionControl *session)
{
    struct notification *n = (struct notification *)iface;
    IAudioSessionControl2 *control = NULL;
    DWORD pid = 0;
    HRESULT hr = IAudioSessionControl_QueryInterface(session, &IID_IAudioSessionControl2, (void **)&control);
    if (SUCCEEDED(hr)) { hr = IAudioSessionControl2_GetProcessId(control, &pid); IAudioSessionControl2_Release(control); }
    printf("callback_session_pid_matches=%d hr=%lx\n", pid == GetCurrentProcessId(), hr);
    InterlockedIncrement(&n->calls); SetEvent(n->event); return S_OK;
}
static const IAudioSessionNotificationVtbl vtable = {query, addref, release, created};
static int failures;
static void check(int ok, const char *name)
{
    printf("%s=%s\n", name, ok ? "pass" : "FAIL");
    if (!ok) ++failures;
}
static void new_session(IAudioSessionManager2 *manager)
{
    GUID guid; IAudioSessionControl *control = NULL;
    CoCreateGuid(&guid);
    HRESULT hr = IAudioSessionManager2_GetAudioSessionControl(manager, &guid, 0, &control);
    check(SUCCEEDED(hr), "create_session");
    if (control) IAudioSessionControl_Release(control);
}
int main(void)
{
    IMMDeviceEnumerator *devices = NULL; IMMDevice *device = NULL;
    IAudioSessionManager2 *manager = NULL; IAudioSessionEnumerator *sessions = NULL;
    HRESULT hr = CoInitializeEx(NULL, COINIT_MULTITHREADED);
    if (FAILED(hr)) return 2;
    hr = CoCreateInstance(&CLSID_MMDeviceEnumerator, NULL, CLSCTX_ALL, &IID_IMMDeviceEnumerator, (void **)&devices);
    if (SUCCEEDED(hr)) hr = IMMDeviceEnumerator_GetDefaultAudioEndpoint(devices, eRender, eMultimedia, &device);
    if (SUCCEEDED(hr)) hr = IMMDevice_Activate(device, &IID_IAudioSessionManager2, CLSCTX_ALL, NULL, (void **)&manager);
    if (FAILED(hr)) { printf("setup_error=%lx\n", hr); return 2; }
    struct notification n = {{&vtable}, 1, 0, CreateEventW(NULL, FALSE, FALSE, NULL)};
    check(IAudioSessionManager2_RegisterSessionNotification(manager, NULL) == E_POINTER, "null_registration");
    hr = IAudioSessionManager2_RegisterSessionNotification(manager, &n.iface);
    check(hr == S_OK, "register");
    printf("register_hr=%lx\n", hr);
    if (FAILED(hr)) return 1;
    check(n.refs == 2, "registration_addref");
    new_session(manager);
    check(WaitForSingleObject(n.event, 200) == WAIT_TIMEOUT, "no_callback_before_getcount");
    hr = IAudioSessionManager2_GetSessionEnumerator(manager, &sessions);
    int count = -1;
    if (SUCCEEDED(hr)) hr = IAudioSessionEnumerator_GetCount(sessions, &count);
    check(SUCCEEDED(hr) && count >= 1, "enumeration");
    new_session(manager);
    check(WaitForSingleObject(n.event, 3000) == WAIT_OBJECT_0 && n.calls == 1, "real_creation_callback");
    check(IAudioSessionManager2_UnregisterSessionNotification(manager, &n.iface) == S_OK, "unregister");
    new_session(manager);
    check(WaitForSingleObject(n.event, 300) == WAIT_TIMEOUT && n.calls == 1, "no_callback_after_unregister");
    IAudioSessionEnumerator_Release(sessions);
    IAudioSessionManager2_Release(manager);
    IMMDevice_Release(device); IMMDeviceEnumerator_Release(devices);
    check(n.refs == 1, "callback_reference_balance");
    CloseHandle(n.event); CoUninitialize();
    printf("failures=%d\n", failures);
    return failures ? 1 : 0;
}
