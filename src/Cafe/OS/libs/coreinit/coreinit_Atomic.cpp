#include "Cafe/OS/common/OSCommon.h"
#include <atomic>
#include <cstdint>
#include <cstring>
#include <mutex>
#include "coreinit_Atomic.h"

namespace coreinit
{
	namespace
	{
		std::mutex s_unalignedAtomic64Mutex;

		bool isAtomic64Aligned(const void* mem)
		{
			return (reinterpret_cast<std::uintptr_t>(mem) % alignof(std::atomic<uint64be>)) == 0;
		}

		uint64be loadUnalignedAtomic64(const void* mem)
		{
			uint64be value;
			std::memcpy(&value, mem, sizeof(value));
			return value;
		}

		void storeUnalignedAtomic64(void* mem, const uint64be& value)
		{
			std::memcpy(mem, &value, sizeof(value));
		}
	}

	/* 32bit atomic operations */

	uint32 OSSwapAtomic(std::atomic<uint32be>* mem, uint32 newValue)
	{
		uint32be _newValue = newValue;
		uint32be previousValue = mem->exchange(_newValue);
		return previousValue;
	}

	bool OSCompareAndSwapAtomic(std::atomic<uint32be>* mem, uint32 compareValue, uint32 swapValue)
	{
		// seen in GTA3 homebrew port
		uint32be _compareValue = compareValue;
		uint32be _swapValue = swapValue;
		return mem->compare_exchange_strong(_compareValue, _swapValue);
	}

	bool OSCompareAndSwapAtomicEx(std::atomic<uint32be>* mem, uint32 compareValue, uint32 swapValue, uint32be* previousValue)
	{
		// seen in GTA3 homebrew port
		uint32be _compareValue = compareValue;
		uint32be _swapValue = swapValue;
		bool r = mem->compare_exchange_strong(_compareValue, _swapValue);
		*previousValue = _compareValue;
		return r;
	}

	uint32 OSAddAtomic(std::atomic<uint32be>* mem, uint32 adder)
	{
        // used by SDL Wii U port
		uint32be knownValue;
		while (true)
		{
			knownValue = mem->load();
			uint32be newValue = knownValue + adder;
			if (mem->compare_exchange_strong(knownValue, newValue))
				break;
		}
		return knownValue;
	}

	/* 64bit atomic operations */

	uint64 OSSwapAtomic64(std::atomic<uint64be>* mem, uint64 newValue)
	{
		uint64be _newValue = newValue;
		if (isAtomic64Aligned(mem))
		{
			uint64be previousValue = mem->exchange(_newValue);
			return previousValue;
		}

		std::lock_guard<std::mutex> lock(s_unalignedAtomic64Mutex);
		uint64be previousValue = loadUnalignedAtomic64(mem);
		storeUnalignedAtomic64(mem, _newValue);
		return previousValue;
	}

	uint64 OSSetAtomic64(std::atomic<uint64be>* mem, uint64 newValue)
	{
		return OSSwapAtomic64(mem, newValue);
	}

	uint64 OSGetAtomic64(std::atomic<uint64be>* mem)
	{
		if (isAtomic64Aligned(mem))
			return mem->load();

		std::lock_guard<std::mutex> lock(s_unalignedAtomic64Mutex);
		return loadUnalignedAtomic64(mem);
	}

	uint64 OSAddAtomic64(std::atomic<uint64be>* mem, uint64 adder)
	{
		if (isAtomic64Aligned(mem))
		{
			uint64be knownValue;
			while (true)
			{
				knownValue = mem->load();
				uint64be newValue = knownValue + adder;
				if (mem->compare_exchange_strong(knownValue, newValue))
					break;
			}
			return knownValue;
		}

		std::lock_guard<std::mutex> lock(s_unalignedAtomic64Mutex);
		uint64be knownValue = loadUnalignedAtomic64(mem);
		uint64be newValue = knownValue + adder;
		storeUnalignedAtomic64(mem, newValue);
		return knownValue;
	}

