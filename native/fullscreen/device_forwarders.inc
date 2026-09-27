// Unmodified IDirect3DDevice9 calls. Signatures checked by C++ override against the SDK.
HRESULT STDMETHODCALLTYPE TestCooperativeLevel() noexcept override { return real_->TestCooperativeLevel(); }
UINT STDMETHODCALLTYPE GetAvailableTextureMem() noexcept override { return real_->GetAvailableTextureMem(); }
HRESULT STDMETHODCALLTYPE EvictManagedResources() noexcept override { return real_->EvictManagedResources(); }
HRESULT STDMETHODCALLTYPE GetDeviceCaps(D3DCAPS9* pCaps) noexcept override { return real_->GetDeviceCaps(pCaps); }
HRESULT STDMETHODCALLTYPE GetDisplayMode(UINT iSwapChain, D3DDISPLAYMODE* pMode) noexcept override { return real_->GetDisplayMode(iSwapChain, pMode); }
HRESULT STDMETHODCALLTYPE GetCreationParameters(D3DDEVICE_CREATION_PARAMETERS *pParameters) noexcept override { return real_->GetCreationParameters(pParameters); }
HRESULT STDMETHODCALLTYPE SetCursorProperties(UINT XHotSpot, UINT YHotSpot, IDirect3DSurface9* pCursorBitmap) noexcept override { return real_->SetCursorProperties(XHotSpot, YHotSpot, pCursorBitmap); }
void STDMETHODCALLTYPE SetCursorPosition(int X, int Y, DWORD Flags) noexcept override { return real_->SetCursorPosition(X, Y, Flags); }
BOOL STDMETHODCALLTYPE ShowCursor(BOOL bShow) noexcept override { return real_->ShowCursor(bShow); }
UINT STDMETHODCALLTYPE GetNumberOfSwapChains() noexcept override { return real_->GetNumberOfSwapChains(); }
HRESULT STDMETHODCALLTYPE GetBackBuffer(UINT iSwapChain, UINT iBackBuffer, D3DBACKBUFFER_TYPE Type, IDirect3DSurface9** ppBackBuffer) noexcept override { return real_->GetBackBuffer(iSwapChain, iBackBuffer, Type, ppBackBuffer); }
HRESULT STDMETHODCALLTYPE GetRasterStatus(UINT iSwapChain, D3DRASTER_STATUS* pRasterStatus) noexcept override { return real_->GetRasterStatus(iSwapChain, pRasterStatus); }
HRESULT STDMETHODCALLTYPE SetDialogBoxMode(BOOL bEnableDialogs) noexcept override { return real_->SetDialogBoxMode(bEnableDialogs); }
void STDMETHODCALLTYPE SetGammaRamp(UINT swapchain_idx, DWORD flags, const D3DGAMMARAMP *ramp) noexcept override { return real_->SetGammaRamp(swapchain_idx, flags, ramp); }
void STDMETHODCALLTYPE GetGammaRamp(UINT iSwapChain, D3DGAMMARAMP* pRamp) noexcept override { return real_->GetGammaRamp(iSwapChain, pRamp); }
HRESULT STDMETHODCALLTYPE CreateTexture(UINT Width, UINT Height, UINT Levels, DWORD Usage, D3DFORMAT Format, D3DPOOL Pool, IDirect3DTexture9** ppTexture, HANDLE* pSharedHandle) noexcept override { return real_->CreateTexture(Width, Height, Levels, Usage, Format, Pool, ppTexture, pSharedHandle); }
HRESULT STDMETHODCALLTYPE CreateVolumeTexture(UINT Width, UINT Height, UINT Depth, UINT Levels, DWORD Usage, D3DFORMAT Format, D3DPOOL Pool, IDirect3DVolumeTexture9** ppVolumeTexture, HANDLE* pSharedHandle) noexcept override { return real_->CreateVolumeTexture(Width, Height, Depth, Levels, Usage, Format, Pool, ppVolumeTexture, pSharedHandle); }
HRESULT STDMETHODCALLTYPE CreateCubeTexture(UINT EdgeLength, UINT Levels, DWORD Usage, D3DFORMAT Format, D3DPOOL Pool, IDirect3DCubeTexture9** ppCubeTexture, HANDLE* pSharedHandle) noexcept override { return real_->CreateCubeTexture(EdgeLength, Levels, Usage, Format, Pool, ppCubeTexture, pSharedHandle); }
HRESULT STDMETHODCALLTYPE CreateVertexBuffer(UINT Length, DWORD Usage, DWORD FVF, D3DPOOL Pool, IDirect3DVertexBuffer9** ppVertexBuffer, HANDLE* pSharedHandle) noexcept override { return real_->CreateVertexBuffer(Length, Usage, FVF, Pool, ppVertexBuffer, pSharedHandle); }
HRESULT STDMETHODCALLTYPE CreateIndexBuffer(UINT Length, DWORD Usage, D3DFORMAT Format, D3DPOOL Pool, IDirect3DIndexBuffer9** ppIndexBuffer, HANDLE* pSharedHandle) noexcept override { return real_->CreateIndexBuffer(Length, Usage, Format, Pool, ppIndexBuffer, pSharedHandle); }
HRESULT STDMETHODCALLTYPE CreateRenderTarget(UINT Width, UINT Height, D3DFORMAT Format, D3DMULTISAMPLE_TYPE MultiSample, DWORD MultisampleQuality, BOOL Lockable, IDirect3DSurface9** ppSurface, HANDLE* pSharedHandle) noexcept override { return real_->CreateRenderTarget(Width, Height, Format, MultiSample, MultisampleQuality, Lockable, ppSurface, pSharedHandle); }
HRESULT STDMETHODCALLTYPE CreateDepthStencilSurface(UINT Width, UINT Height, D3DFORMAT Format, D3DMULTISAMPLE_TYPE MultiSample, DWORD MultisampleQuality, BOOL Discard, IDirect3DSurface9** ppSurface, HANDLE* pSharedHandle) noexcept override { return real_->CreateDepthStencilSurface(Width, Height, Format, MultiSample, MultisampleQuality, Discard, ppSurface, pSharedHandle); }
HRESULT STDMETHODCALLTYPE UpdateSurface(IDirect3DSurface9 *src_surface, const RECT *src_rect, IDirect3DSurface9 *dst_surface, const POINT *dst_point) noexcept override { return real_->UpdateSurface(src_surface, src_rect, dst_surface, dst_point); }
HRESULT STDMETHODCALLTYPE UpdateTexture(IDirect3DBaseTexture9* pSourceTexture, IDirect3DBaseTexture9* pDestinationTexture) noexcept override { return real_->UpdateTexture(pSourceTexture, pDestinationTexture); }
HRESULT STDMETHODCALLTYPE GetRenderTargetData(IDirect3DSurface9* pRenderTarget, IDirect3DSurface9* pDestSurface) noexcept override { return real_->GetRenderTargetData(pRenderTarget, pDestSurface); }
HRESULT STDMETHODCALLTYPE GetFrontBufferData(UINT iSwapChain, IDirect3DSurface9* pDestSurface) noexcept override { return real_->GetFrontBufferData(iSwapChain, pDestSurface); }
HRESULT STDMETHODCALLTYPE StretchRect(IDirect3DSurface9 *src_surface, const RECT *src_rect, IDirect3DSurface9 *dst_surface, const RECT *dst_rect, D3DTEXTUREFILTERTYPE filter) noexcept override { return real_->StretchRect(src_surface, src_rect, dst_surface, dst_rect, filter); }
HRESULT STDMETHODCALLTYPE ColorFill(IDirect3DSurface9 *surface, const RECT *rect, D3DCOLOR color) noexcept override { return real_->ColorFill(surface, rect, color); }
HRESULT STDMETHODCALLTYPE CreateOffscreenPlainSurface(UINT Width, UINT Height, D3DFORMAT Format, D3DPOOL Pool, IDirect3DSurface9** ppSurface, HANDLE* pSharedHandle) noexcept override { return real_->CreateOffscreenPlainSurface(Width, Height, Format, Pool, ppSurface, pSharedHandle); }
HRESULT STDMETHODCALLTYPE SetRenderTarget(DWORD RenderTargetIndex, IDirect3DSurface9* pRenderTarget) noexcept override { return real_->SetRenderTarget(RenderTargetIndex, pRenderTarget); }
HRESULT STDMETHODCALLTYPE GetRenderTarget(DWORD RenderTargetIndex, IDirect3DSurface9** ppRenderTarget) noexcept override { return real_->GetRenderTarget(RenderTargetIndex, ppRenderTarget); }
HRESULT STDMETHODCALLTYPE SetDepthStencilSurface(IDirect3DSurface9* pNewZStencil) noexcept override { return real_->SetDepthStencilSurface(pNewZStencil); }
HRESULT STDMETHODCALLTYPE GetDepthStencilSurface(IDirect3DSurface9** ppZStencilSurface) noexcept override { return real_->GetDepthStencilSurface(ppZStencilSurface); }
HRESULT STDMETHODCALLTYPE BeginScene() noexcept override { return real_->BeginScene(); }
HRESULT STDMETHODCALLTYPE EndScene() noexcept override { return real_->EndScene(); }
HRESULT STDMETHODCALLTYPE Clear(DWORD rect_count, const D3DRECT *rects, DWORD flags, D3DCOLOR color, float z, DWORD stencil) noexcept override { return real_->Clear(rect_count, rects, flags, color, z, stencil); }
HRESULT STDMETHODCALLTYPE SetTransform(D3DTRANSFORMSTATETYPE state, const D3DMATRIX *matrix) noexcept override { return real_->SetTransform(state, matrix); }
HRESULT STDMETHODCALLTYPE GetTransform(D3DTRANSFORMSTATETYPE State, D3DMATRIX* pMatrix) noexcept override { return real_->GetTransform(State, pMatrix); }
HRESULT STDMETHODCALLTYPE MultiplyTransform(D3DTRANSFORMSTATETYPE state, const D3DMATRIX *matrix) noexcept override { return real_->MultiplyTransform(state, matrix); }
HRESULT STDMETHODCALLTYPE SetViewport(const D3DVIEWPORT9 *viewport) noexcept override { return real_->SetViewport(viewport); }
HRESULT STDMETHODCALLTYPE GetViewport(D3DVIEWPORT9* pViewport) noexcept override { return real_->GetViewport(pViewport); }
HRESULT STDMETHODCALLTYPE SetMaterial(const D3DMATERIAL9 *material) noexcept override { return real_->SetMaterial(material); }
HRESULT STDMETHODCALLTYPE GetMaterial(D3DMATERIAL9* pMaterial) noexcept override { return real_->GetMaterial(pMaterial); }
HRESULT STDMETHODCALLTYPE SetLight(DWORD index, const D3DLIGHT9 *light) noexcept override { return real_->SetLight(index, light); }
HRESULT STDMETHODCALLTYPE GetLight(DWORD Index, D3DLIGHT9* arg1) noexcept override { return real_->GetLight(Index, arg1); }
HRESULT STDMETHODCALLTYPE LightEnable(DWORD Index, BOOL Enable) noexcept override { return real_->LightEnable(Index, Enable); }
HRESULT STDMETHODCALLTYPE GetLightEnable(DWORD Index, BOOL* pEnable) noexcept override { return real_->GetLightEnable(Index, pEnable); }
HRESULT STDMETHODCALLTYPE SetClipPlane(DWORD index, const float *plane) noexcept override { return real_->SetClipPlane(index, plane); }
HRESULT STDMETHODCALLTYPE GetClipPlane(DWORD Index, float* pPlane) noexcept override { return real_->GetClipPlane(Index, pPlane); }
HRESULT STDMETHODCALLTYPE SetRenderState(D3DRENDERSTATETYPE State, DWORD Value) noexcept override { return real_->SetRenderState(State, Value); }
HRESULT STDMETHODCALLTYPE GetRenderState(D3DRENDERSTATETYPE State, DWORD* pValue) noexcept override { return real_->GetRenderState(State, pValue); }
HRESULT STDMETHODCALLTYPE CreateStateBlock(D3DSTATEBLOCKTYPE Type, IDirect3DStateBlock9** ppSB) noexcept override { return real_->CreateStateBlock(Type, ppSB); }
HRESULT STDMETHODCALLTYPE BeginStateBlock() noexcept override { return real_->BeginStateBlock(); }
HRESULT STDMETHODCALLTYPE EndStateBlock(IDirect3DStateBlock9** ppSB) noexcept override { return real_->EndStateBlock(ppSB); }
HRESULT STDMETHODCALLTYPE SetClipStatus(const D3DCLIPSTATUS9 *clip_status) noexcept override { return real_->SetClipStatus(clip_status); }
HRESULT STDMETHODCALLTYPE GetClipStatus(D3DCLIPSTATUS9* pClipStatus) noexcept override { return real_->GetClipStatus(pClipStatus); }
HRESULT STDMETHODCALLTYPE GetTexture(DWORD Stage, IDirect3DBaseTexture9** ppTexture) noexcept override { return real_->GetTexture(Stage, ppTexture); }
HRESULT STDMETHODCALLTYPE SetTexture(DWORD Stage, IDirect3DBaseTexture9* pTexture) noexcept override { return real_->SetTexture(Stage, pTexture); }
HRESULT STDMETHODCALLTYPE GetTextureStageState(DWORD Stage, D3DTEXTURESTAGESTATETYPE Type, DWORD* pValue) noexcept override { return real_->GetTextureStageState(Stage, Type, pValue); }
HRESULT STDMETHODCALLTYPE SetTextureStageState(DWORD Stage, D3DTEXTURESTAGESTATETYPE Type, DWORD Value) noexcept override { return real_->SetTextureStageState(Stage, Type, Value); }
HRESULT STDMETHODCALLTYPE GetSamplerState(DWORD Sampler, D3DSAMPLERSTATETYPE Type, DWORD* pValue) noexcept override { return real_->GetSamplerState(Sampler, Type, pValue); }
HRESULT STDMETHODCALLTYPE SetSamplerState(DWORD Sampler, D3DSAMPLERSTATETYPE Type, DWORD Value) noexcept override { return real_->SetSamplerState(Sampler, Type, Value); }
HRESULT STDMETHODCALLTYPE ValidateDevice(DWORD* pNumPasses) noexcept override { return real_->ValidateDevice(pNumPasses); }
HRESULT STDMETHODCALLTYPE SetPaletteEntries(UINT palette_idx, const PALETTEENTRY *entries) noexcept override { return real_->SetPaletteEntries(palette_idx, entries); }
HRESULT STDMETHODCALLTYPE GetPaletteEntries(UINT PaletteNumber, PALETTEENTRY* pEntries) noexcept override { return real_->GetPaletteEntries(PaletteNumber, pEntries); }
HRESULT STDMETHODCALLTYPE SetCurrentTexturePalette(UINT PaletteNumber) noexcept override { return real_->SetCurrentTexturePalette(PaletteNumber); }
HRESULT STDMETHODCALLTYPE GetCurrentTexturePalette(UINT *PaletteNumber) noexcept override { return real_->GetCurrentTexturePalette(PaletteNumber); }
HRESULT STDMETHODCALLTYPE SetScissorRect(const RECT *rect) noexcept override { return real_->SetScissorRect(rect); }
HRESULT STDMETHODCALLTYPE GetScissorRect(RECT* pRect) noexcept override { return real_->GetScissorRect(pRect); }
HRESULT STDMETHODCALLTYPE SetSoftwareVertexProcessing(BOOL bSoftware) noexcept override { return real_->SetSoftwareVertexProcessing(bSoftware); }
BOOL STDMETHODCALLTYPE GetSoftwareVertexProcessing() noexcept override { return real_->GetSoftwareVertexProcessing(); }
HRESULT STDMETHODCALLTYPE SetNPatchMode(float nSegments) noexcept override { return real_->SetNPatchMode(nSegments); }
float STDMETHODCALLTYPE GetNPatchMode() noexcept override { return real_->GetNPatchMode(); }
HRESULT STDMETHODCALLTYPE DrawPrimitive(D3DPRIMITIVETYPE PrimitiveType, UINT StartVertex, UINT PrimitiveCount) noexcept override { return real_->DrawPrimitive(PrimitiveType, StartVertex, PrimitiveCount); }
HRESULT STDMETHODCALLTYPE DrawIndexedPrimitive(D3DPRIMITIVETYPE arg0, INT BaseVertexIndex, UINT MinVertexIndex, UINT NumVertices, UINT startIndex, UINT primCount) noexcept override { return real_->DrawIndexedPrimitive(arg0, BaseVertexIndex, MinVertexIndex, NumVertices, startIndex, primCount); }
HRESULT STDMETHODCALLTYPE DrawPrimitiveUP(D3DPRIMITIVETYPE primitive_type, UINT primitive_count, const void *data, UINT stride) noexcept override { return real_->DrawPrimitiveUP(primitive_type, primitive_count, data, stride); }
HRESULT STDMETHODCALLTYPE DrawIndexedPrimitiveUP(D3DPRIMITIVETYPE primitive_type, UINT min_vertex_idx, UINT vertex_count, UINT primitive_count, const void *index_data, D3DFORMAT index_format, const void *data, UINT stride) noexcept override { return real_->DrawIndexedPrimitiveUP(primitive_type, min_vertex_idx, vertex_count, primitive_count, index_data, index_format, data, stride); }
HRESULT STDMETHODCALLTYPE ProcessVertices(UINT SrcStartIndex, UINT DestIndex, UINT VertexCount, IDirect3DVertexBuffer9* pDestBuffer, IDirect3DVertexDeclaration9* pVertexDecl, DWORD Flags) noexcept override { return real_->ProcessVertices(SrcStartIndex, DestIndex, VertexCount, pDestBuffer, pVertexDecl, Flags); }
HRESULT STDMETHODCALLTYPE CreateVertexDeclaration(const D3DVERTEXELEMENT9 *elements, IDirect3DVertexDeclaration9 **declaration) noexcept override { return real_->CreateVertexDeclaration(elements, declaration); }
HRESULT STDMETHODCALLTYPE SetVertexDeclaration(IDirect3DVertexDeclaration9* pDecl) noexcept override { return real_->SetVertexDeclaration(pDecl); }
HRESULT STDMETHODCALLTYPE GetVertexDeclaration(IDirect3DVertexDeclaration9** ppDecl) noexcept override { return real_->GetVertexDeclaration(ppDecl); }
HRESULT STDMETHODCALLTYPE SetFVF(DWORD FVF) noexcept override { return real_->SetFVF(FVF); }
HRESULT STDMETHODCALLTYPE GetFVF(DWORD* pFVF) noexcept override { return real_->GetFVF(pFVF); }
HRESULT STDMETHODCALLTYPE CreateVertexShader(const DWORD *byte_code, IDirect3DVertexShader9 **shader) noexcept override { return real_->CreateVertexShader(byte_code, shader); }
HRESULT STDMETHODCALLTYPE SetVertexShader(IDirect3DVertexShader9* pShader) noexcept override { return real_->SetVertexShader(pShader); }
HRESULT STDMETHODCALLTYPE GetVertexShader(IDirect3DVertexShader9** ppShader) noexcept override { return real_->GetVertexShader(ppShader); }
HRESULT STDMETHODCALLTYPE SetVertexShaderConstantF(UINT reg_idx, const float *data, UINT count) noexcept override { return real_->SetVertexShaderConstantF(reg_idx, data, count); }
HRESULT STDMETHODCALLTYPE GetVertexShaderConstantF(UINT StartRegister, float* pConstantData, UINT Vector4fCount) noexcept override { return real_->GetVertexShaderConstantF(StartRegister, pConstantData, Vector4fCount); }
HRESULT STDMETHODCALLTYPE SetVertexShaderConstantI(UINT reg_idx, const int *data, UINT count) noexcept override { return real_->SetVertexShaderConstantI(reg_idx, data, count); }
HRESULT STDMETHODCALLTYPE GetVertexShaderConstantI(UINT StartRegister, int* pConstantData, UINT Vector4iCount) noexcept override { return real_->GetVertexShaderConstantI(StartRegister, pConstantData, Vector4iCount); }
HRESULT STDMETHODCALLTYPE SetVertexShaderConstantB(UINT reg_idx, const BOOL *data, UINT count) noexcept override { return real_->SetVertexShaderConstantB(reg_idx, data, count); }
HRESULT STDMETHODCALLTYPE GetVertexShaderConstantB(UINT StartRegister, BOOL* pConstantData, UINT BoolCount) noexcept override { return real_->GetVertexShaderConstantB(StartRegister, pConstantData, BoolCount); }
HRESULT STDMETHODCALLTYPE SetStreamSource(UINT StreamNumber, IDirect3DVertexBuffer9* pStreamData, UINT OffsetInBytes, UINT Stride) noexcept override { return real_->SetStreamSource(StreamNumber, pStreamData, OffsetInBytes, Stride); }
HRESULT STDMETHODCALLTYPE GetStreamSource(UINT StreamNumber, IDirect3DVertexBuffer9** ppStreamData, UINT* OffsetInBytes, UINT* pStride) noexcept override { return real_->GetStreamSource(StreamNumber, ppStreamData, OffsetInBytes, pStride); }
HRESULT STDMETHODCALLTYPE SetStreamSourceFreq(UINT StreamNumber, UINT Divider) noexcept override { return real_->SetStreamSourceFreq(StreamNumber, Divider); }
HRESULT STDMETHODCALLTYPE GetStreamSourceFreq(UINT StreamNumber, UINT* Divider) noexcept override { return real_->GetStreamSourceFreq(StreamNumber, Divider); }
HRESULT STDMETHODCALLTYPE SetIndices(IDirect3DIndexBuffer9* pIndexData) noexcept override { return real_->SetIndices(pIndexData); }
HRESULT STDMETHODCALLTYPE GetIndices(IDirect3DIndexBuffer9** ppIndexData) noexcept override { return real_->GetIndices(ppIndexData); }
HRESULT STDMETHODCALLTYPE CreatePixelShader(const DWORD *byte_code, IDirect3DPixelShader9 **shader) noexcept override { return real_->CreatePixelShader(byte_code, shader); }
HRESULT STDMETHODCALLTYPE SetPixelShader(IDirect3DPixelShader9* pShader) noexcept override { return real_->SetPixelShader(pShader); }
HRESULT STDMETHODCALLTYPE GetPixelShader(IDirect3DPixelShader9** ppShader) noexcept override { return real_->GetPixelShader(ppShader); }
HRESULT STDMETHODCALLTYPE SetPixelShaderConstantF(UINT reg_idx, const float *data, UINT count) noexcept override { return real_->SetPixelShaderConstantF(reg_idx, data, count); }
HRESULT STDMETHODCALLTYPE GetPixelShaderConstantF(UINT StartRegister, float* pConstantData, UINT Vector4fCount) noexcept override { return real_->GetPixelShaderConstantF(StartRegister, pConstantData, Vector4fCount); }
HRESULT STDMETHODCALLTYPE SetPixelShaderConstantI(UINT reg_idx, const int *data, UINT count) noexcept override { return real_->SetPixelShaderConstantI(reg_idx, data, count); }
HRESULT STDMETHODCALLTYPE GetPixelShaderConstantI(UINT StartRegister, int* pConstantData, UINT Vector4iCount) noexcept override { return real_->GetPixelShaderConstantI(StartRegister, pConstantData, Vector4iCount); }
HRESULT STDMETHODCALLTYPE SetPixelShaderConstantB(UINT reg_idx, const BOOL *data, UINT count) noexcept override { return real_->SetPixelShaderConstantB(reg_idx, data, count); }
HRESULT STDMETHODCALLTYPE GetPixelShaderConstantB(UINT StartRegister, BOOL* pConstantData, UINT BoolCount) noexcept override { return real_->GetPixelShaderConstantB(StartRegister, pConstantData, BoolCount); }
HRESULT STDMETHODCALLTYPE DrawRectPatch(UINT handle, const float *segment_count, const D3DRECTPATCH_INFO *patch_info) noexcept override { return real_->DrawRectPatch(handle, segment_count, patch_info); }
HRESULT STDMETHODCALLTYPE DrawTriPatch(UINT handle, const float *segment_count, const D3DTRIPATCH_INFO *patch_info) noexcept override { return real_->DrawTriPatch(handle, segment_count, patch_info); }
HRESULT STDMETHODCALLTYPE DeletePatch(UINT Handle) noexcept override { return real_->DeletePatch(Handle); }
HRESULT STDMETHODCALLTYPE CreateQuery(D3DQUERYTYPE Type, IDirect3DQuery9** ppQuery) noexcept override { return real_->CreateQuery(Type, ppQuery); }
