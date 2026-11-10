// Build 25936576 only. Called by the game's ISimulatable dispatch on its own thread.
typedef unsigned __int64 U64;
typedef long LONG;
extern "C" int _fltused = 0;
extern "C" long _InterlockedCompareExchange(long volatile*, long, long);
extern "C" long _InterlockedExchange(long volatile*, long);
#pragma intrinsic(_InterlockedCompareExchange)
#pragma intrinsic(_InterlockedExchange)
struct State {
    U64 magic = 0x315055524549444CULL;
    U64 base = 0, manager = 0, game = 0, global = 0, soldier = 0, design = 0;
    volatile LONG status = 0; // 0 idle, 1 pending, 2 running, 3 done, negative rejected
    LONG action = 0;
    float before = 0, after = 0;
};
extern "C" __declspec(dllexport) State SoldierState;
State SoldierState;
template<class T> T& f(void* o, U64 n) { return *reinterpret_cast<T*>(reinterpret_cast<U64>(o)+n); }
template<class T> T fn(U64 n) { return reinterpret_cast<T>(SoldierState.base+n); }
bool finiteRange(float x, float low, float high) { return x >= low && x <= high; }
extern "C" __declspec(dllexport) void SoldierSimulate(void* manager, void* game, void* global, void* method) {
    fn<void(*)(void*,void*,void*,void*)>(0x7CABB0)(manager,game,global,method);
    if (_InterlockedCompareExchange(&SoldierState.status,2,1)!=1) return;
    if (reinterpret_cast<U64>(manager)!=SoldierState.manager ||
        reinterpret_cast<U64>(game)!=SoldierState.game ||
        reinterpret_cast<U64>(global)!=SoldierState.global ||
        f<void*>(manager,0xA0)!=global || f<void*>(manager,0xA8)!=game ||
        f<void*>(game,0x48)!=global || f<void*>(global,0x20)!=manager) {
        _InterlockedExchange(&SoldierState.status,-1); return;
    }
    void* list=f<void*>(manager,0x10);
    if (!list) { _InterlockedExchange(&SoldierState.status,-2); return; }
    int count=f<int>(list,0x18); void* items=f<void*>(list,0x10);
    if (!items || count<0 || count>64 || f<U64>(items,0x18)<static_cast<U64>(count)) {
        _InterlockedExchange(&SoldierState.status,-2); return;
    }
    void* soldier=nullptr;
    for (int i=0;i<count;++i) {
        void* current=f<void*>(items,0x20+8ULL*i);
        if (reinterpret_cast<U64>(current)==SoldierState.soldier) soldier=current;
    }
    if (!soldier || f<unsigned char>(soldier,0x8C)) {
        _InterlockedExchange(&SoldierState.status,-3); return;
    }
    void* design=f<void*>(soldier,0xB8);
    if (!design || reinterpret_cast<U64>(design)!=SoldierState.design || f<void*>(design,0x10)!=soldier) {
        _InterlockedExchange(&SoldierState.status,-3); return;
    }
    if (SoldierState.action==1 && finiteRange(f<float>(design,0x30),0,999)) {
        SoldierState.before=f<float>(design,0x30);
        fn<void(*)(void*,void*)>(0x7BAE00)(soldier,nullptr);
        SoldierState.after=f<float>(design,0x30);
    } else if (SoldierState.action==2 && f<int>(design,0x38)>=0 && f<int>(design,0x38)<20 &&
               finiteRange(f<float>(design,0x3C),0,19.75f)) {
        SoldierState.before=f<float>(design,0x3C);
        fn<void(*)(void*,float,void*)>(0x7B5110)(design,0.25f,nullptr);
        SoldierState.after=f<float>(design,0x3C);
    } else if (SoldierState.action==3 && f<int>(design,0x34)>=0 && f<int>(design,0x34)<20 &&
               finiteRange(f<float>(soldier,0x88),0.25f,19.75f) &&
               f<void*>(soldier,0x50) && f<void*>(soldier,0x30)) {
        SoldierState.before=f<float>(soldier,0x88);
        fn<void(*)(void*,float,void*)>(0x7B9140)(soldier,0.25f,nullptr);
        SoldierState.after=f<float>(soldier,0x88);
    } else { _InterlockedExchange(&SoldierState.status,-4); return; }
    _InterlockedExchange(&SoldierState.status,3);
}
extern "C" int __stdcall DllMain(void*,unsigned long,void*) { return 1; }
