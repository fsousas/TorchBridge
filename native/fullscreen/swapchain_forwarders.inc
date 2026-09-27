// Unmodified IDirect3DSwapChain9 calls. Signatures checked by C++ override against the SDK.
HRESULT STDMETHODCALLTYPE GetFrontBufferData(struct IDirect3DSurface9 *pDestSurface) noexcept override { return real_->GetFrontBufferData(pDestSurface); }
HRESULT STDMETHODCALLTYPE GetBackBuffer(UINT iBackBuffer, D3DBACKBUFFER_TYPE Type, struct IDirect3DSurface9 **ppBackBuffer) noexcept override { return real_->GetBackBuffer(iBackBuffer, Type, ppBackBuffer); }
HRESULT STDMETHODCALLTYPE GetRasterStatus(D3DRASTER_STATUS *pRasterStatus) noexcept override { return real_->GetRasterStatus(pRasterStatus); }
HRESULT STDMETHODCALLTYPE GetDisplayMode(D3DDISPLAYMODE *pMode) noexcept override { return real_->GetDisplayMode(pMode); }
HRESULT STDMETHODCALLTYPE GetPresentParameters(D3DPRESENT_PARAMETERS *pPresentationParameters) noexcept override { return real_->GetPresentParameters(pPresentationParameters); }
