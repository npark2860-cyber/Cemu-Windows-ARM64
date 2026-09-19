#pragma once
#include <cstdint>
#include <vector>
using uint8 = uint8_t;
using uint16 = uint16_t;
using uint32 = uint32_t;
using uint64 = uint64_t;
inline std::vector<uint8> testMemory(2 * 1024 * 1024);
inline uint32 testAccessibleSize = static_cast<uint32>(testMemory.size());
inline bool memory_isAddressRangeAccessible(uint32 address, uint32 size)
{
	return static_cast<uint64>(address) + size <= testAccessibleSize;
}
inline uint8* memory_getPointerFromVirtualOffset(uint32 address)
{
	return testMemory.data() + address;
}
