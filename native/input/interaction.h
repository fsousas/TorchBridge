#pragma once
#include <cstdint>

namespace tbinput {
// CTriggerUnit emits Triggered (0), then its state output (46/47), on its next
// Update after Interact/Activate return. Authorize each output once, because
// layouts may wire the warper to either one.
struct TriggerEvent {
    uintptr_t object = 0, player = 0, level = 0;
    uint32_t event = 0, generation = 0;
    uint64_t expires = 0;
    bool needs_session = false;
    uint8_t pending_outputs = 0;

    void clear() { object = 0; pending_outputs = 0; }
    void arm(uintptr_t target, uintptr_t hero, uintptr_t map, uint32_t output,
             uint32_t connection, uint64_t until, bool session) {
        object = target; player = hero; level = map; event = output;
        generation = connection; expires = until; needs_session = session;
        pending_outputs = 3;
    }
    bool consume(uintptr_t target, uintptr_t hero, uintptr_t map, uint32_t output,
                 uint32_t connection, uint64_t now, bool focused, bool session) {
        if (!object) return false;
        if (hero != player || map != level || connection != generation ||
            now > expires || !focused || (needs_session && !session)) {
            clear();
            return false;
        }
        if (target != object) return false;
        const uint8_t bit = output == 0 ? 1 : output == event ? 2 : 0;
        if (!(pending_outputs & bit)) return false;
        pending_outputs &= ~bit;
        if (!pending_outputs) clear();
        // Consume before dispatch; recursive/repeated outputs cannot replay it.
        return true;
    }
};
}
