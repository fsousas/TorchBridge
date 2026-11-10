#include <windows.h>
extern "C" void tb_start_input();
namespace {
HMODULE system_runtime() {
    static HMODULE module = [] {
        wchar_t path[MAX_PATH]{};
        const auto size = GetSystemDirectoryW(path, MAX_PATH);
        if (!size || size > MAX_PATH - 12) return static_cast<HMODULE>(nullptr);
        lstrcatW(path, L"\\winmm.dll");
        return LoadLibraryExW(path, nullptr, LOAD_WITH_ALTERED_SEARCH_PATH);
    }();
    return module;
}
}
#define RESOLVE(name) \
    extern "C" FARPROC __cdecl tb_resolve_##name() { \
        static FARPROC function = GetProcAddress(system_runtime(), #name); \
        if (!function) RaiseException(ERROR_PROC_NOT_FOUND, EXCEPTION_NONCONTINUABLE, 0, nullptr); \
        return function; \
    }
#if defined(_MSC_VER)
#define FORWARD(name) \
    RESOLVE(name) \
    extern "C" __declspec(naked) void tb_##name() { \
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
    RESOLVE(name) \
    extern "C" __attribute__((naked)) void tb_##name() { \
        __asm__ __volatile__("pushl %eax\n\tpushfl\n\tpushal\n\t" \
            "call _tb_resolve_" #name "\n\tmovl %eax, 36(%esp)\n\t" \
            "popal\n\tpopfl\n\tret\n\t"); \
    }
#endif
#include "exports.inc"

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        tb_start_input();
    }
    return TRUE;
}
