// Session-only random expeditions, exact Steam builds 25479909 / 25936576.
// The existing campaign delegate invokes this on the game's own thread.
typedef unsigned __int64 uint64_t;
typedef unsigned __int64 uintptr_t;
typedef unsigned __int64 size_t;
typedef long LONG;
extern "C" long _InterlockedIncrement(long volatile*);
extern "C" long _InterlockedDecrement(long volatile*);
#pragma intrinsic(_InterlockedIncrement)
#pragma intrinsic(_InterlockedDecrement)

struct State {
    uint64_t magic = 0x31534B5341544641ULL;
    uint64_t base = 0;
    volatile LONG count = 0;
    volatile LONG generated = 0;
    volatile LONG calls = 0;
    volatile LONG error = 0;
    int seeds[10] = {};
    uint64_t lastList = 0; // diagnostic only; never dereferenced later by this DLL
    volatile LONG activity = 0;
    LONG build = 0; // selected only after the trainer verifies GameAssembly SHA-256
};
extern "C" __declspec(dllexport) State TaskState;
State TaskState;

template<class T> T field(void* object, size_t offset) {
    return *reinterpret_cast<T*>(reinterpret_cast<uintptr_t>(object) + offset);
}
uintptr_t mapped(uintptr_t rva) {
    if (TaskState.build == 26049821) {
        switch (rva) {
        case 0x69FD60: return 0x766DB0;
        case 0x6CB4A0: return 0x7924F0;
        case 0x3C5A60: return 0x4708C0;
        case 0x3D78540: return 0x4868B20;
        case 0x8CB6B0: return 0x985060; // .ctor(this, MethodInfo), NOT the copy constructor
        case 0x8E8200: return 0x9A1BB0;
        case 0x8CAF50: return 0x984900; // Add(Generator), NOT Add(IEnumerable<Generator>)
        case 0x5FEA40: return 0x6B0A50;
        case 0x2E60: return 0x2F80;
        case 0x3D98FE0: return 0x48F2390;
        }
    }
    if (TaskState.build == 25936576) {
        switch (rva) {
        case 0x69FD60: return 0x766D50;
        case 0x6CB4A0: return 0x792490;
        case 0x3C5A60: return 0x4708C0;
        case 0x3D78540: return 0x4868B20;
        case 0x8CB6B0: return 0x985000;
        case 0x8E8200: return 0x9A1B50;
        case 0x8CAF50: return 0x9848A0;
        case 0x5FEA40: return 0x6B0970;
        case 0x2E60: return 0x2F80;
        case 0x3D98FE0: return 0x48F2390;
        }
    }
    return rva;
}
#ifdef TRAINER_ADDRESS_TEST
// Exercise the compiled production mapping against dumped method signatures.
extern "C" __declspec(dllexport) uintptr_t TestMapped(LONG build, uintptr_t rva) {
    TaskState.build = build;
    return mapped(rva);
}
#endif
template<class T> T fn(uintptr_t rva) {
    rva = mapped(rva);
    return reinterpret_cast<T>(TaskState.base + rva);
}
void* slot(uintptr_t rva) { return *fn<void**>(rva); }

extern "C" __declspec(dllexport) void* TaskLevels(void* loader, void* method) {
    // Enter before reading configuration, so the trainer can safely refuse an
    // update while a callback (including the original generator) is in flight.
    _InterlockedIncrement(&TaskState.activity);
    if (TaskState.build != 25479909 && TaskState.build != 25936576 && TaskState.build != 26049821) {
        TaskState.error = 4;
        _InterlockedDecrement(&TaskState.activity);
        return nullptr;
    }
    auto list = fn<void*(*)(void*, void*)>(0x69FD60)(loader, method);
    if (!list || field<int>(list, 0x18) == 0) {
        _InterlockedDecrement(&TaskState.activity);
        return list;
    }
    const LONG count = TaskState.count;
    if (count < 0 || count > 5 || !loader) {
        _InterlockedDecrement(&TaskState.activity);
        return list;
    }
    TaskState.generated = 0;
    TaskState.error = 0;
    _InterlockedIncrement(&TaskState.calls);
    for (LONG i = 0; i < count; ++i) {
        void* level = fn<void*(*)(void*, int, void*)>(0x6CB4A0)(loader, TaskState.seeds[i], nullptr);
        if (!level) { TaskState.error = 1; break; }
        void* chain = fn<void*(*)(void*)>(0x3C5A60)(slot(0x3D78540));
        if (!chain) { TaskState.error = 2; break; }
        fn<void(*)(void*, void*)>(0x8CB6B0)(chain, nullptr);
        void* objective = fn<void*(*)(void*, void*, void*)>(0x8E8200)(loader, level, nullptr);
        if (!objective) { TaskState.error = 3; break; }
        fn<void(*)(void*, void*, void*)>(0x8CAF50)(chain, objective, nullptr);
        fn<void*(*)(void*, void*, void*)>(0x5FEA40)(level, chain, nullptr);
        fn<void(*)(void*, void*, void*)>(0x2E60)(list, level, slot(0x3D98FE0));
        ++TaskState.generated;
    }
    TaskState.lastList = reinterpret_cast<uint64_t>(list);
    _InterlockedDecrement(&TaskState.activity);
    return list;
}

extern "C" int __stdcall DllMain(void*, unsigned long, void*) {
    return 1;
}
