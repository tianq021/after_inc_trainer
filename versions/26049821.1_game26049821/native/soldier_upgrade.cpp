// Build 26049821 only. Called by the game's ISimulatable dispatch on its own thread.
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
// Diagnostics shared with the trainer so a stuck request can be explained instead
// of guessed at. hookCalls only grows when the game really enters SoldierSimulate.
struct Diag {
    LONG hookCalls;      // entries into SoldierSimulate
    LONG runsStarted;    // entries that won the pending -> running exchange
    LONG identityFails;  // entries rejected by the object identity checks
    LONG stage;          // last step reached inside requestUpgrade
    LONG eventFound;     // 1 when the SoldierUpgrade event was located
    LONG engagedBefore;  // pending-cluster count seen before firing
    LONG hasUpgradesLeft;// -1 unknown, 0 no reward left, 1 available
    LONG optHasValue;    // raw Optional<EngagedCluster>.hasValue
    LONG optIsObject;    // raw Optional<EngagedCluster>.isObject
    LONG createdCount;   // events inside the created cluster, -1 unknown
    LONG lastStatus;     // status written by the last completed run
    LONG reserved;
    U64 lastManager = 0, lastGame = 0, lastGlobal = 0;
    U64 optValue = 0, optObjectValue = 0;
};
extern "C" __declspec(dllexport) State SoldierState;
extern "C" __declspec(dllexport) Diag SoldierDiag = {};
State SoldierState;
template<class T> T& f(void* o, U64 n) { return *reinterpret_cast<T*>(reinterpret_cast<U64>(o)+n); }
#ifdef TRAINER_TEST
void* testResolve(U64 n);
template<class T> T fn(U64 n) { return reinterpret_cast<T>(testResolve(n)); }
#else
template<class T> T fn(U64 n) { return reinterpret_cast<T>(SoldierState.base+n); }
#endif
bool finiteRange(float x, float low, float high) { return x >= low && x <= high; }
bool listData(void* list, void*& items, int& count) {
    if (!list) return false;
    count=f<int>(list,0x18); items=f<void*>(list,0x10);
    return items && count>=0 && count<=4096 && f<U64>(items,0x18)>=static_cast<U64>(count);
}
bool upgradeIdent(void* text) {
    // "SoldierUpgrade" is 14 characters, not 13. Derive the length from the
    // literal so a miscount cannot silently stop this from ever matching.
    const wchar_t expected[]=L"SoldierUpgrade";
    const int length=static_cast<int>(sizeof(expected)/sizeof(wchar_t))-1;
    if (!text || f<int>(text,0x10)!=length) return false;
    for (int i=0;i<length;++i) if (f<wchar_t>(text,0x14+2ULL*i)!=expected[i]) return false;
    return true;
}
// Stage codes written to Diag.stage. The trainer turns them into plain language.
enum Stage {
    STAGE_EVENTS = 1, STAGE_BLOCKED = 2, STAGE_LIST = 3, STAGE_NOTFOUND = 4,
    STAGE_AMBIGUOUS = 5, STAGE_ENGAGED = 6, STAGE_PENDING = 7, STAGE_EMPTY = 8,
    STAGE_COUNT = 9, STAGE_OK = 10, STAGE_LEFT = 11
};
// Types are checked structurally (owner pointers that the dump confirms) rather
// than against hardcoded class slots, so a stale slot address cannot reject a
// perfectly good object graph.
//
// The original event creates the clickable upgrade token and lets the player
// choose a bonus Tech. It is a settlement-wide choice, NOT soldier.exp += 1.
LONG requestUpgrade(void* game, void* zone) {
    Diag& d = SoldierDiag;
    d.eventFound = 0; d.engagedBefore = -1; d.hasUpgradesLeft = -1;
    d.optHasValue = -1; d.optIsObject = -1; d.createdCount = -1;
    d.optValue = 0; d.optObjectValue = 0;
    void* events=f<void*>(game,0xC0);
    if (!events || f<void*>(events,0x20)!=game || !zone) { d.stage=STAGE_EVENTS; return -7; }
    if (f<unsigned char>(events,0xD8)) { d.stage=STAGE_BLOCKED; return -7; }
    void* items=nullptr; int count=0;
    if (!listData(f<void*>(events,0x68),items,count)) { d.stage=STAGE_LIST; return -7; }
    void* upgrade=nullptr;
    for (int i=0;i<count;++i) {
        void* entry=f<void*>(items,0x20+8ULL*i);
        if (!entry || f<void*>(entry,0x70)!=events) { d.stage=STAGE_LIST; return -7; }
        if (upgradeIdent(f<void*>(entry,0x10))) {
            if (upgrade) { d.stage=STAGE_AMBIGUOUS; return -7; }
            upgrade=entry;
        }
    }
    if (!upgrade) { d.stage=STAGE_NOTFOUND; return -7; }
    d.eventFound=1;
    if (!listData(f<void*>(events,0x78),items,count)) { d.stage=STAGE_ENGAGED; return -7; }
    d.engagedBefore=count;
    for (int i=0;i<count;++i) {
        void* holder=f<void*>(items,0x20+8ULL*i);
        if (!holder) continue;
        void* cluster=f<void*>(holder,0x18);
        if (!cluster || f<void*>(cluster,0x28)!=events) continue;
        // Even a hidden or closing token must finish before another is created.
        if (f<void*>(cluster,0x18)==upgrade) { d.stage=STAGE_PENDING; return -6; }
    }
    // The original event counts its own options with exactly this predicate and
    // returns before creating any token when the count is zero, so a settlement
    // that has taken every non-repeatable soldier Tech genuinely has no icon to
    // show. Refusing here is the honest answer, and Diag.stage records it.
    d.hasUpgradesLeft = fn<bool(*)(void*,void*)>(0x622C80)(events,nullptr) ? 1 : 0;
    if (!d.hasUpgradesLeft) { d.stage=STAGE_LEFT; return -5; }
    // Optional<EngagedCluster> is a 24-byte value returned through an sret pointer:
    // value, hasValue, isObject, then objectValue. The fourth argument matches the
    // game's own TryFire call, which permits an event whose checks did not pass.
    struct OptionalResult { void* value; unsigned char flags[8]; void* objectValue; } result={};
    fn<void*(*)(void*,void*,void*,void*,void*,bool,void*)>(0x5D9DA0)(
        &result,events,upgrade,zone,nullptr,true,nullptr);
    d.optHasValue=result.flags[0]?1:0;
    d.optIsObject=result.flags[1]?1:0;
    d.optValue=reinterpret_cast<U64>(result.value);
    d.optObjectValue=reinterpret_cast<U64>(result.objectValue);
    void* created=nullptr;
    void* candidates[2]={result.value,result.objectValue};
    for (int i=0;i<2 && !created;++i) {
        void* candidate=candidates[i];
        if (candidate && f<void*>(candidate,0x28)==events && f<void*>(candidate,0x18)==upgrade)
            created=candidate;
    }
    if (!created) { d.stage=STAGE_EMPTY; return d.hasUpgradesLeft ? -8 : -5; }
    void* child=nullptr; int childCount=0;
    if (!listData(f<void*>(created,0x20),child,childCount) || childCount!=1) {
        d.stage=STAGE_COUNT; return d.hasUpgradesLeft ? -8 : -5;
    }
    d.createdCount=childCount;
    d.stage=STAGE_OK;
    return 3;
}
extern "C" __declspec(dllexport) void SoldierSimulate(void* manager, void* game, void* global, void* method) {
    ++SoldierDiag.hookCalls;
    fn<void(*)(void*,void*,void*,void*)>(0x7CAC10)(manager,game,global,method);
    if (_InterlockedCompareExchange(&SoldierState.status,2,1)!=1) return;
    ++SoldierDiag.runsStarted;
    SoldierDiag.lastManager=reinterpret_cast<U64>(manager);
    SoldierDiag.lastGame=reinterpret_cast<U64>(game);
    SoldierDiag.lastGlobal=reinterpret_cast<U64>(global);
    if (reinterpret_cast<U64>(manager)!=SoldierState.manager ||
        reinterpret_cast<U64>(game)!=SoldierState.game ||
        reinterpret_cast<U64>(global)!=SoldierState.global ||
        f<void*>(manager,0xA0)!=global || f<void*>(manager,0xA8)!=game ||
        f<void*>(game,0x48)!=global || f<void*>(global,0x20)!=manager) {
        ++SoldierDiag.identityFails;
        _InterlockedExchange(&SoldierState.status,-1); SoldierDiag.lastStatus=-1; return;
    }
    void* list=f<void*>(manager,0x10);
    if (!list) { _InterlockedExchange(&SoldierState.status,-2); SoldierDiag.lastStatus=-2; return; }
    int count=f<int>(list,0x18); void* items=f<void*>(list,0x10);
    if (!items || count<0 || count>64 || f<U64>(items,0x18)<static_cast<U64>(count)) {
        _InterlockedExchange(&SoldierState.status,-2); SoldierDiag.lastStatus=-2; return;
    }
    void* soldier=nullptr;
    for (int i=0;i<count;++i) {
        void* current=f<void*>(items,0x20+8ULL*i);
        if (reinterpret_cast<U64>(current)==SoldierState.soldier) soldier=current;
    }
    if (!soldier || f<unsigned char>(soldier,0x8C)) {
        _InterlockedExchange(&SoldierState.status,-3); SoldierDiag.lastStatus=-3; return;
    }
    void* design=f<void*>(soldier,0xB8);
    if (!design || reinterpret_cast<U64>(design)!=SoldierState.design || f<void*>(design,0x10)!=soldier) {
        _InterlockedExchange(&SoldierState.status,-3); SoldierDiag.lastStatus=-3; return;
    }
    if (SoldierState.action==1) {
        LONG result=-9;
        __try { result=requestUpgrade(game,f<void*>(soldier,0x30)); }
        __except(1) { result=-9; }
        _InterlockedExchange(&SoldierState.status,result); SoldierDiag.lastStatus=result; return;
    } else if (SoldierState.action==2 && f<int>(design,0x38)>=0 && f<int>(design,0x38)<20 &&
               finiteRange(f<float>(design,0x3C),0,19.75f)) {
        SoldierState.before=f<float>(design,0x3C);
        fn<void(*)(void*,float,void*)>(0x7B5170)(design,0.25f,nullptr);
        SoldierState.after=f<float>(design,0x3C);
    } else if (SoldierState.action==3 && f<int>(design,0x34)>=0 && f<int>(design,0x34)<20 &&
               finiteRange(f<float>(soldier,0x88),0.25f,19.75f) &&
               f<void*>(soldier,0x50) && f<void*>(soldier,0x30)) {
        SoldierState.before=f<float>(soldier,0x88);
        fn<void(*)(void*,float,void*)>(0x7B91A0)(soldier,0.25f,nullptr);
        SoldierState.after=f<float>(soldier,0x88);
    } else { _InterlockedExchange(&SoldierState.status,-4); SoldierDiag.lastStatus=-4; return; }
    _InterlockedExchange(&SoldierState.status,3); SoldierDiag.lastStatus=3;
}
extern "C" int __stdcall DllMain(void*,unsigned long,void*) { return 1; }
