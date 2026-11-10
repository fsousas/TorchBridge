#pragma once
#include <cmath>
#include <cstdint>
#include <cstring>

namespace tbinput {
constexpr char magic[8] = {'T','B','I','N','P','0','0','2'};
constexpr uint32_t version = 2;
constexpr uint32_t active = 1, direct = 2, walking = 4, allow_interaction = 8;
constexpr uint32_t ready = 1, protected_world = 2, highlighted = 4, moving = 8, complete = 16;
enum Reason : uint32_t { idle, walking_now, no_session, no_focus, wrong_scene, menu,
    skill_lock, no_target, acting, unsupported, incomplete, transport_error };
enum ActionResult : uint32_t { none, accepted, unavailable, changed_target, blocked };
#pragma pack(push, 1)
struct Endpoint {
    char magic[8];
    uint32_t version, port;
    uint8_t token[16];
    uint32_t pid, image_base, capabilities, error;
};
struct Command {
    char magic[8];
    uint32_t version, sequence;
    uint8_t token[16];
    uint32_t flags, player, level;
    float dx, dz, radius;
    uint32_t action, target;
};
struct Reply {
    char magic[8];
    uint32_t version, sequence, flags, reason, selected, executed, action_result, count;
    float destination_x, destination_z;
    uint32_t lease_age, blocked_interactions, blocked_warps, frames;
};
#pragma pack(pop)
static_assert(sizeof(Endpoint) == 48 && sizeof(Command) == 64 && sizeof(Reply) == 64);

inline bool newer(uint32_t a, uint32_t b) { return static_cast<int32_t>(a - b) > 0; }
inline bool valid(const Command& c, const uint8_t* token) {
    return !std::memcmp(c.magic, magic, 8) && c.version == version &&
        !std::memcmp(c.token, token, 16) && (c.flags & ~15u) == 0 &&
        std::isfinite(c.dx) && std::isfinite(c.dz) && std::isfinite(c.radius) &&
        std::hypot(c.dx, c.dz) <= 1.001f && c.radius >= 0.5f && c.radius <= 8.f;
}
struct Candidate {
    uintptr_t address = 0;
    float x = 0, y = 0, z = 0;
    uint32_t type = 0; // 1 character, 2 item, 3 warper
};
inline double distance2(const Candidate& c, float x, float z) {
    return (double(c.x) - x) * (double(c.x) - x) + (double(c.z) - z) * (double(c.z) - z);
}
inline bool nearer(const Candidate& a, const Candidate& b, float x, float z) {
    const auto da = distance2(a, x, z), db = distance2(b, x, z);
    return da < db || (da == db && a.address < b.address);
}
inline bool in_range(const Candidate& c, float x, float y, float z, float radius) {
    return std::isfinite(c.x) && std::isfinite(c.y) && std::isfinite(c.z) &&
        std::fabs(c.y - y) <= 2.5f && distance2(c, x, z) <= double(radius) * radius;
}
}
