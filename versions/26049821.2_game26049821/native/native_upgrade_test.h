// Shared layout for the native upgrade tests. Deliberately header-only and
// dependency-free: the test DLL is linked with /NODEFAULTLIB, so no CRT header
// and no dynamic initializer may be used.
typedef unsigned __int64 U64;

// Pointers into the test DLL's fake game graph, consumed by the Python tests.
struct NativeScene {
    U64 manager;
    U64 game;
    U64 glob;
    U64 soldier;
    U64 design;
};

// How often each stubbed game entry point was reached.
struct NativeCalls {
    int upgradesLeft;
    int tryFire;
    int original;
    int weapon;
    int squad;
};
