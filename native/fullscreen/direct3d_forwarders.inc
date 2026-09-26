// Unmodified IDirect3D9 calls. Signatures checked by C++ override against the SDK.
HRESULT STDMETHODCALLTYPE RegisterSoftwareDevice(void* pInitializeFunction) noexcept override { return real_->RegisterSoftwareDevice(pInitializeFunction); }
UINT STDMETHODCALLTYPE GetAdapterCount() noexcept override { return real_->GetAdapterCount(); }
HRESULT STDMETHODCALLTYPE GetAdapterIdentifier(UINT Adapter, DWORD Flags, D3DADAPTER_IDENTIFIER9* pIdentifier) noexcept override { return real_->GetAdapterIdentifier(Adapter, Flags, pIdentifier); }
UINT STDMETHODCALLTYPE GetAdapterModeCount(UINT Adapter, D3DFORMAT Format) noexcept override { return real_->GetAdapterModeCount(Adapter, Format); }
HRESULT STDMETHODCALLTYPE EnumAdapterModes(UINT Adapter, D3DFORMAT Format, UINT Mode, D3DDISPLAYMODE* pMode) noexcept override { return real_->EnumAdapterModes(Adapter, Format, Mode, pMode); }
HRESULT STDMETHODCALLTYPE GetAdapterDisplayMode(UINT Adapter, D3DDISPLAYMODE* pMode) noexcept override { return real_->GetAdapterDisplayMode(Adapter, pMode); }
HRESULT STDMETHODCALLTYPE CheckDeviceType(UINT iAdapter, D3DDEVTYPE DevType, D3DFORMAT DisplayFormat, D3DFORMAT BackBufferFormat, BOOL bWindowed) noexcept override { return real_->CheckDeviceType(iAdapter, DevType, DisplayFormat, BackBufferFormat, bWindowed); }
HRESULT STDMETHODCALLTYPE CheckDeviceFormat(UINT Adapter, D3DDEVTYPE DeviceType, D3DFORMAT AdapterFormat, DWORD Usage, D3DRESOURCETYPE RType, D3DFORMAT CheckFormat) noexcept override { return real_->CheckDeviceFormat(Adapter, DeviceType, AdapterFormat, Usage, RType, CheckFormat); }
HRESULT STDMETHODCALLTYPE CheckDeviceMultiSampleType(UINT Adapter, D3DDEVTYPE DeviceType, D3DFORMAT SurfaceFormat, BOOL Windowed, D3DMULTISAMPLE_TYPE MultiSampleType, DWORD* pQualityLevels) noexcept override { return real_->CheckDeviceMultiSampleType(Adapter, DeviceType, SurfaceFormat, Windowed, MultiSampleType, pQualityLevels); }
HRESULT STDMETHODCALLTYPE CheckDepthStencilMatch(UINT Adapter, D3DDEVTYPE DeviceType, D3DFORMAT AdapterFormat, D3DFORMAT RenderTargetFormat, D3DFORMAT DepthStencilFormat) noexcept override { return real_->CheckDepthStencilMatch(Adapter, DeviceType, AdapterFormat, RenderTargetFormat, DepthStencilFormat); }
HRESULT STDMETHODCALLTYPE CheckDeviceFormatConversion(UINT Adapter, D3DDEVTYPE DeviceType, D3DFORMAT SourceFormat, D3DFORMAT TargetFormat) noexcept override { return real_->CheckDeviceFormatConversion(Adapter, DeviceType, SourceFormat, TargetFormat); }
HRESULT STDMETHODCALLTYPE GetDeviceCaps(UINT Adapter, D3DDEVTYPE DeviceType, D3DCAPS9* pCaps) noexcept override { return real_->GetDeviceCaps(Adapter, DeviceType, pCaps); }
HMONITOR STDMETHODCALLTYPE GetAdapterMonitor(UINT Adapter) noexcept override { return real_->GetAdapterMonitor(Adapter); }
