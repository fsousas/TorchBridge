#ifdef NDEBUG
#undef NDEBUG
#endif
// Run the actual game-thread dispatcher against synthetic NPCs/items/pathfinding.
// No window, controller, mouse event or game installation is needed.
#include "runtime.cpp"
#include <cassert>
#include <cstdio>

void tb_start_linux_memory() {}
namespace {
ULONGLONG test_now = 10000;
bool test_focus = true, navigation_available = true, advance_path = true;
unsigned npc_updates = 0;
bool collect_immediately = false, collect_next_update = false;
unsigned pickup_calls = 0, fishing_calls = 0;
std::vector<std::pair<float, float>> destinations;
DWORD WINAPI test_window(HWND, LPDWORD pid) {
    *pid = test_focus ? GetCurrentProcessId() : 0;
    return 0;
}
ULONGLONG WINAPI test_clock() { return test_now; }
template<class T> void put(uintptr_t p, size_t offset, T value) {
    std::memcpy(reinterpret_cast<void*>(p + offset), &value, sizeof value);
}
void __fastcall test_target(void* self, void*, void* target) {
    put<uint32_t>(reinterpret_cast<uintptr_t>(self), 0x290, reinterpret_cast<uintptr_t>(target));
}
void __fastcall test_item(void* self, void*, void* target) {
    put<uint32_t>(reinterpret_cast<uintptr_t>(self), 0x298, reinterpret_cast<uintptr_t>(target));
}
void __fastcall test_stop(void* self, void*) {
    put<uint8_t>(reinterpret_cast<uintptr_t>(self), 0x208, 0);
}
void __fastcall test_mode(void* self, void*, int mode) {
    put<uint32_t>(reinterpret_cast<uintptr_t>(self), 0x284, mode);
}
void __fastcall test_move(void* self, void*, void*, float x, float z) {
    destinations.emplace_back(x, z);
    put<uint8_t>(reinterpret_cast<uintptr_t>(self), 0x208, navigation_available ? 1 : 0);
}
float* __fastcall test_position(void* self, void*, float* out, int) {
    read_raw(reinterpret_cast<uintptr_t>(self) + 0x70, out, 12);
    return out;
}
bool __fastcall test_is_a(void*, void*, int type) { return type == 131; }
void __fastcall test_highlight(void*, void*, bool) {}
uint32_t __fastcall test_interact(void*, void*, void*) { return 1; }
void complete_pickup(void* self) {
    const auto hero = reinterpret_cast<uintptr_t>(self);
    const auto item = field<uint32_t>(hero, 0x298);
    if (item) put<uint8_t>(item, 0x19D, 1);
    test_item(self, nullptr, nullptr);
    test_mode(self, nullptr, 0);
    test_stop(self, nullptr);
}
void __fastcall test_pickup(void* self, void*, float, void*) {
    ++pickup_calls;
    if (collect_immediately) complete_pickup(self);
}
void __fastcall test_fishing(void* self, void*) {
    ++fishing_calls;
    test_mode(self, nullptr, 32);
}
bool __fastcall test_range(void*, void*, bool) { return true; }
bool __fastcall test_sight(void*, void*, void*, bool) { return true; }
bool __fastcall test_attack(void* self, void*) {
    const auto hero = reinterpret_cast<uintptr_t>(self);
    test_mode(self, nullptr, 3);
    put<uint32_t>(hero, 0x2D0, hero);
    put<uint8_t>(hero, 0x20B, 1);
    return true;
}
void __fastcall test_update(void* self, void*, uint32_t, uint32_t, float) {
    const auto hero = reinterpret_cast<uintptr_t>(self);
    if (field<uint32_t>(hero, 0x284) == 7 && collect_next_update) complete_pickup(self);
    if (field<uint32_t>(hero, 0x284) != 9) return;
    ++npc_updates;
    const auto npc = field<uint32_t>(hero, 0x290);
    const auto distance = npc ? field<float>(npc, 0x70) - field<float>(hero, 0x70) : 100.f;
    // Native talk never starts navigation: it gives up when far and idle,
    // or advances to the dialog/service state once the path brings it close.
    if (distance <= 2.f) {
        test_stop(self, nullptr);
        test_mode(self, nullptr, 30);
    } else if (!field<uint8_t>(hero, 0x208)) {
        test_target(self, nullptr, nullptr);
        test_mode(self, nullptr, 2);
    } else if (advance_path) {
        put<float>(hero, 0x70, field<float>(hero, 0x70) + .4f);
    }
}
struct Fixture {
    std::array<uint8_t, 0x100> game{}, client{};
    std::array<uint8_t, 0xA20> hero{}, npc{};
    std::array<uint8_t, 0x300> level{};
    std::array<uint8_t, 0x1700> ui{};
    std::array<uint8_t, 0xD88> manager{};
    std::array<uint32_t, 0x200 / 4> hero_vt{}, npc_vt{};
    std::array<uint32_t, 2> node{};
    uint32_t characters = 0, items = 0, game_object = 0;
    uintptr_t h = reinterpret_cast<uintptr_t>(hero.data()), n = reinterpret_cast<uintptr_t>(npc.data());
    uintptr_t map = reinterpret_cast<uintptr_t>(level.data());
    Fixture(float distance = 4.49f, float radius = 4.5f) {
        test_now += 10000; test_focus = navigation_available = advance_path = true;
        npc_updates = 0; destinations.clear();
        collect_immediately = collect_next_update = false; pickup_calls = fishing_calls = 0;
        image = 0x10000; image_end = UINT32_MAX; classes.clear();
        const auto hvt = reinterpret_cast<uintptr_t>(hero_vt.data());
        const auto nvt = reinterpret_cast<uintptr_t>(npc_vt.data());
        classes[hvt] = {player | character, "CPlayer"};
        classes[nvt] = {character, "CMonster"};
        put<uint32_t>(h, 0, hvt); put<uint32_t>(n, 0, nvt);
        put<uint32_t>(h, 0x2F0, UINT32_MAX); put<uint32_t>(h, 0x2F4, UINT32_MAX);
        hero_vt[0x174 / 4] = reinterpret_cast<uintptr_t>(&test_mode);
        hero_vt[0x16C / 4] = reinterpret_cast<uintptr_t>(&test_fishing);
        npc_vt[0x100 / 4] = reinterpret_cast<uintptr_t>(&test_highlight);
        for (const auto offset : {0x6Eu, 0x161u}) put<uint8_t>(n, offset, 1);
        put<uint32_t>(n, 0x28C, 3); put<float>(n, 0x394, 100.f);
        put<float>(n, 0x70, distance);
        node = {static_cast<uint32_t>(n), 0};
        characters = reinterpret_cast<uintptr_t>(node.data());
        put<uint32_t>(map, 0x5C, reinterpret_cast<uintptr_t>(&characters));
        put<uint32_t>(map, 0x68, reinterpret_cast<uintptr_t>(&items));
        const auto c = reinterpret_cast<uintptr_t>(client.data());
        const auto u = reinterpret_cast<uintptr_t>(ui.data());
        put<uint32_t>(c, 0x2C, h); put<uint32_t>(c, 0x38, map); put<uint32_t>(c, 0x3C, u);
        put<uint32_t>(u, 0x169C, 6);
        put<uint32_t>(u, 0x324, reinterpret_cast<uintptr_t>(manager.data()));
        put<uint32_t>(reinterpret_cast<uintptr_t>(manager.data()), 0xD84, 6);
        game_object = reinterpret_cast<uintptr_t>(game.data());
        game_global = reinterpret_cast<uintptr_t>(&game_object);
        put<uint32_t>(game_object, 0x64, c);
        scene = {c, h, map, u};
        authorized_target = highlighted_object = highlight_level = 0;
        stationary_attack = was_moving = false;
        actions = {}; status = {}; latest = {};
        strict_world = strict_warps = true;
        current_generation = connection_generation = 1;
        original_target = reinterpret_cast<TargetFn>(&test_target);
        original_item = reinterpret_cast<TargetFn>(&test_item);
        stop_path = reinterpret_cast<VoidFn>(&test_stop);
        move_to = reinterpret_cast<MoveFn>(&test_move);
        get_position = reinterpret_cast<PositionFn>(&test_position);
        is_a = reinterpret_cast<IsaFn>(&test_is_a);
        original_update = test_update;
        latest.flags = active | direct | allow_interaction | world_action;
        latest.player = h; latest.level = map; latest.radius = radius;
        received_at = test_now;
        frame(); // Prime the connection without replaying a held action.
        assert(status.selected == n);
    }
    void as_item(uint32_t type, float distance, float radius = 0) {
        characters = 0; items = reinterpret_cast<uintptr_t>(node.data());
        const auto vt = reinterpret_cast<uintptr_t>(npc_vt.data());
        classes[vt] = {item | (type == 4 ? breakable : type == 3 ? 0u : trigger), "CItem"};
        npc_vt[0x13C / 4] = reinterpret_cast<uintptr_t>(&test_interact);
        interact_hooks.emplace(reinterpret_cast<uintptr_t>(&test_interact), 0);
        hero_vt[0x1B4 / 4] = reinterpret_cast<uintptr_t>(&test_pickup);
        put<uint8_t>(n, 0x19C, 1);
        put<float>(n, 0x70, distance); put<float>(n, 0x15C, radius);
        put<uint32_t>(n, 0x174, type == 5 ? 122 : 0);
        basic_attack = reinterpret_cast<AttackFn>(&test_attack);
        attack_in_range = reinterpret_cast<RangeFn>(&test_range);
        attack_in_sight = reinterpret_cast<SightFn>(&test_sight);
        latest.flags = active | direct | allow_interaction |
            (type == 4 ? attack_action : type == 3 ? pickup_action : world_action);
        frame();
    }
    void press() { ++latest.action; received_at = test_now; frame(); }
    void step(ULONGLONG milliseconds = 250) {
        test_now += milliseconds; received_at = test_now;
        update_hook(hero.data(), nullptr, 0, 0, milliseconds / 1000.f);
    }
    void walk() { latest.flags |= walking; latest.dx = -1.f; latest.dz = 0; step(16); }
};
}
int main() {
    assert(MH_Initialize() == MH_OK);
    assert(MH_CreateHook(reinterpret_cast<void*>(&GetWindowThreadProcessId),
        reinterpret_cast<void*>(&test_window), nullptr) == MH_OK);
    assert(MH_CreateHook(reinterpret_cast<void*>(&GetTickCount64),
        reinterpret_cast<void*>(&test_clock), nullptr) == MH_OK);
    assert(MH_EnableHook(MH_ALL_HOOKS) == MH_OK);
    for (const auto radius : {4.5f, 8.f}) {
        Fixture f(radius - .01f, radius);
        const auto start = test_now;
        f.press();
        if (destinations.empty()) {
            std::fprintf(stderr, "NPC edge regression: talk state was issued without a navigation path\n");
            return 10;
        }
        assert(destinations.size() == 1 && destinations[0].first == radius - .01f);
        assert(field<uint32_t>(f.h, 0x284) == 9 && !status.executed);
        for (unsigned i = 0; i < 24 && authorized_target; ++i) f.step();
        assert(test_now - start > 1500); // A slow/long path must keep progressing.
        assert(field<uint32_t>(f.h, 0x284) == 30 && !authorized_target);
        assert(status.executed == f.n && status.action_result == accepted);
    }
    {
        Fixture f; f.press(); f.walk();
        assert(!authorized_target && !npc_updates && !field<uint32_t>(f.h, 0x290));
        assert(destinations.size() == 2 && destinations.back().first < 0);
        assert(status.flags & moving); // Same update, no 1.5 second lockout.
    }
    {
        Fixture f; navigation_available = false; f.press(); f.step(16);
        assert(!authorized_target && !status.executed && status.action_result == unavailable);
        navigation_available = true; f.walk();
        assert((status.flags & moving) && field<uint8_t>(f.h, 0x208));
    }
    {
        Fixture f; advance_path = false; f.press(); f.step(1490);
        assert(authorized_target); f.step(11);
        assert(!authorized_target && !field<uint32_t>(f.h, 0x290));
    }
    {
        Fixture f; f.press(); f.characters = 0; f.step();
        assert(!authorized_target && !field<uint32_t>(f.h, 0x290));
        f.walk(); assert(status.flags & moving);
    }
    {
        Fixture f; f.press();
        put<uint32_t>(f.h, 0x284, 3);
        put<uint32_t>(f.h, 0x2D0, f.map); put<uint8_t>(f.h, 0x20B, 1);
        f.step(16);
        assert(!authorized_target && !status.executed && status.action_result == unavailable);
        assert(field<uint8_t>(f.h, 0x208)); // The skill owns this path now.
    }
    for (unsigned cancelled = 0; cancelled != 3; ++cancelled) {
        Fixture f; f.press();
        if (cancelled == 0) test_focus = false;
        if (cancelled == 1) latest.flags &= ~direct;
        if (cancelled == 2) put<uint32_t>(reinterpret_cast<uintptr_t>(f.manager.data()), 0xD84, 7);
        f.step(16);
        assert(!authorized_target && !field<uint32_t>(f.h, 0x290) && !field<uint8_t>(f.h, 0x208));
    }
    // Selection and the use dispatcher agree on exclusive destructible/fishing
    // ranges, including the exact circle contact point and the next .01 unit.
    for (const auto type : {2u, 3u, 4u, 5u}) {
        Fixture f;
        const auto limit = type == 4 ? 9.f : type == 5 ? 7.75f : 4.5f;
        f.as_item(type, limit, 3.25f);
        assert(status.selected == f.n);
        put<float>(f.n, 0x70, limit + .01f); f.step(16);
        assert(!status.selected && (status.flags & complete));
    }
    for (const auto close_to_water : {true, false}) {
        Fixture f; f.as_item(5, 0);
        put<float>(f.n, 0x70, -9.37f); put<float>(f.n, 0x78, 14.2f);
        put<float>(f.h, 0x70, close_to_water ? -8.85f : -7.91f);
        put<float>(f.h, 0x78, close_to_water ? 16.64f : 20.21f);
        put<float>(f.h, 0x74, close_to_water ? 4.f : 0.f);
        f.step(16);
        assert(status.selected == f.n);
        f.press();
        assert(fishing_calls == 1 && pickup_calls == 0 && destinations.empty());
        assert(status.executed == f.n && !authorized_target);
        assert(field<uint32_t>(f.h, 0x284) == 32 && field<uint32_t>(f.h, 0x298) == f.n);
        assert(field<float>(f.h, 0x70) == (close_to_water ? -8.85f : -7.91f));
        for (uint32_t mode : {32u, 33u, 34u}) {
            put<uint32_t>(f.h, 0x284, mode);
            f.walk(); // Even an old client cannot interrupt the cast/reel gap.
            assert(status.reason == menu && destinations.empty());
            assert(field<uint32_t>(f.h, 0x284) == mode);
        }
    }
    for (bool immediate : {true, false}) {
        Fixture f; f.as_item(3, 1.f);
        collect_immediately = immediate;
        f.press();
        assert(pickup_calls == 1);
        if (!immediate) {
            assert(authorized_target == f.n);
            collect_next_update = true; f.step(16);
        }
        assert(!authorized_target && !field<uint32_t>(f.h, 0x298));
        f.walk(); assert(status.flags & moving);
        assert(pickup_calls == 1); // Held/old action cannot collect another item.
    }
    {
        Fixture f; f.as_item(3, 4.49f); f.press();
        assert(authorized_target == f.n);
        collect_next_update = true; f.walk();
        assert(!authorized_target && !field<uint8_t>(f.n, 0x19D));
        assert(status.flags & moving); // Cancels before the old pickup AI runs.
    }
    {
        Fixture f; f.as_item(4, 8.99f); f.press();
        assert(!authorized_target && stationary_attack && !pickup_calls);
        assert(status.executed == f.n && locked());
        f.walk();
        assert(status.reason == skill_lock && destinations.empty());
        put<uint32_t>(f.h, 0x2D0, 0); put<uint8_t>(f.h, 0x20B, 0);
        f.walk();
        assert(status.flags & moving); // First free frame, far before 1500 ms.
        assert(!stationary_attack && !field<uint32_t>(f.h, 0x298));
    }
    assert(MH_DisableHook(MH_ALL_HOOKS) == MH_OK);
    assert(MH_Uninitialize() == MH_OK);
}
