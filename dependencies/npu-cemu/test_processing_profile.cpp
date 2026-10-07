#include "processing_profile.h"
#include <iostream>
int main() {
    unsigned checks=0;
    auto check=[&](bool condition){++checks;if(!condition)throw std::runtime_error("profile contract failed");};
    for (uint32_t h : {1080u,720u}) {
        auto p=ProcessingProfile::fromHeight(h);
        check(p.width==(h==1080?1920u:1280u));
        check(p.height==h);
        check(p.inputBytes==p.pixels*6 && p.outputBytes==p.pixels*3);
        check(p.flowWidth==(h==1080?120u:80u) && p.flowHeight==(h==1080?68u:45u));
        check(p.flowBytes==size_t(p.flowWidth)*p.flowHeight*16);
        check(p.width%4==0 && p.pixels%4==0);
        // Last pixel's forward-flow index and clamped backward lookup fit.
        check(((p.height-1)/16)*p.flowWidth+(p.width-1)/16<p.flowBytes/16);
        check(((p.height/4+15)/16)*16>=p.height/4);
        check(((p.flowHeight+7)/8)*8>=p.flowHeight);
        // Packed input/output tails end exactly at the allocated boundary.
        check((p.pixels/2-1)*12+12==p.inputBytes);
        check((p.pixels/4-1)*12+12==p.outputBytes);
    }
    for (uint32_t h : {0u,540u,810u,1440u,0xffffffffu}) {
        bool rejected=false;
        try { (void)ProcessingProfile::fromHeight(h); } catch(const std::invalid_argument&) { rejected=true; }
        check(rejected);
    }
    std::cout<<"PROFILE_CPU_CONTRACT_PASSED checks="<<checks<<"\n";
}
