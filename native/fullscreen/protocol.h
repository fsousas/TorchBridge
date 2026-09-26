#pragma once
#include <cstddef>
#include <cstdint>

namespace tb {
constexpr std::uint32_t magic = 0x54424f31;
constexpr std::uint32_t version = 1;
constexpr std::uint32_t max_dimension = 4096;
constexpr std::uint32_t timeout_ms = 1500;

struct Header {
    std::uint32_t magic, version, header_size;
    std::uint32_t width, height, stride, visible, sequence, producer_tick;
    std::uint32_t consumer_tick, backbuffer_width, backbuffer_height;
    std::uint32_t fullscreen, ready, max_width, max_height;
};
static_assert(sizeof(Header) == 64);
static_assert(offsetof(Header, consumer_tick) == 36);
constexpr std::size_t map_size = sizeof(Header) + max_dimension * max_dimension * 4u;

inline bool valid_protocol(const Header& h) noexcept {
    return h.magic == magic && h.version == version && h.header_size == sizeof(Header);
}
inline bool valid_frame(const Header& h, std::uint32_t now) noexcept {
    return valid_protocol(h) && h.visible == 1 &&
        now - h.producer_tick <= timeout_ms &&
        h.width > 0 && h.width <= max_dimension &&
        h.height > 0 && h.height <= max_dimension && h.stride == h.width * 4;
}
} // namespace tb
