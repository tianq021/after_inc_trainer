// Native unit tests for the build-26049821 soldier upgrade path.
//
// Compiled together with soldier_upgrade.cpp under /DTRAINER_TEST, so every game
// address in that file is resolved through testResolve() below instead of through
// the game module base. That lets the upgrade request, its guards and its
// rejection codes be exercised without the game running.
//
// The DLL builds a fake Il2Cpp-style object graph in a static arena. Python calls
// PrepareScene(scenario), reads TestScene, seeds SoldierState, then calls the real
// exported SoldierSimulate. Nothing here runs a CRT initializer, so every global
// is either a plain zero-initialized .bss object or assigned inside PrepareScene.
//
// This file must not define DllMain: soldier_upgrade.cpp already exports one.
#include "native_upgrade_test.h"

namespace {

unsigned char arena[8192];

template <class T> T& af(void* o, U64 n) {
    return *reinterpret_cast<T*>(reinterpret_cast<U64>(o) + n);
}
void* at(U64 off) { return arena + off; }

void setList(void* list, void* items, int count) {
    af<void*>(list, 0x10) = items;
    af<int>(list, 0x18) = count;
}
// Il2Cpp array header: klass/monitor/bounds/max_length(0x18), data at 0x20.
void setArray(void* array, int length, U64 first) {
    af<U64>(array, 0x18) = static_cast<U64>(length);
    af<U64>(array, 0x20) = first;
}

bool upgradesLeft;
bool reportFlags;
bool reportedWrongValue;
int reportedCount;
int upgradesLeftCalls, tryFireCalls, originalCalls;
int weaponCalls, squadCalls;

void fakeOriginal(void*, void*, void*, void*) { ++originalCalls; }

// Stands in for GameEvents.HasSoldierUpgradesLeft().
bool fakeUpgradesLeft(void*, void*) {
    ++upgradesLeftCalls;
    return upgradesLeft;
}

void* fakeTryFire(void* result, void*, void*, void*, void*, bool, void*) {
    ++tryFireCalls;
    af<void*>(result, 0x00) = reportedWrongValue ? at(0x0700) : at(0x1000);
    af<unsigned char>(result, 0x08) = reportFlags ? 1 : 0;
    af<int>(at(0x1100), 0x18) = reportedCount;
    return result;
}

void fakeWeapon(void* design, float delta, void*) {
    ++weaponCalls;
    af<float>(design, 0x3C) += delta;
}

void fakeSquad(void* soldier, float delta, void*) {
    ++squadCalls;
    af<float>(soldier, 0x88) += delta;
}

}  // namespace

extern "C" __declspec(dllexport) NativeScene TestScene = {};
extern "C" __declspec(dllexport) NativeCalls TestCalls = {};

// soldier_upgrade.cpp declares `void* testResolve(U64)`. Every slot it asks for is
// a code address, so each case hands back the callable address itself.
void* testResolve(U64 slot) {
    switch (slot) {
        case 0x622C80: return reinterpret_cast<void*>(&fakeUpgradesLeft);
        case 0x5D9DA0: return reinterpret_cast<void*>(&fakeTryFire);
        case 0x7CAC10: return reinterpret_cast<void*>(&fakeOriginal);
        case 0x7B5170: return reinterpret_cast<void*>(&fakeWeapon);
        case 0x7B91A0: return reinterpret_cast<void*>(&fakeSquad);
        default: return nullptr;
    }
}

