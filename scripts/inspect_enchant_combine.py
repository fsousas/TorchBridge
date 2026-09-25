from torchbridge.memory import TorchlightMemoryReader

reader = TorchlightMemoryReader()
if reader._ensure_handle():
    for addr in [0x00E7C380, 0x00E7C250, 0x00E7C088, 0x00E7C1B8, 0x00E7C418]:
        bytes_dump = [reader.read_u8(addr + i) for i in range(32)]
        print(f"0x{addr:08X}: {bytes_dump}")
