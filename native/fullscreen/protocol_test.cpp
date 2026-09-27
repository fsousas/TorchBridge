// Portable checks for the wire protocol; no Windows API or graphics required.
#include "protocol.h"
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <cassert>
#include <cstdint>

int main() {
    tb::Header h{};
    h.magic = tb::magic; h.version = tb::version; h.header_size = sizeof(h);
    h.width = 1920; h.height = 1080; h.stride = h.width * 4;
    h.visible = 1; h.producer_tick = 1000;
    assert(tb::valid_frame(h, 1001));
    assert(!tb::valid_frame(h, 2501));
    h.producer_tick = 0xffffff00;
    assert(tb::valid_frame(h, 0x100));
    h.width = 0xffffffff;
    assert(!tb::valid_frame(h, 0x100));
    h.width = 1920; h.stride = 1;
    assert(!tb::valid_frame(h, 0x100));
    h.stride = h.width * 4; h.height = 4097;
    assert(!tb::valid_frame(h, 0x100));
    h.height = 1080; h.visible = 0;
    assert(!tb::valid_frame(h, 0x100));
    h.visible = 1; h.version = 99;
    assert(!tb::valid_frame(h, 0x100));
}
