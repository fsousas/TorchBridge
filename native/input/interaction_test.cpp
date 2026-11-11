#ifdef NDEBUG
#undef NDEBUG
#endif
// Exercise the real runtime hooks with synthetic game objects. No game,
// controller, window, cursor movement or desktop input is needed.
#include "runtime.cpp"
#include <cassert>

void tb_start_linux_memory() {}
namespace {
bool test_focus = true;
unsigned warps = 0;
uint32_t next_state = 0;
uint32_t warp_event = 0;
uintptr_t attack_item = 0;
bool within_reach = true, visible = true, attack_ready = true;
unsigned attacks = 0, pickups = 0, path_stops = 0;
int ai_mode = -1;
void __fastcall test_target(void*, void*, void*) {}
void __fastcall test_target_item(void*, void*, void* target) {
    attack_item = reinterpret_cast<uintptr_t>(target);
}
void __fastcall test_stop(void*, void*) { ++path_stops; }
void __fastcall test_mode(void*, void*, int mode) { ai_mode = mode; }
void __fastcall test_pickup(void*, void*, float, void*) { ++pickups; }
bool __fastcall test_range(void*, void*, bool) { return within_reach; }
bool __fastcall test_sight(void*, void*, void* level, bool) {
    assert(reinterpret_cast<uintptr_t>(level) == scene.level);
    return visible;
}
bool __fastcall test_attack(void*, void*) {
    assert(attack_item && ai_mode == 0);
    ++attacks;
    return attack_ready;
}
DWORD WINAPI window_process(HWND, LPDWORD pid) {
    *pid = test_focus ? GetCurrentProcessId() : 0;
    return 0;
}
void __fastcall test_warp(void*, void*) { ++warps; }
void __fastcall test_signal(void* self, void* edx, uint32_t event) {
    if (event == warp_event) warp_hook(self, edx);
}
uint32_t __fastcall test_item(void*, void*, void*) { return 1; }
template<class T> void put(uintptr_t p, size_t offset, T value) {
    std::memcpy(reinterpret_cast<void*>(p + offset), &value, sizeof value);
}
uint32_t __fastcall test_activate(void* self, void* edx, void* user) {
    // Like CTriggerUnit::Activate: schedule a state output, then dispatch the
    // base CItem::Interact. That nested call consumes authorized_target.
    const auto p = reinterpret_cast<uintptr_t>(self);
    put<uint32_t>(p, 0x1EC, next_state);
    put<uint8_t>(p, 0x201, 1);
    return interact_hook<0>(self, edx, user);
}
uint32_t __fastcall test_trigger(void* self, void* edx, void* user) {
    return activate_hook(self, edx, user);
}
}
int main() {
    assert(MH_Initialize() == MH_OK);
    assert(MH_CreateHook(reinterpret_cast<void*>(&GetWindowThreadProcessId),
        reinterpret_cast<void*>(&window_process), nullptr) == MH_OK);
    assert(MH_EnableHook(MH_ALL_HOOKS) == MH_OK);
    original_activate = test_activate;
    original_interacts[0] = test_item;
    original_interacts[1] = test_trigger;
    original_signal = test_signal;
    original_warp = test_warp;
    std::array<uint8_t, 0x300> prop{};
    std::array<uint8_t, 0x100> game{}, client{};
    std::array<uint8_t, 0x1700> ui{};
    std::array<uint8_t, 0xD88> manager{};
    const auto object = reinterpret_cast<uintptr_t>(prop.data());
    game_global = reinterpret_cast<uintptr_t>(&image);
    image = reinterpret_cast<uintptr_t>(game.data());
    scene = {reinterpret_cast<uintptr_t>(client.data()), 0x10000, 0x20000,
             reinterpret_cast<uintptr_t>(ui.data())};
    put<uint32_t>(image, 0x64, scene.client);
    put<uint32_t>(scene.client, 0x2C, scene.player);
    put<uint32_t>(scene.client, 0x38, scene.level);
    put<uint32_t>(scene.ui, 0x169C, 6);
    put<uint32_t>(scene.ui, 0x324, reinterpret_cast<uintptr_t>(manager.data()));
    put<uint32_t>(reinterpret_cast<uintptr_t>(manager.data()), 0xD84, 6);
    current_generation = connection_generation = 1;
    latest.flags = active | direct | allow_interaction;
    latest.player = scene.player; latest.level = scene.level;
    strict_world = strict_warps = true;
    for (const auto offset : {0x6E, 0x161, 0x19C}) put<uint8_t>(object, offset, 1);
    // An automatic activation still cannot create a transition authorization.
    assert(activate_hook(prop.data(), nullptr, nullptr) == 0);
    assert(!trigger_event.object && status.blocked_interactions == 1);
    auto press = [&] {
        received_at = GetTickCount64();
        authorized_target = object;
        authorized_player = scene.player; authorized_level = scene.level;
        authorized_until = received_at + 1500;
        assert(interact_hook<1>(prop.data(), nullptr, reinterpret_cast<void*>(scene.player)) == 1);
        assert(!scope && !authorized_target && trigger_event.object == object);
    };
    for (next_state = 0; next_state <= 1; ++next_state) {
      for (const auto output : {0u, 46 + next_state}) {
        warp_event = output;
        const auto before = warps;
        press();
        warp_hook(prop.data(), nullptr); // Unrelated proximity warper.
        signal_hook(prop.data() + 4, nullptr, output);
        signal_hook(prop.data(), nullptr, 47 - next_state);
        assert(warps == before && trigger_event.object == object);
        // Actual Update order: Triggered (0) first, then state 0/1 (46/47).
        // Mine Entrance wires its warper to 0, not to the state output.
        signal_hook(prop.data(), nullptr, 0);
        assert(warps == before + (output == 0 ? 1 : 0) && !scope);
        signal_hook(prop.data(), nullptr, 0);
        assert(warps == before + (output == 0 ? 1 : 0));
        signal_hook(prop.data(), nullptr, 46 + next_state);
        assert(warps == before + 1 && !scope && !trigger_event.object);
        signal_hook(prop.data(), nullptr, 46 + next_state);
        assert(warps == before + 1); // Cannot replay on the next frame.
      }
    }
    next_state = 1;
    warp_event = 0;
    for (unsigned cancelled = 0; cancelled != 5; ++cancelled) {
        press();
        const auto before = warps;
        if (cancelled == 0) received_at = 0;
        if (cancelled == 1) latest.flags &= ~allow_interaction;
        if (cancelled == 2) test_focus = false;
        if (cancelled == 3) put<uint32_t>(scene.client, 0x38, scene.level + 4);
        if (cancelled == 4) ++connection_generation;
        signal_hook(prop.data(), nullptr, 0);
        assert(warps == before && !trigger_event.object && !scope);
        received_at = GetTickCount64();
        latest.flags |= allow_interaction;
        test_focus = true;
        put<uint32_t>(scene.client, 0x38, scene.level);
        connection_generation = current_generation;
        signal_hook(prop.data(), nullptr, 0);
        signal_hook(prop.data(), nullptr, 47);
        assert(warps == before);
    }
    // Both barrel variants and any CBreakable subclass take the stationary
    // attack branch. It must never call pickup, select state 7 or grant use/warp.
    std::array<uint8_t, 0x700> hero{};
    std::array<uint32_t, 0x200 / 4> hero_vtable{};
    scene.player = reinterpret_cast<uintptr_t>(hero.data());
    put<uint32_t>(scene.player, 0, reinterpret_cast<uintptr_t>(hero_vtable.data()));
    hero_vtable[0x174 / 4] = reinterpret_cast<uintptr_t>(&test_mode);
    hero_vtable[0x1B4 / 4] = reinterpret_cast<uintptr_t>(&test_pickup);
    original_target = reinterpret_cast<TargetFn>(&test_target);
    original_item = reinterpret_cast<TargetFn>(&test_target_item);
    stop_path = reinterpret_cast<VoidFn>(&test_stop);
    basic_attack = reinterpret_cast<AttackFn>(&test_attack);
    attack_in_range = reinterpret_cast<RangeFn>(&test_range);
    attack_in_sight = reinterpret_cast<SightFn>(&test_sight);
    Candidate barrel{object, 4, 0, 0, 4};
    use(barrel, GetTickCount64());
    assert(attacks == 1 && !pickups && path_stops == 1 && ai_mode == 0);
    assert(attack_item == object && stationary_attack && !authorized(object));
    assert(status.executed == object && status.action_result == accepted && !scope);
    put<uint32_t>(scene.client, 0x2C, scene.player);
    latest.player = scene.player;
    // Losing focus cancels the combat target before the next original AI tick.
    test_focus = false;
    cancel_before_update(hero.data());
    assert(!authorized_target && !stationary_attack && !attack_item);
    test_focus = true;
    // A melee weapon outside its reach, a wall or cooldown must not make the
    // character approach the barrel, nor bypass the original combat checks.
    for (unsigned refused = 0; refused != 3; ++refused) {
        within_reach = refused != 0; visible = refused != 1; attack_ready = refused != 2;
        const auto before = attacks;
        use(barrel, GetTickCount64());
        assert(attacks == before + (refused == 2 ? 1 : 0));
        assert(!pickups && ai_mode == 0 && !attack_item && !authorized_target);
        assert(status.action_result == unavailable && !scope);
    }
    // Non-destructible props retain their native approach/use behavior.
    barrel.type = 2;
    use(barrel, GetTickCount64());
    assert(pickups == 1 && ai_mode == 7 && !stationary_attack);
    assert(MH_DisableHook(MH_ALL_HOOKS) == MH_OK);
    assert(MH_Uninitialize() == MH_OK);
}
