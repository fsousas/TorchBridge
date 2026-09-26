#include "renderer.h"
#include <algorithm>
#include <array>
#include <cstring>
#include <cwchar>

namespace tb {
namespace {
template<class T> struct ComPtr {
    T* p = nullptr;
    ~ComPtr() { if (p) p->Release(); }
    T* operator->() const { return p; }
};
struct Unlock {
    HANDLE mutex;
    ~Unlock() { ReleaseMutex(mutex); }
};

// D3DSBT_ALL does not save render targets/depth surfaces. Restore them before
// applying the state block, because SetRenderTarget also changes the viewport.
class SavedState {
public:
    SavedState(IDirect3DDevice9* device, UINT targets) : device_(device), count_(targets) {
        if (FAILED(device_->CreateStateBlock(D3DSBT_ALL, &state_.p)) ||
            FAILED(state_->Capture())) return;
        if (FAILED(device_->GetRenderTarget(0, &targets_[0].p))) return;
        for (UINT i = 1; i < count_; ++i) device_->GetRenderTarget(i, &targets_[i].p);
        device_->GetDepthStencilSurface(&depth_.p);
        valid = true;
    }
    ~SavedState() {
        if (!valid) return;
        for (UINT i = 0; i < count_; ++i) device_->SetRenderTarget(i, targets_[i].p);
        device_->SetDepthStencilSurface(depth_.p);
        state_->Apply();
    }
    bool valid = false;
private:
    IDirect3DDevice9* device_;
    UINT count_;
    ComPtr<IDirect3DStateBlock9> state_;
    std::array<ComPtr<IDirect3DSurface9>, 4> targets_;
    ComPtr<IDirect3DSurface9> depth_;
};
UINT texture_extent(UINT value, const D3DCAPS9& caps) {
    if (!(caps.TextureCaps & D3DPTEXTURECAPS_POW2)) return value;
    UINT result = 1;
    while (result < value) result *= 2;
    return result;
}
} // namespace

Renderer::~Renderer() {
    reset();
    if (shared_) UnmapViewOfFile(shared_);
    if (mapping_) CloseHandle(mapping_);
    if (mutex_) CloseHandle(mutex_);
}

void Renderer::reset() noexcept {
    if (texture_) texture_->Release();
    texture_ = nullptr;
    uploaded_ = false;
}

bool Renderer::connect() noexcept {
    if (shared_) return true;
    DWORD now = GetTickCount();
    if (tried_open_ && now - last_open_ < 1000) return false;
    tried_open_ = true;
    last_open_ = now;
    wchar_t name[96];
    swprintf(name, 96, L"Local\\TorchBridge.Overlay.v1.%lu", GetCurrentProcessId());
    mapping_ = OpenFileMappingW(FILE_MAP_ALL_ACCESS, FALSE, name);
    if (!mapping_) return false;
    shared_ = static_cast<Header*>(MapViewOfFile(mapping_, FILE_MAP_ALL_ACCESS, 0, 0, map_size));
    wcscat_s(name, L".Mutex");
    mutex_ = OpenMutexW(SYNCHRONIZE | MUTEX_MODIFY_STATE, FALSE, name);
    if (shared_ && mutex_) return true;
    if (shared_) UnmapViewOfFile(shared_);
    if (mutex_) CloseHandle(mutex_);
    CloseHandle(mapping_);
    shared_ = nullptr;
    mapping_ = mutex_ = nullptr;
    return false;
}

bool Renderer::read_frame(const D3DSURFACE_DESC& desc, const D3DPRESENT_PARAMETERS& params,
                          const D3DCAPS9& caps) {
    if (!connect()) return false;
    DWORD wait = WaitForSingleObject(mutex_, 0);
    if (wait != WAIT_OBJECT_0 && wait != WAIT_ABANDONED)
        return !params.Windowed && !pixels_.empty() && valid_frame(frame_, GetTickCount());
    Unlock unlock{mutex_};
    if (!valid_protocol(*shared_)) return false;
    if (wait == WAIT_ABANDONED) shared_->visible = 0;
    DWORD now = GetTickCount();
    shared_->consumer_tick = now;
    shared_->backbuffer_width = desc.Width;
    shared_->backbuffer_height = desc.Height;
    shared_->fullscreen = !params.Windowed;
    shared_->ready = 1;
    shared_->max_width = caps.MaxTextureWidth;
    shared_->max_height = caps.MaxTextureHeight;
    if (params.Windowed || !valid_frame(*shared_, now) ||
        shared_->width > caps.MaxTextureWidth || shared_->height > caps.MaxTextureHeight) {
        frame_.visible = 0;
        return false;
    }
    if (pixels_.empty() || shared_->sequence != frame_.sequence ||
        shared_->producer_tick != frame_.producer_tick ||
        shared_->width != frame_.width || shared_->height != frame_.height) {
        frame_ = *shared_;
        pixels_.resize(static_cast<std::size_t>(frame_.stride) * frame_.height);
        std::memcpy(pixels_.data(), shared_ + 1, pixels_.size());
    }
    return true;
}

void Renderer::present(IDirect3DDevice9* device, IDirect3DSwapChain9* chain, HWND focus) noexcept {
    // No exceptions may cross the game's COM boundary, including allocation failure.
    try {
        D3DPRESENT_PARAMETERS params{};
        D3DSURFACE_DESC desc{};
        D3DCAPS9 caps{};
        ComPtr<IDirect3DSurface9> backbuffer;
        if (FAILED(chain->GetPresentParameters(&params)) ||
            FAILED(chain->GetBackBuffer(0, D3DBACKBUFFER_TYPE_MONO, &backbuffer.p)) ||
            FAILED(backbuffer->GetDesc(&desc)) || FAILED(device->GetDeviceCaps(&caps))) return;
        if (!read_frame(desc, params, caps)) return;
        HWND target = params.hDeviceWindow ? params.hDeviceWindow : focus;
        if (!target || IsIconic(target) ||
            GetAncestor(GetForegroundWindow(), GA_ROOT) != GetAncestor(target, GA_ROOT)) return;
        draw(device, backbuffer.p, desc, caps);
    } catch (...) {
        reset();
    }
}

void Renderer::draw(IDirect3DDevice9* device, IDirect3DSurface9* backbuffer,
                    const D3DSURFACE_DESC& desc, const D3DCAPS9& caps) {
    UINT tw = texture_extent(frame_.width, caps), th = texture_extent(frame_.height, caps);
    if (caps.TextureCaps & D3DPTEXTURECAPS_SQUAREONLY) tw = th = std::max(tw, th);
    if (tw > caps.MaxTextureWidth || th > caps.MaxTextureHeight) return;
    if (!texture_ || texture_width_ != tw || texture_height_ != th) {
        reset();
        dynamic_ = true;
        if (FAILED(device->CreateTexture(tw, th, 1, D3DUSAGE_DYNAMIC, D3DFMT_A8R8G8B8,
                                        D3DPOOL_DEFAULT, &texture_, nullptr))) {
            dynamic_ = false;
            if (FAILED(device->CreateTexture(tw, th, 1, 0, D3DFMT_A8R8G8B8,
                                            D3DPOOL_MANAGED, &texture_, nullptr))) return;
        }
        texture_width_ = tw;
        texture_height_ = th;
    }
    if (!uploaded_ || uploaded_sequence_ != frame_.sequence || uploaded_tick_ != frame_.producer_tick) {
        D3DLOCKED_RECT locked{};
        if (FAILED(texture_->LockRect(0, &locked, nullptr, dynamic_ ? D3DLOCK_DISCARD : 0))) return;
        for (UINT y = 0; y < th; ++y) {
            auto row = static_cast<unsigned char*>(locked.pBits) + y * locked.Pitch;
            std::memset(row, 0, tw * 4);
            if (y < frame_.height)
                std::memcpy(row, pixels_.data() + y * frame_.stride, frame_.stride);
        }
        texture_->UnlockRect(0);
        uploaded_sequence_ = frame_.sequence;
        uploaded_tick_ = frame_.producer_tick;
        uploaded_ = true;
    }

    SavedState saved(device, std::min<UINT>(4, caps.NumSimultaneousRTs));
    if (!saved.valid || FAILED(device->BeginScene())) return;
    // All paths below must EndScene; draw calls themselves do not throw.
    device->SetDepthStencilSurface(nullptr);
    device->SetRenderTarget(0, backbuffer);
    for (UINT i = 1; i < std::min<UINT>(4, caps.NumSimultaneousRTs); ++i)
        device->SetRenderTarget(i, nullptr);
    D3DVIEWPORT9 viewport{0, 0, desc.Width, desc.Height, 0.0f, 1.0f};
    device->SetViewport(&viewport);
    device->SetVertexShader(nullptr);
    device->SetPixelShader(nullptr);
    device->SetFVF(D3DFVF_XYZRHW | D3DFVF_DIFFUSE | D3DFVF_TEX1);
    device->SetStreamSourceFreq(0, 1);
    device->SetRenderState(D3DRS_ZENABLE, FALSE);
    device->SetRenderState(D3DRS_ZWRITEENABLE, FALSE);
    device->SetRenderState(D3DRS_STENCILENABLE, FALSE);
    device->SetRenderState(D3DRS_ALPHATESTENABLE, FALSE);
    device->SetRenderState(D3DRS_ALPHABLENDENABLE, TRUE);
    device->SetRenderState(D3DRS_SEPARATEALPHABLENDENABLE, FALSE);
    device->SetRenderState(D3DRS_BLENDOP, D3DBLENDOP_ADD);
    device->SetRenderState(D3DRS_SRCBLEND, D3DBLEND_ONE); // Qt premultiplies alpha.
    device->SetRenderState(D3DRS_DESTBLEND, D3DBLEND_INVSRCALPHA);
    device->SetRenderState(D3DRS_CULLMODE, D3DCULL_NONE);
    device->SetRenderState(D3DRS_FILLMODE, D3DFILL_SOLID);
    device->SetRenderState(D3DRS_LIGHTING, FALSE);
    device->SetRenderState(D3DRS_SPECULARENABLE, FALSE);
    device->SetRenderState(D3DRS_VERTEXBLEND, D3DVBF_DISABLE);
    device->SetRenderState(D3DRS_INDEXEDVERTEXBLENDENABLE, FALSE);
    device->SetRenderState(D3DRS_MULTISAMPLEMASK, 0xffffffff);
    device->SetRenderState(D3DRS_FOGENABLE, FALSE);
    device->SetRenderState(D3DRS_SCISSORTESTENABLE, FALSE);
    device->SetRenderState(D3DRS_CLIPPLANEENABLE, 0);
    device->SetRenderState(D3DRS_COLORWRITEENABLE, 0xF);
    device->SetRenderState(D3DRS_SRGBWRITEENABLE, FALSE);
    device->SetRenderState(D3DRS_WRAP0, 0);
    device->SetTexture(0, texture_);
    device->SetTextureStageState(0, D3DTSS_COLOROP, D3DTOP_SELECTARG1);
    device->SetTextureStageState(0, D3DTSS_COLORARG1, D3DTA_TEXTURE);
    device->SetTextureStageState(0, D3DTSS_ALPHAOP, D3DTOP_SELECTARG1);
    device->SetTextureStageState(0, D3DTSS_ALPHAARG1, D3DTA_TEXTURE);
    device->SetTextureStageState(0, D3DTSS_RESULTARG, D3DTA_CURRENT);
    device->SetTextureStageState(0, D3DTSS_TEXCOORDINDEX, 0);
    device->SetTextureStageState(0, D3DTSS_TEXTURETRANSFORMFLAGS, D3DTTFF_DISABLE);
    device->SetTextureStageState(1, D3DTSS_COLOROP, D3DTOP_DISABLE);
    device->SetTextureStageState(1, D3DTSS_ALPHAOP, D3DTOP_DISABLE);
    device->SetSamplerState(0, D3DSAMP_MINFILTER, D3DTEXF_LINEAR);
    device->SetSamplerState(0, D3DSAMP_MAGFILTER, D3DTEXF_LINEAR);
    device->SetSamplerState(0, D3DSAMP_MIPFILTER, D3DTEXF_NONE);
    device->SetSamplerState(0, D3DSAMP_ADDRESSU, D3DTADDRESS_CLAMP);
    device->SetSamplerState(0, D3DSAMP_ADDRESSV, D3DTADDRESS_CLAMP);
    device->SetSamplerState(0, D3DSAMP_SRGBTEXTURE, FALSE);
    struct Vertex { float x, y, z, rhw; DWORD color; float u, v; };
    float right = static_cast<float>(desc.Width) - 0.5f, bottom = static_cast<float>(desc.Height) - 0.5f;
    float u = static_cast<float>(frame_.width) / tw, v = static_cast<float>(frame_.height) / th;
    Vertex vertices[] = {
        {-0.5f, -0.5f, 0, 1, 0xffffffff, 0, 0}, {right, -0.5f, 0, 1, 0xffffffff, u, 0},
        {-0.5f, bottom, 0, 1, 0xffffffff, 0, v}, {right, bottom, 0, 1, 0xffffffff, u, v},
    };
    device->DrawPrimitiveUP(D3DPT_TRIANGLESTRIP, 2, vertices, sizeof(Vertex));
    device->EndScene();
}
} // namespace tb
