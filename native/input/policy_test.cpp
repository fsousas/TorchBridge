#ifdef NDEBUG
#undef NDEBUG
#endif
#include "wire.h"
#include <cassert>
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
    Candidate a{200, 1, 0, 0, 1}, b{100, 1, 0, 0, 2}, c{300, 0.5f, 0, 0, 3};
    assert(nearer(b, a, 0, 0) && nearer(c, b, 0, 0));
    assert(in_range(a, 0, 0, 0, 1) && !in_range(a, 0, 3, 0, 4.5f));
    a.x = std::numeric_limits<float>::infinity();
    assert(!in_range(a, 0, 0, 0, 4.5f));
}
