// Wine/Linux only: hand our own O_RDONLY memory descriptor to the controller.
// SCM_RIGHTS preserves the existing Wine ptracer and the system Yama policy.
// The i386 Linux ABI is used only after Wine reports a Linux host.
#include <windows.h>
#include <cstdint>
#include <cstring>
#include <string>

namespace {
constexpr char host_magic[8] = {'T','B','M','E','M','F','D','1'};
#pragma pack(push, 1)
struct Host { char magic[8]; uint32_t version, pid; char path[108]; };
#pragma pack(pop)
static_assert(sizeof(Host) == 124 && sizeof(void*) == 4);

#if defined(_MSC_VER)
__declspec(naked) long __cdecl linux_call(uint32_t, uintptr_t = 0, uintptr_t = 0, uintptr_t = 0) {
    __asm {
        push ebx
        mov eax, [esp + 8]
        mov ebx, [esp + 12]
        mov ecx, [esp + 16]
        mov edx, [esp + 20]
        int 80h
        pop ebx
        ret
    }
}
#else
long linux_call(uint32_t number, uintptr_t a = 0, uintptr_t b = 0, uintptr_t c = 0) {
    long result;
    __asm__ volatile("int $0x80" : "=a"(result) : "a"(number), "b"(a), "c"(b), "d"(c) : "memory");
    return result;
}
#endif
long socket_call(uint32_t operation, uintptr_t* arguments) {
    return linux_call(102, operation, reinterpret_cast<uintptr_t>(arguments));
}
void close_fd(long fd) { if (fd >= 0) linux_call(6, static_cast<uintptr_t>(fd)); }

bool transfer(const Host& host) {
    uintptr_t args[6] = {1, 1 | 0x80000, 0}; // AF_UNIX, SOCK_STREAM | CLOEXEC.
    const auto channel = socket_call(1, args);
    if (channel < 0) return false;
    struct Address { uint16_t family; char path[108]; } address{};
    address.family = 1;
    std::memcpy(address.path, host.path, sizeof address.path);
    args[0] = channel; args[1] = reinterpret_cast<uintptr_t>(&address);
    args[2] = 2 + std::strlen(address.path) + 1;
    bool sent = false;
    if (socket_call(3, args) == 0) {
        struct Credentials { int32_t pid; uint32_t uid, gid; } credentials{};
        uint32_t size = sizeof credentials;
        args[0] = channel; args[1] = 1; args[2] = 17; // SOL_SOCKET, SO_PEERCRED.
        args[3] = reinterpret_cast<uintptr_t>(&credentials);
        args[4] = reinterpret_cast<uintptr_t>(&size);
        if (socket_call(15, args) == 0 && credentials.pid > 0 &&
            static_cast<uint32_t>(credentials.pid) == host.pid &&
            credentials.uid == static_cast<uint32_t>(linux_call(199))) {
            // Open directly in this process, never via Wine's file server.
            const char self[] = "/proc/self/mem";
            const auto memory = linux_call(5, reinterpret_cast<uintptr_t>(self), 0x80000);
            if (memory >= 0) {
                struct Iovec { const void* data; uint32_t size; } iovec{host_magic, 8};
                struct Rights { uint32_t size; int32_t level, type, descriptor; }
                    rights{16, 1, 1, static_cast<int32_t>(memory)};
                struct Message {
                    void* name; uint32_t name_size;
                    Iovec* vectors; uint32_t vector_count;
                    Rights* control; uint32_t control_size, flags;
                } message{nullptr, 0, &iovec, 1, &rights, sizeof rights, 0};
                static_assert(sizeof(Message) == 28 && sizeof(Rights) == 16);
                args[0] = channel; args[1] = reinterpret_cast<uintptr_t>(&message);
                args[2] = 0x4000; // MSG_NOSIGNAL.
                sent = socket_call(16, args) == 8;
                close_fd(memory);
            }
        }
    }
    close_fd(channel);
    return sent;
}
DWORD WINAPI watch_host(void*) {
    using HostVersion = void(__cdecl*)(const char**, const char**);
    const auto fn = reinterpret_cast<HostVersion>(
        GetProcAddress(GetModuleHandleW(L"ntdll.dll"), "wine_get_host_version"));
    const char* system = nullptr;
    if (!fn) return 0;
    fn(&system, nullptr);
    if (!system || std::strcmp(system, "Linux")) return 0;
    wchar_t executable[32768]{};
    const auto length = GetModuleFileNameW(nullptr, executable, 32768);
    if (!length || length >= 32768) return 0;
    std::wstring filename(executable, length);
    const auto slash = filename.find_last_of(L"\\/");
    if (slash == std::wstring::npos) return 0;
    filename.resize(slash + 1);
    filename += L".torchbridge-input-host";
    Host previous{};
    for (;;) {
        Host host{};
        const auto file = CreateFileW(filename.c_str(), GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr,
            OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
        DWORD bytes = 0;
        bool valid = false;
        if (file != INVALID_HANDLE_VALUE) {
            valid = GetFileSize(file, nullptr) == sizeof host &&
                ReadFile(file, &host, sizeof host, &bytes, nullptr) && bytes == sizeof host;
            CloseHandle(file);
        }
        valid = valid && !std::memcmp(host.magic, host_magic, 8) &&
            host.version == 1 && host.pid > 1 && host.path[0] == '/' &&
            std::memchr(host.path, 0, sizeof host.path);
        if (valid && std::memcmp(&host, &previous, sizeof host) && transfer(host))
            previous = host;
        Sleep(250);
    }
}
}

void tb_start_linux_memory() {
    const auto thread = CreateThread(nullptr, 0, watch_host, nullptr, 0, nullptr);
    if (thread) CloseHandle(thread);
}