extern "C" __declspec(dllexport) void PrepareScene(int scenario) {
    // Volatile stores keep this from turning into a memset call, which would not
    // be available in a /NODEFAULTLIB build.
    volatile U64* wipe = reinterpret_cast<volatile U64*>(arena);
    for (unsigned int i = 0; i < sizeof(arena) / sizeof(U64); ++i) wipe[i] = 0;

    upgradesLeft = true;
    reportFlags = true;
    reportedWrongValue = false;
    reportedCount = 1;
    upgradesLeftCalls = tryFireCalls = originalCalls = 0;
    weaponCalls = squadCalls = 0;

    void* manager = at(0x0000);
    void* game = at(0x0100);
    void* glob = at(0x0200);
    void* soldier = at(0x0300);
    void* design = at(0x0400);
    void* zone = at(0x0500);
    void* events = at(0x0600);
    void* entry = at(0x0700);
    void* ident = at(0x0800);
    void* holder = at(0x0D00);
    void* cluster = at(0x1000);

    // Event graph: List<GameEvent> at +0x68, List<EngagedEvent> at +0x78.
    af<void*>(events, 0x20) = game;
    af<unsigned char>(events, 0xD8) = 0;
    setList(at(0x0900), at(0x0A00), 1);
    setArray(at(0x0A00), 1, reinterpret_cast<U64>(entry));
    af<void*>(events, 0x68) = at(0x0900);
    setList(at(0x0B00), at(0x0C00), 0);
    setArray(at(0x0C00), 1, reinterpret_cast<U64>(holder));
    af<void*>(events, 0x78) = at(0x0B00);

    // The single entry carrying the SoldierUpgrade identity. The real ident is
    // 14 characters long; scenario 3 hands over 13 to pin that regression down.
    const wchar_t name[] = L"SoldierUpgrade";
    const int nameLength = static_cast<int>(sizeof(name) / sizeof(wchar_t)) - 1;
    af<void*>(entry, 0x10) = ident;
    af<int>(entry, 0x30) = 7;
    af<void*>(entry, 0x70) = events;
    af<int>(ident, 0x10) = nameLength;
    for (int i = 0; i < nameLength; ++i) af<wchar_t>(ident, 0x14 + 2ULL * i) = name[i];

    // Pending-upgrade holder plus the cluster it would create.
    af<void*>(holder, 0x18) = cluster;
    af<void*>(cluster, 0x18) = entry;
    af<void*>(cluster, 0x28) = events;
    setList(at(0x1100), at(0x1200), 1);
    setArray(at(0x1200), 1, reinterpret_cast<U64>(at(0x1300)));
    af<void*>(cluster, 0x20) = at(0x1100);

    // Soldier graph.
    af<void*>(manager, 0xA0) = glob;
    af<void*>(manager, 0xA8) = game;
    setList(at(0x1400), at(0x1500), 1);
    setArray(at(0x1500), 1, reinterpret_cast<U64>(soldier));
    af<void*>(manager, 0x10) = at(0x1400);
    af<void*>(game, 0x48) = glob;
    af<void*>(game, 0xC0) = events;
    af<void*>(glob, 0x20) = manager;
    af<unsigned char>(soldier, 0x8C) = 0;
    af<void*>(soldier, 0xB8) = design;
    af<void*>(soldier, 0x30) = zone;
    af<void*>(soldier, 0x50) = manager;
    af<float>(soldier, 0x88) = 1.0f;
    af<void*>(design, 0x10) = soldier;
    af<float>(design, 0x30) = 1.0f;
    af<int>(design, 0x34) = 0;
    af<int>(design, 0x38) = 0;
    af<float>(design, 0x3C) = 1.0f;

    switch (scenario) {
        case 1: af<void*>(events, 0x20) = manager; break;      // events owner wrong
        case 2: af<unsigned char>(events, 0xD8) = 1; break;    // events are blocked
        case 3: af<int>(ident, 0x10) = 13; break;              // old bug: 13 instead of 14
        case 4: setList(at(0x0B00), at(0x0C00), 1); break;     // already pending
        case 5: upgradesLeft = false; reportedWrongValue = true; break;  // nothing left, nothing created
        case 6: reportFlags = false; break;                    // hasValue not set
        case 7: reportedCount = 2; break;                      // unexpected token count
        case 8: af<void*>(manager, 0xA0) = game; break;        // identity check fails
        case 9: af<void*>(manager, 0x10) = nullptr; break;     // no soldier list
        case 10: af<unsigned char>(soldier, 0x8C) = 1; break;  // soldier is gone
        case 11: af<void*>(design, 0x10) = manager; break;     // design backref wrong
        case 12: af<int>(design, 0x38) = 20; break;            // weapon count at cap
        case 13: af<void*>(entry, 0x70) = game; break;         // entry owner wrong
        case 14: af<void*>(soldier, 0x30) = nullptr; break;    // no zone to place in
        case 15: af<float>(soldier, 0x88) = 20.0f; break;      // squad size out of range
        case 16: reportedWrongValue = true; break;             // created cluster wrong
        case 17: upgradesLeft = false; break;                  // exhausted, but fires
        default: break;
    }

    TestScene.manager = reinterpret_cast<U64>(manager);
    TestScene.game = reinterpret_cast<U64>(game);
    TestScene.glob = reinterpret_cast<U64>(glob);
    TestScene.soldier = reinterpret_cast<U64>(soldier);
    TestScene.design = reinterpret_cast<U64>(design);
    TestCalls.upgradesLeft = 0;
    TestCalls.tryFire = 0;
    TestCalls.original = 0;
    TestCalls.weapon = 0;
    TestCalls.squad = 0;
}

extern "C" __declspec(dllexport) void HarvestCalls(void) {
    TestCalls.upgradesLeft = upgradesLeftCalls;
    TestCalls.tryFire = tryFireCalls;
    TestCalls.original = originalCalls;
    TestCalls.weapon = weaponCalls;
    TestCalls.squad = squadCalls;
}
