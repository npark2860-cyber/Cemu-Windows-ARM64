#include "qnn_context_cache.h"
#include <iostream>
#include <set>
using namespace cemu::npu;
namespace fs = std::filesystem;
int checks{};
void require(bool value,const char* message) {++checks;if(!value)throw std::runtime_error(message);}

int main(int argc,char** argv) {
    try {
        if(argc!=2) throw std::runtime_error("expected a scratch directory");
        const auto root=fs::absolute(argv[1])/"qnn-context-cache";
        fs::remove_all(root);fs::create_directories(root);
        const auto model=root/"model.onnx";
        { std::ofstream(model,std::ios::binary)<<"model bytes"; }
        const auto bytes=readFile(model);
        require(std::string(bytes.begin(),bytes.end())=="model bytes","model bytes read back");
        bool empty=false;{ std::ofstream(root/"empty.bin",std::ios::binary); }
        try {readFile(root/"empty.bin");} catch(const std::exception&) {empty=true;}
        require(empty,"empty context is never loaded");

        // The name changes with the model, every option and runtime identity.
        const auto name=[&](std::string_view model,std::string_view option,const fs::path& runtime) {
            ContextCacheKey key;key.add("v1").add(std::vector<char>(model.begin(),model.end())).add(option).addFile(runtime);
            return contextFileName(key).string();
        };
        const auto runtime=root/"QnnHtp.dll";
        const auto missing=name("m","fp16=1",runtime);
        { std::ofstream(runtime,std::ios::binary)<<"v1"; }
        const auto present=name("m","fp16=1",runtime);
        std::set<std::string> names{missing,present,name("n","fp16=1",runtime),name("m","fp16=0",runtime)};
        { std::ofstream(runtime,std::ios::binary)<<"v2 runtime"; }
        names.insert(name("m","fp16=1",runtime));
        require(names.size()==5,"model, option and runtime changes select new contexts");
        require(name("m","fp16=1",runtime)==name("m","fp16=1",runtime),"names are stable");
        ContextCacheKey ab,a_b;ab.add("ab");a_b.add("a").add("b");
        require(ab.hex()!=a_b.hex(),"fields are separated");
        require(present.rfind(std::string(ContextPrefix),0)==0 && present.size()==ContextPrefix.size()+16+9,"prefix, 16 hex digits, .ctx.onnx");

        // Writes land under the final name only when complete.
        const auto cache=root/"cache"/present;
        require(writeFileReplacing(cache,"context",7),"write creates the cache folder");
        require(!fs::exists(fs::path(cache)+=".partial"),"no partial file remains");
        const auto stored=readFile(cache);
        require(std::string(stored.begin(),stored.end())=="context","context bytes stored");
        require(writeFileReplacing(cache,"replaced",8),"rewrite replaces an existing context");
        const auto rewritten=readFile(cache);
        require(std::string(rewritten.begin(),rewritten.end())=="replaced","replacement stored");
        const auto marker=disabledMarker(cache);
        require(marker.filename().string()==present+".disabled","marker sits beside its context");
        require(writeFileReplacing(marker,"",0) && fs::is_regular_file(marker) && fs::file_size(marker)==0,"empty marker written");
        require(!writeFileReplacing(model/"child","x",1),"a file parent fails without throwing");

        // Cleanup keeps the current context and files that are not ours.
        const auto other=root/"cache"/(std::string(ContextPrefix)+"0000000000000000.ctx.onnx");
        { std::ofstream(other)<<"old"; std::ofstream(fs::path(other)+=".partial")<<"x"; std::ofstream(root/"cache"/"notes.txt")<<"keep"; }
        removeStaleContexts(root/"cache",cache.filename());
        require(fs::exists(cache) && fs::exists(root/"cache"/"notes.txt"),"current context and foreign files kept");
        require(!fs::exists(other) && !fs::exists(fs::path(other)+=".partial") && !fs::exists(marker),"other keys, partial writes and markers removed");
        removeStaleContexts(root/"missing",cache.filename());
        fs::remove_all(root);
        std::cout<<"{\"status\":\"QNN_CONTEXT_CACHE_TESTS_PASSED\",\"checks\":"<<checks<<",\"gpu_npu_executed\":false}\n";
        return 0;
    } catch(const std::exception& error) {std::cerr<<error.what()<<'\n';return 1;}
}
