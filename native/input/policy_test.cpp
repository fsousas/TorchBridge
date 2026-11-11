#ifdef NDEBUG
#undef NDEBUG
#endif
#include "wire.h"
#include "interaction.h"
#include <cassert>
#include <initializer_list>
#include <limits>
using namespace tbinput;
int main() {
    Command command{};
    std::memcpy(command.magic, magic, 8);
    command.version = version;
    command.radius = 4.5f;
    uint8_t token[16]{};
    assert(valid(command, token));
    command.dx = std::numeric_limits<float>::quiet_NaN();
    assert(!valid(command, token));
    command.dx = 2.f;
    assert(!valid(command, token));
    command.dx = 0;
    command.flags = 16;
    assert(!valid(command, token));
    command.flags = 0;
    command.token[0] = 1;
    assert(!valid(command, token));
    assert(newer(1, 0xffffffffu) && !newer(0xffffffffu, 1) && !newer(2, 2));
    ActionLatch latch;
    assert(!latch.consume(1, 7) && !latch.consume(1, 7));
    assert(latch.consume(1, 8) && !latch.consume(1, 8));
    assert(!latch.consume(2, 8) && !latch.consume(2, 8));
    assert(latch.consume(2, 9));
    command.action_age = 150;
    assert(recent_action(command, 50) && !recent_action(command, 51));
    command.action_age = 5000;
    assert(!recent_action(command, 0)); // Frozen game cannot revive an old press.
    Candidate a{200, 1, 0, 0, 1}, b{100, 1, 0, 0, 2}, c{300, 0.5f, 0, 0, 3};
    assert(nearer(b, a, 0, 0) && nearer(c, b, 0, 0));
    assert(in_range(a, 0, 0, 0, 1) && !in_range(a, 0, 3, 0, 4.5f));
    a.x = std::numeric_limits<float>::infinity();
    assert(!in_range(a, 0, 0, 0, 4.5f));

    // Stairs/entrances emit state outputs on the next frame, after the
    // synchronous Interact scope has ended. Only that exact output may warp.
    for (uint32_t state : {0u, 1u}) {
        TriggerEvent event;
        event.arm(200, 10, 20, 46 + state, 1, 1500, true);
        assert(!event.consume(201, 10, 20, 46 + state, 1, 16, true, true));
        assert(!event.consume(200, 10, 20, 29, 1, 16, true, true));
        assert(!event.consume(200, 10, 20, 47 - state, 1, 16, true, true));
        assert(event.consume(200, 10, 20, 0, 1, 16, true, true));
        assert(!event.consume(200, 10, 20, 0, 1, 16, true, true));
        assert(event.consume(200, 10, 20, 46 + state, 1, 16, true, true));
        assert(!event.consume(200, 10, 20, 46 + state, 1, 17, true, true));
    }
    // Focus, connection, scene, menu/lease cancellation cannot leave an old
    // press available when input resumes, even before its original deadline.
    for (unsigned cancelled = 0; cancelled != 6; ++cancelled) {
        TriggerEvent event;
        event.arm(200, 10, 20, 47, 1, 1500, true);
        assert(!event.consume(200, cancelled == 0 ? 11 : 10, cancelled == 1 ? 21 : 20,
            47, cancelled == 2 ? 2 : 1, cancelled == 3 ? 1501 : 16,
            cancelled != 4, cancelled != 5));
        assert(!event.consume(200, 10, 20, 47, 1, 17, true, true));
    }
    TriggerEvent mouse;
    mouse.arm(200, 10, 20, 47, 1, 1500, false);
    assert(mouse.consume(200, 10, 20, 47, 1, 16, true, false));
}