	uint64 OSAndAtomic64(std::atomic<uint64be>* mem, uint64 val)
	{
		if (isAtomic64Aligned(mem))
		{
			uint64be knownValue;
			while (true)
			{
				knownValue = mem->load();
				uint64be newValue = knownValue & val;
				if (mem->compare_exchange_strong(knownValue, newValue))
					break;
			}
			return knownValue;
		}

		std::lock_guard<std::mutex> lock(s_unalignedAtomic64Mutex);
		uint64be knownValue = loadUnalignedAtomic64(mem);
		uint64be newValue = knownValue & val;
		storeUnalignedAtomic64(mem, newValue);
		return knownValue;
	}

	uint64 OSOrAtomic64(std::atomic<uint64be>* mem, uint64 val)
	{
		if (isAtomic64Aligned(mem))
		{
			uint64be knownValue;
			while (true)
			{
				knownValue = mem->load();
				uint64be newValue = knownValue | val;
				if (mem->compare_exchange_strong(knownValue, newValue))
					break;
			}
			return knownValue;
		}

		std::lock_guard<std::mutex> lock(s_unalignedAtomic64Mutex);
		uint64be knownValue = loadUnalignedAtomic64(mem);
		uint64be newValue = knownValue | val;
		storeUnalignedAtomic64(mem, newValue);
		return knownValue;
	}

	bool OSCompareAndSwapAtomic64(std::atomic<uint64be>* mem, uint64 compareValue, uint64 swapValue)
	{
		uint64be _compareValue = compareValue;
		uint64be _swapValue = swapValue;
		if (isAtomic64Aligned(mem))
			return mem->compare_exchange_strong(_compareValue, _swapValue);

		std::lock_guard<std::mutex> lock(s_unalignedAtomic64Mutex);
		uint64be currentValue = loadUnalignedAtomic64(mem);
		if (currentValue != _compareValue)
			return false;
		storeUnalignedAtomic64(mem, _swapValue);
		return true;
	}

	bool OSCompareAndSwapAtomicEx64(std::atomic<uint64be>* mem, uint64 compareValue, uint64 swapValue, uint64be* previousValue)
	{
		uint64be _compareValue = compareValue;
		uint64be _swapValue = swapValue;
		if (isAtomic64Aligned(mem))
		{
			bool r = mem->compare_exchange_strong(_compareValue, _swapValue);
			std::memcpy(previousValue, &_compareValue, sizeof(_compareValue));
			return r;
		}

		std::lock_guard<std::mutex> lock(s_unalignedAtomic64Mutex);
		uint64be currentValue = loadUnalignedAtomic64(mem);
		bool r = currentValue == _compareValue;
		if (r)
			storeUnalignedAtomic64(mem, _swapValue);
		std::memcpy(previousValue, &currentValue, sizeof(currentValue));
		return r;
	}

	void InitializeAtomic()
	{
		// 32bit atomic operations
		cafeExportRegister("coreinit", OSSwapAtomic, LogType::Placeholder);
		cafeExportRegister("coreinit", OSCompareAndSwapAtomic, LogType::Placeholder);
		cafeExportRegister("coreinit", OSCompareAndSwapAtomicEx, LogType::Placeholder);
		cafeExportRegister("coreinit", OSAddAtomic, LogType::Placeholder);
		
		// 64bit atomic operations
		cafeExportRegister("coreinit", OSSetAtomic64, LogType::Placeholder);
		cafeExportRegister("coreinit", OSGetAtomic64, LogType::Placeholder);
		cafeExportRegister("coreinit", OSSwapAtomic64, LogType::Placeholder);
		cafeExportRegister("coreinit", OSAddAtomic64, LogType::Placeholder);
		cafeExportRegister("coreinit", OSAndAtomic64, LogType::Placeholder);
		cafeExportRegister("coreinit", OSOrAtomic64, LogType::Placeholder);
		cafeExportRegister("coreinit", OSCompareAndSwapAtomic64, LogType::Placeholder);
		cafeExportRegister("coreinit", OSCompareAndSwapAtomicEx64, LogType::Placeholder);
	}
}
