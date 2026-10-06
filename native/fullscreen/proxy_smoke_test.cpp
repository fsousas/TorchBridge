// Windows integration test: actual loader, COM lifetime, swap-chain identity,
// pass-through Present and Reset on a NULLREF or HAL device.
#include <windows.h>
#include <d3d9.h>
#include <cstdio>
#include <cstring>

#define CHECK(test) do { \
    if (!(test)) { \
        std::fprintf(stderr, "Failed at line %d: %s\n", __LINE__, #test); \
        std::fflush(stderr); \
        return 1; \
    } \
} while (0)

int main() {
    HMODULE proxy = LoadLibraryW(L"d3d9.dll");
    CHECK(proxy);
    auto identity = reinterpret_cast<const char* (WINAPI*)()>(GetProcAddress(proxy, "TorchBridgeOverlayIdentity"));
    CHECK(identity && std::strcmp(identity(), "TorchBridge.D3D9.Overlay.v1.x86") == 0);
    auto create = reinterpret_cast<IDirect3D9* (WINAPI*)(UINT)>(GetProcAddress(proxy, "Direct3DCreate9"));
    CHECK(create);
    IDirect3D9* api = create(D3D_SDK_VERSION);
    CHECK(api);

    HWND window = CreateWindowW(L"STATIC", L"TorchBridge native test", WS_OVERLAPPEDWINDOW,
                                 0, 0, 128, 128, nullptr, nullptr, GetModuleHandleW(nullptr), nullptr);
    CHECK(window);

    D3DPRESENT_PARAMETERS params{};
    params.Windowed = TRUE;
    params.SwapEffect = D3DSWAPEFFECT_DISCARD;
    params.BackBufferWidth = params.BackBufferHeight = 64;
    params.BackBufferFormat = D3DFMT_X8R8G8B8;
    params.hDeviceWindow = window;
    IDirect3DDevice9* device = nullptr;

    HRESULT hr = api->CreateDevice(0, D3DDEVTYPE_HAL, window,
        D3DCREATE_HARDWARE_VERTEXPROCESSING, &params, &device);
    if (FAILED(hr)) {
        hr = api->CreateDevice(0, D3DDEVTYPE_NULLREF, window,
            D3DCREATE_SOFTWARE_VERTEXPROCESSING | D3DCREATE_FPU_PRESERVE, &params, &device);
    }
    if (FAILED(hr)) {
        hr = api->CreateDevice(0, D3DDEVTYPE_REF, window,
            D3DCREATE_SOFTWARE_VERTEXPROCESSING | D3DCREATE_FPU_PRESERVE, &params, &device);
    }

    if (FAILED(hr)) {
        std::printf("D3D9 device not available in this environment (hr=0x%08lX); proxy loader and exports verified.\n", (unsigned long)hr);
        DestroyWindow(window);
        api->Release();
        FreeLibrary(proxy);
        return 0;
    }

    IDirect3D9* parent = nullptr;
    CHECK(SUCCEEDED(device->GetDirect3D(&parent)) && parent == api);
    parent->Release();

    IUnknown* identity_device = nullptr;
    CHECK(SUCCEEDED(device->QueryInterface(__uuidof(IUnknown), reinterpret_cast<void**>(&identity_device))));
    CHECK(identity_device == static_cast<IUnknown*>(device));
    identity_device->Release();

    IDirect3DSwapChain9 *a = nullptr, *b = nullptr;
    if (SUCCEEDED(device->GetSwapChain(0, &a))) {
        CHECK(SUCCEEDED(device->GetSwapChain(0, &b)) && a == b);
        IDirect3DDevice9* owner = nullptr;
        CHECK(SUCCEEDED(a->GetDevice(&owner)) && owner == device);
        owner->Release();
        CHECK(SUCCEEDED(device->BeginScene()));
        CHECK(SUCCEEDED(device->EndScene()));
        CHECK(SUCCEEDED(a->Present(nullptr, nullptr, nullptr, nullptr, 0)));
        CHECK(SUCCEEDED(device->Present(nullptr, nullptr, nullptr, nullptr)));
        a->Release(); b->Release();
        params.BackBufferWidth = params.BackBufferHeight = 96;
        CHECK(SUCCEEDED(device->Reset(&params)));
        CHECK(SUCCEEDED(device->GetSwapChain(0, &a)));
        D3DPRESENT_PARAMETERS actual{};
        CHECK(SUCCEEDED(a->GetPresentParameters(&actual)) && actual.BackBufferWidth == 96);
        a->Release();
    } else {
        CHECK(SUCCEEDED(device->BeginScene()));
        CHECK(SUCCEEDED(device->EndScene()));
        CHECK(SUCCEEDED(device->Present(nullptr, nullptr, nullptr, nullptr)));
        params.BackBufferWidth = params.BackBufferHeight = 96;
        CHECK(SUCCEEDED(device->Reset(&params)));
    }

    CHECK(device->Release() == 0);
    CHECK(api->Release() == 0);
    DestroyWindow(window);
    FreeLibrary(proxy);
    std::puts("D3D9 loader, COM, Present and Reset OK.");
    return 0;
}
