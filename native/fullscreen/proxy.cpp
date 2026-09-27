// A local D3D9 proxy for Torchlight 1 (x86). The system runtime owns every real
// COM resource. Only presentation and Reset add overlay work; all other calls
// forward unchanged. No remote injection, code patching or background thread.
#include <windows.h>
#include <d3d9.h>
#include <atomic>
#include <mutex>
#include <new>
#include <unordered_map>
#include "renderer.h"

namespace {
HMODULE runtime() noexcept {
    static HMODULE module = [] {
        wchar_t path[MAX_PATH];
        UINT size = GetSystemDirectoryW(path, MAX_PATH);
        if (!size || size > MAX_PATH - 12) return static_cast<HMODULE>(nullptr);
        wcscat_s(path, L"\\d3d9.dll");
        return LoadLibraryExW(path, nullptr, LOAD_LIBRARY_SEARCH_SYSTEM32);
    }();
    return module;
}
template<class T> T system_function(const char* name) noexcept {
    HMODULE module = runtime();
    return module ? reinterpret_cast<T>(GetProcAddress(module, name)) : nullptr;
}

class DeviceProxy;
class SwapChainProxy;
class Direct3DProxy final : public IDirect3D9 {
public:
    explicit Direct3DProxy(IDirect3D9* real) : real_(real) {}
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid, void** out) noexcept override {
        if (!out) return E_POINTER;
        if (iid == __uuidof(IUnknown) || iid == __uuidof(IDirect3D9)) {
            *out = static_cast<IDirect3D9*>(this); AddRef(); return S_OK;
        }
        return real_->QueryInterface(iid, out);
    }
    ULONG STDMETHODCALLTYPE AddRef() noexcept override { return ++refs_; }
    ULONG STDMETHODCALLTYPE Release() noexcept override {
        ULONG count = --refs_;
        if (!count) delete this;
        return count;
    }
    HRESULT STDMETHODCALLTYPE CreateDevice(UINT adapter, D3DDEVTYPE type, HWND focus, DWORD flags,
                                            D3DPRESENT_PARAMETERS* params, IDirect3DDevice9** out) noexcept override;
#include "direct3d_forwarders.inc"
private:
    ~Direct3DProxy() { real_->Release(); }
    std::atomic<ULONG> refs_{1};
    IDirect3D9* real_;
};

class DeviceProxy final : public IDirect3DDevice9 {
public:
    DeviceProxy(IDirect3DDevice9* real, IDirect3D9* parent, HWND focus)
        : real_(real), parent_(parent), focus_(focus) { parent_->AddRef(); }
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid, void** out) noexcept override {
        if (!out) return E_POINTER;
        if (iid == __uuidof(IUnknown) || iid == __uuidof(IDirect3DDevice9)) {
            *out = static_cast<IDirect3DDevice9*>(this); AddRef(); return S_OK;
        }
        return real_->QueryInterface(iid, out);
    }
    ULONG STDMETHODCALLTYPE AddRef() noexcept override { return ++refs_; }
    ULONG STDMETHODCALLTYPE Release() noexcept override {
        ULONG count = --refs_;
        if (!count) delete this;
        return count;
    }
    HRESULT STDMETHODCALLTYPE GetDirect3D(IDirect3D9** out) noexcept override {
        if (!out) return D3DERR_INVALIDCALL;
        *out = parent_; parent_->AddRef(); return D3D_OK;
    }
    HRESULT STDMETHODCALLTYPE Reset(D3DPRESENT_PARAMETERS* params) noexcept override {
        std::lock_guard<std::recursive_mutex> guard(mutex_);
        renderer_.reset(); // DEFAULT-pool resources must be released BEFORE Reset.
        return real_->Reset(params);
    }
    HRESULT STDMETHODCALLTYPE Present(const RECT* src, const RECT* dst, HWND window, const RGNDATA* dirty) noexcept override {
        std::lock_guard<std::recursive_mutex> guard(mutex_);
        IDirect3DSwapChain9* chain = nullptr;
        if (SUCCEEDED(real_->GetSwapChain(0, &chain))) {
            renderer_.present(real_, chain, focus_);
            chain->Release();
        }
        return real_->Present(src, dst, window, dirty);
    }
    HRESULT STDMETHODCALLTYPE CreateAdditionalSwapChain(D3DPRESENT_PARAMETERS* params, IDirect3DSwapChain9** out) noexcept override {
        HRESULT result = real_->CreateAdditionalSwapChain(params, out);
        if (SUCCEEDED(result) && out && *out) wrap_chain(out);
        return result;
    }
    HRESULT STDMETHODCALLTYPE GetSwapChain(UINT index, IDirect3DSwapChain9** out) noexcept override {
        HRESULT result = real_->GetSwapChain(index, out);
        if (SUCCEEDED(result) && out && *out) wrap_chain(out);
        return result;
    }
