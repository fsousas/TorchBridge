#pragma once
#include <windows.h>
#include <d3d9.h>
#include <cstdint>
#include <vector>
#include "protocol.h"

namespace tb {
// No COM objects survive Reset except the device owned by the game.
class Renderer {
public:
    Renderer() = default;
    ~Renderer();
    Renderer(const Renderer&) = delete;
    Renderer& operator=(const Renderer&) = delete;
    void reset() noexcept;
    void present(IDirect3DDevice9* device, IDirect3DSwapChain9* chain, HWND focus) noexcept;
private:
    HANDLE mapping_ = nullptr, mutex_ = nullptr;
    Header* shared_ = nullptr;
    DWORD last_open_ = 0;
    bool tried_open_ = false;
    std::vector<unsigned char> pixels_;
    Header frame_{};
    IDirect3DTexture9* texture_ = nullptr;
    UINT texture_width_ = 0, texture_height_ = 0;
    std::uint32_t uploaded_sequence_ = 0;
    std::uint32_t uploaded_tick_ = 0;
    bool uploaded_ = false, dynamic_ = false;
    bool connect() noexcept;
    bool read_frame(const D3DSURFACE_DESC&, const D3DPRESENT_PARAMETERS&, const D3DCAPS9&);
    void draw(IDirect3DDevice9*, IDirect3DSurface9*, const D3DSURFACE_DESC&, const D3DCAPS9&);
};
} // namespace tb
