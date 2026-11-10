#ifdef NDEBUG
#undef NDEBUG
#endif
#include <windows.h>
#include <cassert>
#include <cstring>
#include "wire.h"
int wmain(int argc, wchar_t** argv) {
    assert(argc == 2);
    const auto dll = LoadLibraryW(argv[1]);
    assert(dll);
    const auto identity = reinterpret_cast<const char*(*)()>(GetProcAddress(dll, "TorchBridgeInputIdentity"));
    assert(identity && !std::strcmp(identity(), "TorchBridge.NativeInput.v2.x86"));
    const auto endpoint = reinterpret_cast<const tbinput::Endpoint*>(GetProcAddress(dll, "TorchBridgeInputEndpoint"));
    assert(endpoint);
    for (unsigned i = 0; i < 100 && std::memcmp(endpoint->magic, tbinput::magic, 8); ++i) Sleep(10);
    assert(!std::memcmp(endpoint->magic, tbinput::magic, 8));
    // An unrelated executable must retain normal WinMM and never receive hooks.
    assert(endpoint->error == tbinput::unsupported && endpoint->port == 0);
    const auto timer = reinterpret_cast<DWORD(WINAPI*)()>(GetProcAddress(dll, "timeGetTime"));
    assert(timer && static_cast<DWORD>(GetTickCount() - timer()) < 1000);
    assert(GetProcAddress(dll, "waveInOpen"));
}