#include "device_forwarders.inc"
private:
    friend class SwapChainProxy;
    ~DeviceProxy() {
        renderer_.reset();
        real_->Release();
        parent_->Release();
    }
    void wrap_chain(IDirect3DSwapChain9** out) noexcept;
    std::atomic<ULONG> refs_{1};
    IDirect3DDevice9* real_;
    IDirect3D9* parent_;
    HWND focus_;
    std::recursive_mutex mutex_;
    // Weak cache: stable COM identity without a device/swap-chain reference cycle.
    std::unordered_map<IDirect3DSwapChain9*, SwapChainProxy*> chains_;
    tb::Renderer renderer_;
};

class SwapChainProxy final : public IDirect3DSwapChain9 {
public:
    SwapChainProxy(IDirect3DSwapChain9* real, DeviceProxy* parent)
        : real_(real), parent_(parent) { parent_->AddRef(); }
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid, void** out) noexcept override {
        if (!out) return E_POINTER;
        if (iid == __uuidof(IUnknown) || iid == __uuidof(IDirect3DSwapChain9)) {
            *out = static_cast<IDirect3DSwapChain9*>(this); AddRef(); return S_OK;
        }
        return real_->QueryInterface(iid, out);
    }
    ULONG STDMETHODCALLTYPE AddRef() noexcept override { return ++refs_; }
    ULONG STDMETHODCALLTYPE Release() noexcept override {
        ULONG count;
        {
            std::lock_guard<std::recursive_mutex> guard(parent_->mutex_);
            count = --refs_;
            if (!count) parent_->chains_.erase(real_);
        }
        if (!count) delete this;
        return count;
    }
    HRESULT STDMETHODCALLTYPE GetDevice(IDirect3DDevice9** out) noexcept override {
        if (!out) return D3DERR_INVALIDCALL;
        *out = parent_; parent_->AddRef(); return D3D_OK;
    }
    HRESULT STDMETHODCALLTYPE Present(const RECT* src, const RECT* dst, HWND window,
                                       const RGNDATA* dirty, DWORD flags) noexcept override {
        std::lock_guard<std::recursive_mutex> guard(parent_->mutex_);
        parent_->renderer_.present(parent_->real_, real_, parent_->focus_);
        return real_->Present(src, dst, window, dirty, flags);
    }
#include "swapchain_forwarders.inc"
private:
    ~SwapChainProxy() { real_->Release(); parent_->Release(); }
    std::atomic<ULONG> refs_{1};
    IDirect3DSwapChain9* real_;
    DeviceProxy* parent_;
};

void DeviceProxy::wrap_chain(IDirect3DSwapChain9** out) noexcept {
    try {
        std::lock_guard<std::recursive_mutex> guard(mutex_);
        auto existing = chains_.find(*out);
        if (existing != chains_.end()) {
            existing->second->AddRef();
            (*out)->Release();
            *out = existing->second;
            return;
        }
        // Allocate the map entry first: an allocation failure leaves the real
        // interface untouched and usable by the game.
        auto entry = chains_.emplace(*out, nullptr).first;
        auto proxy = new (std::nothrow) SwapChainProxy(*out, this);
        if (!proxy) { chains_.erase(entry); return; }
        entry->second = proxy;
        *out = proxy;
    } catch (...) { /* Forward the system interface on allocation failure. */ }
}

HRESULT Direct3DProxy::CreateDevice(UINT adapter, D3DDEVTYPE type, HWND focus, DWORD flags,
                                  D3DPRESENT_PARAMETERS* params, IDirect3DDevice9** out) noexcept {
    HRESULT result = real_->CreateDevice(adapter, type, focus, flags, params, out);
    if (SUCCEEDED(result) && out && *out) {
        try {
            auto proxy = new DeviceProxy(*out, this, focus);
            *out = proxy;
        } catch (...) { /* Creating the overlay must not stop the game starting. */ }
    }
    return result;
}
} // namespace

extern "C" IDirect3D9* WINAPI Direct3DCreate9(UINT sdk) {
    auto create = system_function<decltype(&Direct3DCreate9)>("Direct3DCreate9");
    if (!create) return nullptr;
    IDirect3D9* real = create(sdk);
    if (!real) return nullptr;
    auto proxy = new (std::nothrow) Direct3DProxy(real);
    return proxy ? proxy : real;
}

