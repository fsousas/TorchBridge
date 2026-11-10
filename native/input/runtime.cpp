// Game-thread movement and explicit world interaction for Torchlight 1 PE32.
// Layout facts are documented in docs/POSICIONAMENTO.md. No third-party
// controller implementation is used here. MinHook is vendored under BSD-2-Clause.
#include <winsock2.h>
#include <windows.h>
#include <bcrypt.h>
#include <algorithm>
#include <array>
#include <atomic>
#include <cstring>
#include <limits>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>
#include "vendor/minhook/include/MinHook.h"
#include "wire.h"

extern "C" __declspec(dllexport) tbinput::Endpoint TorchBridgeInputEndpoint{};
extern "C" const char* TorchBridgeInputIdentity() {
    return "TorchBridge.NativeInput.v2.x86";
}

namespace {
using namespace tbinput;
uintptr_t image = 0, image_end = 0, game_global = 0;
struct Scene { uintptr_t client = 0, player = 0, level = 0, ui = 0; };
Scene scene;
SRWLOCK channel_lock = SRWLOCK_INIT;
Command latest{};
Reply published{};
ULONGLONG received_at = 0;
uint32_t connection_generation = 0, current_generation = 0;
std::atomic<bool> initialized{false};
bool strict_world = false, strict_warps = false, was_moving = false;
uintptr_t highlighted_object = 0, highlight_level = 0, authorized_target = 0;
uintptr_t authorized_player = 0, authorized_level = 0;
ULONGLONG authorized_until = 0, ordered_at = 0;
uint32_t last_action = 0, scope = 0;
float last_dx = 0, last_dz = 0;
Reply status{};

bool read_raw(uintptr_t address, void* out, size_t size) {
    SIZE_T copied = 0;
    return address >= 0x10000 && address <= UINT32_MAX - size &&
        ReadProcessMemory(GetCurrentProcess(), reinterpret_cast<void*>(address), out, size, &copied) &&
        copied == size;
}
template<class T> T field(uintptr_t p, size_t offset = 0) {
    T value{};
    read_raw(p + offset, &value, sizeof value);
    return value;
}
bool code(uintptr_t p) { return p >= image + 0x1000 && p < image_end; }
bool contains(uintptr_t p, size_t length, const uint8_t* pattern, size_t size) {
    std::vector<uint8_t> bytes(length);
    return read_raw(p, bytes.data(), bytes.size()) &&
        std::search(bytes.begin(), bytes.end(), pattern, pattern + size) != bytes.end();
}
struct ClassInfo { uint32_t mask = 0; std::string name; };
constexpr uint32_t character = 1, item = 2, trigger = 4, breakable = 8, player = 16;
std::unordered_map<uintptr_t, ClassInfo> classes;
std::string type_name(uintptr_t td) {
    char name[96]{};
    if (!read_raw(td + 8, name, sizeof name - 1) || std::strncmp(name, ".?AVC", 5)) return {};
    const auto end = std::strstr(name, "@@");
    return end ? std::string(name + 4, end) : std::string();
}
const ClassInfo& class_info(uintptr_t p) {
    static const ClassInfo empty{};
    const uintptr_t vt = field<uint32_t>(p);
    if (!code(vt)) return empty;
    if (auto found = classes.find(vt); found != classes.end()) return found->second;
    ClassInfo info;
    const auto col = field<uint32_t>(vt - 4);
    info.name = type_name(field<uint32_t>(col, 12));
    const auto hierarchy = field<uint32_t>(col, 16);
    const auto count = field<uint32_t>(hierarchy, 8), bases = field<uint32_t>(hierarchy, 12);
    if (info.name.empty() || count > 64 || !count) return empty;
    for (uint32_t i = 0; i < count; ++i) {
        const auto descriptor = field<uint32_t>(bases, i * 4);
        const auto name = type_name(field<uint32_t>(descriptor));
        if (name == "CCharacter") info.mask |= character;
        if (name == "CItem") info.mask |= item;
        if (name == "CTriggerUnit") info.mask |= trigger;
        if (name == "CBreakable") info.mask |= breakable;
        if (name == "CPlayer") info.mask |= player;
    }
    if (classes.size() >= 256) classes.clear();
    return classes.emplace(vt, std::move(info)).first->second;
}
uintptr_t find_vtable(const char* class_name) {
    const auto dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(image);
    const auto nt = reinterpret_cast<const IMAGE_NT_HEADERS32*>(image + dos->e_lfanew);
    const auto section = IMAGE_FIRST_SECTION(nt);
    std::string decorated = std::string(".?AV") + class_name + "@@";
    uintptr_t td = 0;
    for (unsigned s = 0; s < nt->FileHeader.NumberOfSections; ++s) {
        if (!(section[s].Characteristics & IMAGE_SCN_MEM_READ) ||
            section[s].Characteristics & IMAGE_SCN_MEM_EXECUTE) continue;
        const auto first = image + section[s].VirtualAddress;
        const auto length = section[s].Misc.VirtualSize;
        for (size_t i = 8; i + decorated.size() < length; ++i) {
            if (!std::memcmp(reinterpret_cast<void*>(first + i), decorated.c_str(), decorated.size() + 1))
                td = first + i - 8;
        }
    }
    if (!td) return 0;
    for (unsigned s = 0; s < nt->FileHeader.NumberOfSections; ++s) {
        if (std::memcmp(section[s].Name, ".rdata", 6)) continue;
        const auto first = image + section[s].VirtualAddress, end = first + section[s].Misc.VirtualSize;
        for (auto p = first; p + 20 < end; p += 4) {
            if (field<uint32_t>(p) != 0 || field<uint32_t>(p, 4) != 0 ||
                field<uint32_t>(p, 8) != 0 || field<uint32_t>(p, 12) != td) continue;
            for (auto ref = first; ref + 8 < end; ref += 4)
                if (field<uint32_t>(ref) == p && code(field<uint32_t>(ref + 4))) return ref + 4;
        }
    }
    return 0;
}
template<class Fn> Fn method(uintptr_t p, size_t offset) {
    return reinterpret_cast<Fn>(field<uint32_t>(field<uint32_t>(p), offset));
}
using VoidFn = void(__thiscall*)(void*);
using TargetFn = void(__thiscall*)(void*, void*);
using MoveFn = void(__thiscall*)(void*, void*, float, float);
using ModeFn = void(__thiscall*)(void*, int);
using PickupFn = void(__thiscall*)(void*, float, void*);
using HighlightFn = void(__thiscall*)(void*, bool);
using IsaFn = bool(__thiscall*)(void*, int);
using UpdateFn = void(__fastcall*)(void*, void*, uint32_t, uint32_t, float);
using WarpFn = void(__fastcall*)(void*, void*);
using InteractFn = uint32_t(__fastcall*)(void*, void*, void*);
VoidFn stop_path = nullptr;
MoveFn move_to = nullptr;
TargetFn original_target = nullptr, original_item = nullptr;
UpdateFn original_update = nullptr;
WarpFn original_warp = nullptr;
IsaFn is_a = nullptr;
std::array<InteractFn, 64> original_interacts{};
std::unordered_map<uintptr_t, size_t> interact_hooks;

bool focused() {
    DWORD pid = 0;
    GetWindowThreadProcessId(GetForegroundWindow(), &pid);
    return pid == GetCurrentProcessId();
}
bool authorized(uintptr_t object) {
    return object && object == authorized_target && scene.player == authorized_player &&
        scene.level == authorized_level && GetTickCount64() <= authorized_until && focused();
}
void __fastcall target_hook(void* self, void*, void* target) {
    const auto address = reinterpret_cast<uintptr_t>(target);
    if (strict_world && reinterpret_cast<uintptr_t>(self) == scene.player && address &&
        (class_info(address).mask & character) && field<uint32_t>(address, 0x28C) != 2 &&
        field<uint32_t>(address, 0x28C) != 4 && !authorized(address)) {
        ++status.blocked_interactions;
        return;
    }
    original_target(self, target);
}
void __fastcall item_hook(void* self, void*, void* target) {
    const auto address = reinterpret_cast<uintptr_t>(target);
    if (strict_world && reinterpret_cast<uintptr_t>(self) == scene.player && address &&
        !authorized(address) && !(class_info(address).mask & breakable)) {
        ++status.blocked_interactions;
        return;
    }
    original_item(self, target);
}
void __fastcall warp_hook(void* self, void* edx) {
    // A warper is a logic action, not a nearby mesh to select. Only an explicit
    // interaction dispatch may reach it. Area/spawn/quest triggers keep updating.
    if (strict_warps && !scope) { ++status.blocked_warps; return; }
    original_warp(self, edx);
}
template<size_t N> uint32_t __fastcall interact_hook(void* self, void* edx, void* user) {
    const auto address = reinterpret_cast<uintptr_t>(self);
    const bool local = reinterpret_cast<uintptr_t>(user) == scene.player;
    const bool allowed = local && authorized(address);
    if (strict_world && local && !allowed) {
        ++status.blocked_interactions;
        return 0;
    }
    if (allowed) ++scope;
    const auto result = original_interacts[N](self, edx, user);
    if (allowed) {
        --scope;
        status.executed = static_cast<uint32_t>(address);
        status.action_result = accepted;
        authorized_target = 0; // One dispatch per physical button press.
    }
    return result;
}
template<size_t... N> constexpr auto dispatch_table(std::index_sequence<N...>) {
    return std::array<InteractFn, sizeof...(N)>{&interact_hook<N>...};
}
constexpr auto dispatches = dispatch_table(std::make_index_sequence<64>{});
bool guard_interaction(uintptr_t object) {
    const auto address = field<uint32_t>(field<uint32_t>(object), 0x13C);
    if (!code(address)) return false;
    if (interact_hooks.find(address) != interact_hooks.end()) return true;
    const auto n = interact_hooks.size();
    if (n >= dispatches.size()) return false;
    if (MH_CreateHook(reinterpret_cast<void*>(address), reinterpret_cast<void*>(dispatches[n]),
                      reinterpret_cast<void**>(&original_interacts[n])) != MH_OK ||
        MH_EnableHook(reinterpret_cast<void*>(address)) != MH_OK) return false;
    interact_hooks.emplace(address, n);
    return true;
}
bool position(uintptr_t p, Candidate& out) {
    uintptr_t source = p + 0x70;
    if (field<uint32_t>(p, 0x50)) {
        const auto node = field<uint32_t>(p, 0x58);
        if (!node || field<uint8_t>(node, 0xA0)) return false;
        source = node + 0x10C;
    }
    float xyz[3];
    if (!read_raw(source, xyz, sizeof xyz)) return false;
    out.x = xyz[0]; out.y = xyz[1]; out.z = xyz[2];
    return std::isfinite(out.x) && std::isfinite(out.y) && std::isfinite(out.z) &&
        std::fabs(out.x) < 1e6f && std::fabs(out.y) < 1e6f && std::fabs(out.z) < 1e6f;
}
bool list(uint32_t offset, std::vector<Candidate>& candidates, std::unordered_set<uintptr_t>& objects) {
    const auto container = field<uint32_t>(scene.level, offset);
    if (!container) return false;
    auto node = field<uint32_t>(container);
    std::unordered_set<uintptr_t> seen;
    while (node) {
        if (seen.size() >= 4096 || !seen.emplace(node).second) return false;
        uint32_t pair[2];
        if (!read_raw(node, pair, sizeof pair)) return false;
        node = pair[1];
        const uintptr_t p = pair[0];
        if (!p || !objects.emplace(p).second) continue;
        if (p == scene.player || p == field<uint32_t>(scene.client, 0x30)) continue;
        const auto mask = class_info(p).mask;
        if (!field<uint8_t>(p, 0x6E) || !field<uint8_t>(p, 0x161)) continue;
        Candidate candidate{}; candidate.address = p;
        if (offset == 0x5C) {
            const auto alignment = field<uint32_t>(p, 0x28C);
            if (!(mask & character) || !is_a(reinterpret_cast<void*>(p), 131) ||
                (alignment != 1 && alignment != 3) ||
                field<float>(p, 0x394) <= 0 || field<uint32_t>(p, 0x284) == 5 ||
                field<uint32_t>(p, 0x284) == 6 || field<uint32_t>(p, 0x5B4)) continue;
            candidate.type = 1;
        } else {
            if (!(mask & item)) continue;
            if (!field<uint8_t>(p, 0x19C) || field<uint8_t>(p, 0x19D)) continue;
            // Install at the actual virtual dispatch of each item family,
            // including inherited implementations and modded subclasses.
            if (!guard_interaction(p)) return false;
            candidate.type = 2;
        }
        if (position(p, candidate)) candidates.push_back(candidate);
    }
    return true;
}
void highlight(uintptr_t target, const std::unordered_set<uintptr_t>& objects) {
    if (highlighted_object && highlighted_object != target && highlight_level == scene.level &&
        objects.find(highlighted_object) != objects.end()) {
        const auto fn = method<HighlightFn>(highlighted_object, 0x100);
        if (code(reinterpret_cast<uintptr_t>(fn))) fn(reinterpret_cast<void*>(highlighted_object), false);
    }
    highlighted_object = target; highlight_level = scene.level;
    if (target) {
        const auto fn = method<HighlightFn>(target, 0x100);
        if (code(reinterpret_cast<uintptr_t>(fn))) fn(reinterpret_cast<void*>(target), true);
    }
}
void stop() {
    if (was_moving && (class_info(scene.player).mask & player))
        stop_path(reinterpret_cast<void*>(scene.player));
    was_moving = false;
}
bool menu_open() {
    if (!scene.ui || field<uint32_t>(scene.ui, 0x169C) != 6) return true;
    const auto manager = field<uint32_t>(scene.ui, 0x324);
    if (!manager || field<uint32_t>(manager, 0xD84) != 6) return true;
    // Gameplay panels, dialogs, fishing, loading, modals and pause. The same
    // visibility fields are used by memory.py. Check here again on the game thread.
    const std::pair<uint32_t, uint32_t> panels[] = {
        {0x2CC,0x30}, {0x2D0,0x44}, {0x2D4,0x34}, {0x2D8,0x30},
        {0x2DC,0x38}, {0x2E0,0x54}, {0x2E4,0x30}, {0x2E8,0x18},
        {0x2EC,0x18}, {0x2F0,0x18}, {0x2F4,0x18}, {0x2F8,0x18},
        {0x2FC,0x18}, {0x300,0x18}, {0x304,0x18}, {0x30C,0x1C},
        {0x310,0x1C}, {0x314,0xC8}, {0x31C,0x18}
    };
    for (const auto& entry : panels) {
        const auto panel = field<uint32_t>(scene.ui, entry.first);
        if (panel && field<uint8_t>(panel, entry.second) == 1) return true;
    }
    const auto loading = field<uint32_t>(scene.ui, 0x298);
    if (loading && field<uint32_t>(loading, 0x80)) return true;
    return false;
}
bool locked() {
    if (field<uint8_t>(scene.player, 0x20A)) return true;
    const auto skill = field<uint32_t>(scene.player, 0x2D0);
    return skill && (field<uint8_t>(scene.player, 0x20B) ||
        (field<float>(scene.player, 0x2C0) > 0 && !field<uint8_t>(scene.player, 0x2BD)));
}
void use(const Candidate& candidate, ULONGLONG now) {
    stop();
    authorized_target = candidate.address;
    authorized_player = scene.player; authorized_level = scene.level;
    authorized_until = now + 1500;
    status.reason = acting; status.action_result = accepted;
    auto hero = reinterpret_cast<void*>(scene.player);
    original_target(hero, nullptr);
    original_item(hero, nullptr);
    if (candidate.type == 1) {
        original_target(hero, reinterpret_cast<void*>(candidate.address));
        method<ModeFn>(scene.player, 0x174)(hero, 9); // Native approach/talk state.
        status.executed = static_cast<uint32_t>(candidate.address);
    } else {
        original_item(hero, reinterpret_cast<void*>(candidate.address));
        method<ModeFn>(scene.player, 0x174)(hero, 7);
        method<PickupFn>(scene.player, 0x1B4)(hero, 0.f, reinterpret_cast<void*>(scene.level));
    }
}
void frame() {
    ++status.frames;
    Command command{};
    ULONGLONG received = 0;
    uint32_t generation = current_generation;
    if (TryAcquireSRWLockShared(&channel_lock)) {
        command = latest; received = received_at; generation = connection_generation;
        ReleaseSRWLockShared(&channel_lock);
    }
    const auto now = GetTickCount64();
    if (generation != current_generation) {
        current_generation = generation;
        last_action = 0; authorized_target = 0;
    }
    status.sequence = command.sequence;
    status.lease_age = static_cast<uint32_t>(std::min<ULONGLONG>(now - received, UINT32_MAX));
    const auto game = field<uint32_t>(game_global);
    scene = {field<uint32_t>(game, 0x64), 0, 0, 0};
    scene.player = field<uint32_t>(scene.client, 0x2C);
    scene.level = field<uint32_t>(scene.client, 0x38);
    scene.ui = field<uint32_t>(scene.client, 0x3C);
    std::vector<Candidate> candidates;
    std::unordered_set<uintptr_t> objects;
    bool roster_ok = scene.level && list(0x5C, candidates, objects) && list(0x68, candidates, objects);
    status.flags = ready | (roster_ok ? complete : 0u);
    status.count = static_cast<uint32_t>(candidates.size());
    status.selected = 0;
    const bool live = received && now - received <= 200 && command.flags & active;
    const bool same = scene.player && scene.level && scene.player == command.player &&
        scene.level == command.level && (class_info(scene.player).mask & player);
    const bool focus = focused();
    if (live && focus && (same || !(command.flags & direct)))
        strict_world = (command.flags & direct) != 0;
    if (strict_world) { strict_warps = true; status.flags |= protected_world; }
    if (!live || !same || !focus || menu_open() || !roster_ok || !(command.flags & direct)) {
        stop(); authorized_target = 0; highlight(0, objects);
        status.reason = !live ? no_session : !focus ? no_focus : !same ? wrong_scene :
            !roster_ok ? incomplete : menu_open() ? menu : idle;
    } else {
        Candidate hero{};
        const bool have_position = position(scene.player, hero);
        const Candidate* selected = nullptr;
        if (have_position) for (const auto& candidate : candidates)
            if (in_range(candidate, hero.x, hero.y, hero.z, command.radius) &&
                (!selected || nearer(candidate, *selected, hero.x, hero.z))) selected = &candidate;
        status.selected = selected ? static_cast<uint32_t>(selected->address) : 0;
        const bool may_interact = (command.flags & allow_interaction) != 0;
        highlight(may_interact ? status.selected : 0, objects);
        if (highlighted_object) status.flags |= highlighted;
        if (authorized_target && now > authorized_until) {
            authorized_target = 0;
            original_target(reinterpret_cast<void*>(scene.player), nullptr);
            original_item(reinterpret_cast<void*>(scene.player), nullptr);
            stop_path(reinterpret_cast<void*>(scene.player));
        }
        const bool action = command.action && newer(command.action, last_action);
        if (action) {
            last_action = command.action;
            if (selected && may_interact && !locked()) use(*selected, now);
            else { stop(); status.reason = no_target; status.action_result = unavailable; }
        } else if (locked()) {
            // The skill may now own this path (dash/charge). Do not stop it.
            was_moving = false; status.reason = skill_lock;
        } else if (authorized_target) {
            stop(); status.reason = acting;
        } else if (have_position && command.flags & walking &&
                   std::hypot(command.dx, command.dz) > 0.001f) {
            if (!was_moving) {
                original_target(reinterpret_cast<void*>(scene.player), nullptr);
                original_item(reinterpret_cast<void*>(scene.player), nullptr);
            }
            const auto length = std::hypot(command.dx, command.dz);
            const auto reach = 2.f + 3.f * length;
            status.destination_x = hero.x + command.dx / length * reach;
            status.destination_z = hero.z + command.dz / length * reach;
            if (!was_moving || now - ordered_at >= 50 ||
                command.dx * last_dx + command.dz * last_dz < length * length * 0.95f) {
                move_to(reinterpret_cast<void*>(scene.player), reinterpret_cast<void*>(scene.level),
                        status.destination_x, status.destination_z);
                ordered_at = now; last_dx = command.dx; last_dz = command.dz;
            }
            was_moving = true; status.flags |= moving; status.reason = walking_now;
        } else {
            stop(); status.reason = selected ? idle : no_target;
        }
    }
    if (TryAcquireSRWLockExclusive(&channel_lock)) {
        published = status;
        ReleaseSRWLockExclusive(&channel_lock);
    }
}
void __fastcall update_hook(void* self, void* edx, uint32_t a, uint32_t b, float dt) {
    original_update(self, edx, a, b, dt);
    const auto game = field<uint32_t>(game_global), client = field<uint32_t>(game, 0x64);
    if (reinterpret_cast<uintptr_t>(self) == field<uint32_t>(client, 0x2C)) frame();
}
bool hook(uintptr_t target, void* replacement, void** original) {
    return code(target) && MH_CreateHook(reinterpret_cast<void*>(target), replacement, original) == MH_OK;
}
bool initialize() {
    image = reinterpret_cast<uintptr_t>(GetModuleHandleW(nullptr));
    const auto dos = reinterpret_cast<IMAGE_DOS_HEADER*>(image);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) return false;
    const auto nt = reinterpret_cast<IMAGE_NT_HEADERS32*>(image + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE || nt->FileHeader.Machine != IMAGE_FILE_MACHINE_I386) return false;
    image_end = image + nt->OptionalHeader.SizeOfImage;
    const bool steam = nt->FileHeader.TimeDateStamp == 0x4B5F7519;
    const bool gog = nt->FileHeader.TimeDateStamp == 0x4FFC6815;
    if (!steam && !gog) return false;
    game_global = image + (steam ? 0x7F0E0C : 0x81AD64);
    const auto player_vt = find_vtable("CPlayer"), warper_vt = find_vtable("CWarper");
    if (!player_vt || !warper_vt) return false;
    const auto at = [](uint32_t preferred) { return image + preferred - 0x400000; };
    const auto destination = at(steam ? 0x492AD0 : 0x494B30);
    const auto stopping = at(steam ? 0x484360 : 0x486150);
    const uint8_t pathfinder[] = {0x0C,0x02,0,0}, holding[] = {0x0A,0x02,0,0};
    const uint8_t moving_field[] = {0x08,0x02,0,0};
    if (!contains(destination, 160, pathfinder, 4) || !contains(destination, 160, holding, 4) ||
        !contains(stopping, 48, moving_field, 4)) return false;
    // The warper action follows its scalar deleting destructor. Verify the
    // client-list access before using this build-dependent boundary.
    const auto warp = field<uint32_t>(warper_vt) + 0x20;
    const uint8_t clients[] = {0x34,0x01,0,0};
    if (!contains(warp, 160, clients, 4)) return false;
    move_to = reinterpret_cast<MoveFn>(destination);
    is_a = reinterpret_cast<IsaFn>(at(steam ? 0x47EAF0 : 0x480760));
    stop_path = reinterpret_cast<VoidFn>(stopping);
    if (MH_Initialize() != MH_OK) return false;
    if (!hook(field<uint32_t>(player_vt, 0xFC), reinterpret_cast<void*>(&update_hook),
              reinterpret_cast<void**>(&original_update)) ||
        !hook(at(steam ? 0x492970 : 0x4949D0), reinterpret_cast<void*>(&target_hook),
              reinterpret_cast<void**>(&original_target)) ||
        !hook(at(steam ? 0x492A50 : 0x494AB0), reinterpret_cast<void*>(&item_hook),
              reinterpret_cast<void**>(&original_item)) ||
        !hook(warp, reinterpret_cast<void*>(&warp_hook), reinterpret_cast<void**>(&original_warp))) {
        MH_Uninitialize(); return false;
    }
    std::memcpy(status.magic, magic, 8); status.version = version; status.flags = ready;
    published = status;
    if (MH_EnableHook(MH_ALL_HOOKS) != MH_OK) { MH_Uninitialize(); return false; }
    return true;
}
DWORD WINAPI serve(void*) {
    auto& endpoint = TorchBridgeInputEndpoint;
    endpoint.version = version;
    endpoint.pid = GetCurrentProcessId();
    endpoint.image_base = reinterpret_cast<uintptr_t>(GetModuleHandleW(nullptr));
    if (!initialize()) { endpoint.error = unsupported; std::memcpy(endpoint.magic, magic, 8); return 0; }
    WSADATA data{};
    if (WSAStartup(MAKEWORD(2,2), &data)) return 0;
    const auto listener = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    sockaddr_in address{};
    address.sin_family = AF_INET; address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (listener == INVALID_SOCKET || bind(listener, reinterpret_cast<sockaddr*>(&address), sizeof address) ||
        listen(listener, 1) || BCryptGenRandom(nullptr, endpoint.token, 16, BCRYPT_USE_SYSTEM_PREFERRED_RNG)) {
        endpoint.error = transport_error; std::memcpy(endpoint.magic, magic, 8); return 0;
    }
    int length = sizeof address;
    getsockname(listener, reinterpret_cast<sockaddr*>(&address), &length);
    endpoint.port = ntohs(address.sin_port); endpoint.capabilities = ready | protected_world | highlighted;
    MemoryBarrier(); std::memcpy(endpoint.magic, magic, 8);
    initialized.store(true);
    for (;;) {
        const auto client = accept(listener, nullptr, nullptr);
        if (client == INVALID_SOCKET) { Sleep(25); continue; }
        DWORD timeout = 250;
        setsockopt(client, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char*>(&timeout), sizeof timeout);
        setsockopt(client, SOL_SOCKET, SO_SNDTIMEO, reinterpret_cast<const char*>(&timeout), sizeof timeout);
        BOOL enabled = TRUE;
        setsockopt(client, IPPROTO_TCP, TCP_NODELAY, reinterpret_cast<const char*>(&enabled), sizeof enabled);
        size_t have = 0; Command incoming{}; uint32_t sequence = 0; bool seen = false;
        while (true) {
            const auto got = recv(client, reinterpret_cast<char*>(&incoming) + have,
                                  static_cast<int>(sizeof incoming - have), 0);
            if (got <= 0) break;
            have += static_cast<size_t>(got);
            if (have != sizeof incoming) continue;
            have = 0;
            if (!valid(incoming, endpoint.token) || (seen && !newer(incoming.sequence, sequence))) break;
            sequence = incoming.sequence;
            AcquireSRWLockExclusive(&channel_lock);
            // A reconnect does not replay an action. Python action IDs are
            // monotonically increasing within this game process/session.
            latest = incoming; received_at = GetTickCount64();
            if (!seen) ++connection_generation;
            seen = true;
            const auto reply = published;
            ReleaseSRWLockExclusive(&channel_lock);
            size_t sent = 0;
            while (sent < sizeof reply) {
                const auto n = send(client, reinterpret_cast<const char*>(&reply) + sent,
                                    static_cast<int>(sizeof reply - sent), 0);
                if (n <= 0) break;
                sent += static_cast<size_t>(n);
            }
            if (sent != sizeof reply) break;
        }
        closesocket(client);
        AcquireSRWLockExclusive(&channel_lock);
        received_at = 0;
        ReleaseSRWLockExclusive(&channel_lock);
    }
}
}
extern "C" void tb_start_input() {
    const auto thread = CreateThread(nullptr, 0, serve, nullptr, 0, nullptr);
    if (thread) CloseHandle(thread);
}
