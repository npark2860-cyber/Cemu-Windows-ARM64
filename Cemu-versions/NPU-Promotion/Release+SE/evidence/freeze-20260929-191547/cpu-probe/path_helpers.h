#include <filesystem>
#include <string>
#include <string_view>
namespace fs=std::filesystem;
inline std::string _pathToUtf8(const fs::path& path)
{
    std::u8string strU8 = path.generic_u8string();
    std::string v((const char*)strU8.data(), strU8.size());
    return v;
}
inline fs::path _utf8ToPath(std::string_view input)
{
    std::basic_string_view<char8_t> v((char8_t*)input.data(), input.size());
    return fs::path(v);
}