// Torchlight 1 uses classic D3D9. Ex is forwarded without wrapping; never
// substitute a classic device for a caller explicitly asking for D3D9Ex.
extern "C" HRESULT WINAPI Direct3DCreate9Ex(UINT sdk, IDirect3D9Ex** out) {
    auto create = system_function<decltype(&Direct3DCreate9Ex)>("Direct3DCreate9Ex");
    return create ? create(sdk, out) : D3DERR_NOTAVAILABLE;
}
extern "C" int WINAPI D3DPERF_BeginEvent(D3DCOLOR color, LPCWSTR name) {
    auto fn = system_function<decltype(&D3DPERF_BeginEvent)>("D3DPERF_BeginEvent");
    return fn ? fn(color, name) : -1;
}
extern "C" int WINAPI D3DPERF_EndEvent() {
    auto fn = system_function<decltype(&D3DPERF_EndEvent)>("D3DPERF_EndEvent");
    return fn ? fn() : -1;
}
extern "C" void WINAPI D3DPERF_SetMarker(D3DCOLOR color, LPCWSTR name) {
    auto fn = system_function<decltype(&D3DPERF_SetMarker)>("D3DPERF_SetMarker");
    if (fn) fn(color, name);
}
extern "C" void WINAPI D3DPERF_SetRegion(D3DCOLOR color, LPCWSTR name) {
    auto fn = system_function<decltype(&D3DPERF_SetRegion)>("D3DPERF_SetRegion");
    if (fn) fn(color, name);
}
extern "C" BOOL WINAPI D3DPERF_QueryRepeatFrame() {
    auto fn = system_function<decltype(&D3DPERF_QueryRepeatFrame)>("D3DPERF_QueryRepeatFrame");
    return fn ? fn() : FALSE;
}
extern "C" void WINAPI D3DPERF_SetOptions(DWORD options) {
    auto fn = system_function<decltype(&D3DPERF_SetOptions)>("D3DPERF_SetOptions");
    if (fn) fn(options);
}
extern "C" DWORD WINAPI D3DPERF_GetStatus() {
    auto fn = system_function<decltype(&D3DPERF_GetStatus)>("D3DPERF_GetStatus");
    return fn ? fn() : 0;
}
extern "C" const char* WINAPI TorchBridgeOverlayIdentity() {
    return "TorchBridge.D3D9.Overlay.v1.x86";
}

// Shader validation is also used by D3DX helpers, not just by the executable.
extern "C" void* WINAPI Direct3DShaderValidatorCreate9() {
    auto fn = system_function<void* (WINAPI*)()>("Direct3DShaderValidatorCreate9");
    return fn ? fn() : nullptr;
}
extern "C" void WINAPI DebugSetMute() {
    auto fn = system_function<void (WINAPI*)()>("DebugSetMute");
    if (fn) fn();
}
// These legacy exports have no public SDK signature. Tail forwarding preserves
// the original caller's stack/registers instead of guessing their arguments.
#define RESOLVER(name) \
    extern "C" FARPROC __cdecl tb_resolve_##name() { \
        static FARPROC fn = system_function<FARPROC>(#name); \
        if (!fn) RaiseException(ERROR_PROC_NOT_FOUND, EXCEPTION_NONCONTINUABLE, 0, nullptr); \
        return fn; \
    }
RESOLVER(DebugSetLevel)
RESOLVER(PSGPError)
RESOLVER(PSGPSampleTexture)

#if defined(_MSC_VER)
#define FORWARD(name) \
    extern "C" __declspec(naked) void __cdecl name() { \
        __asm push eax \
        __asm pushfd \
        __asm pushad \
        __asm call tb_resolve_##name \
        __asm mov [esp + 36], eax \
        __asm popad \
        __asm popfd \
        __asm ret \
    }
#else
#define FORWARD(name) \
    extern "C" __attribute__((naked)) void name() { \
        __asm__ __volatile__("pushl %eax\n\tpushfl\n\tpushal\n\t" \
            "call _tb_resolve_" #name "\n\tmovl %eax, 36(%esp)\n\t" \
            "popal\n\tpopfl\n\tret\n\t"); \
    }
#endif
FORWARD(DebugSetLevel)
FORWARD(PSGPError)
FORWARD(PSGPSampleTexture)
#undef FORWARD
#undef RESOLVER
