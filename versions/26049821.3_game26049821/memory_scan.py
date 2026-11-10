#!/usr/bin/env python3
"""Memory analysis helpers for After Inc: Revival.

Scanning, refinement, inspection, and structure location are read-only.  The
separate write-float32 command performs one checked and logged four-byte write.
No command changes files in the game installation directory.
"""

from __future__ import annotations
import session_log

import argparse
import bisect
import ctypes
from ctypes import wintypes
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import sys
import time


if os.name != "nt":
    raise SystemExit("This scanner only supports Windows.")


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_QUERY_INFORMATION = 0x0400
MEM_COMMIT = 0x1000
MEM_PRIVATE = 0x20000
PAGE_NOACCESS = 0x01
PAGE_GUARD = 0x100


# IL2CPP field layout for Steam build 24931318.  WorldSettlementSimulator
# inherits WorldSimBase, whose game/global back-references live at +0x10/+0x18.
# Those back-references let the GUI distinguish the active world from stale
# objects that can remain readable after loading a save or changing levels.
PRODUCTION_LAYOUT = {
    0x30: ("none", 0),
    0x38: ("manpower", 1),
    0x40: ("food_group", 2),
    0x48: ("forage", 3),
    0x50: ("grain", 4),
    0x58: ("fruit", 5),
    0x60: ("vegetable", 6),
    0x68: ("deer", 7),
    0x70: ("sheep", 8),
    0x78: ("cow", 9),
    0x80: ("fuel_group", 10),
    0x88: ("firewood", 11),
    0x90: ("coal", 12),
    0x98: ("water", 13),
    0xA0: ("construction_group", 14),
    0xA8: ("starter", 15),
    0xB0: ("wood", 16),
    0xB8: ("stone", 17),
    0xC0: ("clay", 18),
    0xC8: ("scrap", 19),
    0xD0: ("ore", 20),
    0xD8: ("metal", 21),
    0x1E8: ("morale_group", 57),
    0x200: ("authority", 69),
    0x208: ("housing_group", 32),
}
STANDALONE_PRODUCTIONS = {
    "manpower", "forage", "grain", "fruit", "vegetable", "deer",
    "sheep", "cow", "firewood", "coal", "water", "starter", "wood",
    "stone", "clay", "scrap", "ore", "metal", "authority",
}

# Steam build 24931318, verified from GameAssembly.dll SHA-256
# 81DED46998713B8E79D877DCA14E0D50791603E9A7D3A407B59365883942B6B8.
#
# SteamManager.get_Instance (RVA 0xA88E70) loads SteamManager__TypeInfo from
# this image-relative slot.  The remaining offsets are confirmed both by the
# IL2CPP metadata dump and the native instructions in get_Instance,
# GetLaunchHandler<object>, SteamLaunchHandler.set_scenarioLauncher, and
# GameController.SetUpGame.
GAME_ASSEMBLY_MODULE = "GameAssembly.dll"
STEAM_MANAGER_TYPE_INFO_RVA = 0x3D13B90
IL2CPP_CLASS_STATIC_FIELDS_OFFSET = 0xB8
STEAM_MANAGER_INSTANCE_STATIC_OFFSET = 0x8
STEAM_MANAGER_LAUNCH_OFFSET = 0x50
STEAM_LAUNCH_SCENARIO_LAUNCHER_OFFSET = 0x28


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.c_void_p),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", wintypes.HMODULE),
        ("szModule", wintypes.WCHAR * 256),
        ("szExePath", wintypes.WCHAR * 260),
    ]


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("PartitionId", wintypes.WORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]


kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32FirstW.restype = wintypes.BOOL
kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32NextW.restype = wintypes.BOOL
kernel32.Module32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]
kernel32.Module32FirstW.restype = wintypes.BOOL
kernel32.Module32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]
kernel32.Module32NextW.restype = wintypes.BOOL
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
kernel32.ReadProcessMemory.restype = wintypes.BOOL
kernel32.WriteProcessMemory.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
kernel32.WriteProcessMemory.restype = wintypes.BOOL
kernel32.VirtualQueryEx.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.POINTER(MEMORY_BASIC_INFORMATION),
    ctypes.c_size_t,
]
kernel32.VirtualQueryEx.restype = ctypes.c_size_t
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL


def fail_win32(message: str) -> "NoReturn":
    error = ctypes.get_last_error()
    raise OSError(error, f"{message} (Win32 error {error})")


def find_process(exe_name: str) -> int:
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == wintypes.HANDLE(-1).value:
        fail_win32("CreateToolhelp32Snapshot failed")
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.casefold() == exe_name.casefold():
                return int(entry.th32ProcessID)
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    raise RuntimeError(f"Process not found: {exe_name}")


def find_module_base(pid: int, module_name: str) -> int:
    snapshot = kernel32.CreateToolhelp32Snapshot(
        TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid
    )
    if snapshot == wintypes.HANDLE(-1).value:
        fail_win32(f"Module snapshot failed for PID {pid}")
    try:
        entry = MODULEENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = kernel32.Module32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            if entry.szModule.casefold() == module_name.casefold():
                return int(entry.modBaseAddr or 0)
            ok = kernel32.Module32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    raise RuntimeError(f"Module not found in PID {pid}: {module_name}")


def open_read_only(pid: int) -> int:
    handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not handle:
        fail_win32(f"OpenProcess failed for PID {pid}")
    return handle


def open_read_write(pid: int) -> int:
    access = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION
    handle = kernel32.OpenProcess(access, False, pid)
    if not handle:
        fail_win32(f"OpenProcess read/write failed for PID {pid}")
    return handle


def readable_private_regions(handle: int):
    address = 0
    maximum = 0x7FFFFFFFFFFF
    mbi = MEMORY_BASIC_INFORMATION()
    while address < maximum:
        result = kernel32.VirtualQueryEx(
            handle, ctypes.c_void_p(address), ctypes.byref(mbi), ctypes.sizeof(mbi)
        )
        if not result:
            break
        base = int(mbi.BaseAddress or 0)
        size = int(mbi.RegionSize)
        if (
            mbi.State == MEM_COMMIT
            and mbi.Type == MEM_PRIVATE
            and not (mbi.Protect & PAGE_GUARD)
            and not (mbi.Protect & PAGE_NOACCESS)
            and size > 0
        ):
            yield base, size
        next_address = base + size
        if next_address <= address:
            break
        address = next_address


def read_memory(handle: int, address: int, size: int) -> bytes:
    buffer = ctypes.create_string_buffer(size)
    read = ctypes.c_size_t()
    ok = kernel32.ReadProcessMemory(
        handle, ctypes.c_void_p(address), buffer, size, ctypes.byref(read)
    )
    if not ok and read.value == 0:
        return b""
    return buffer.raw[: read.value]


def private_region_lookup(regions: list[tuple[int, int]]):
    bases = [base for base, _ in regions]

    def contains(address: int, size: int = 1) -> bool:
        index = bisect.bisect_right(bases, address) - 1
        if index < 0:
            return False
        base, region_size = regions[index]
        return base <= address and address + size <= base + region_size

    return contains


def cached_reader(handle: int, contains):
    pages: dict[int, bytes] = {}

    def read(address: int, size: int) -> bytes:
        if not contains(address, size):
            return b""
        page = address & ~0xFFF
        offset = address - page
        if offset + size > 0x1000:
            return read_memory(handle, address, size)
        if page not in pages:
            pages[page] = read_memory(handle, page, 0x1000)
        return pages[page][offset : offset + size]

    return read


def _read_u64(read, address: int) -> int:
    raw = read(address, 8)
    if len(raw) != 8:
        raise RuntimeError(f"Unable to read pointer at 0x{address:016X}")
    return struct.unpack("<Q", raw)[0]


def _read_i32(read, address: int) -> int:
    raw = read(address, 4)
    if len(raw) != 4:
        raise RuntimeError(f"Unable to read int32 at 0x{address:016X}")
    return struct.unpack("<i", raw)[0]


def build_settlement_candidate(read, settlement_address: int) -> dict:
    """Validate and describe one active WorldSettlementSimulator.

    In addition to the production layout, require the complete active-world
    cycle recovered from metadata:

      settlement + 0x10 -> GameController
      settlement + 0x18 -> GlobalSimulation
      GameController + 0x48 -> GlobalSimulation
      GlobalSimulation + 0x50 -> settlement
      GlobalSimulation + 0xE8 -> GameController

    A destroyed GameController has a null Unity m_CachedPtr at +0x10.  This
    rejects stale but still readable save/scene objects before any write.
    """
    if settlement_address <= 0 or settlement_address & 7:
        raise RuntimeError("Settlement address is null or unaligned")

    settlement_class = _read_u64(read, settlement_address)
    game = _read_u64(read, settlement_address + 0x10)
    global_simulation = _read_u64(read, settlement_address + 0x18)
    if (
        not settlement_class
        or settlement_class & 7
        or not game
        or game & 7
        or not global_simulation
        or global_simulation & 7
    ):
        raise RuntimeError("Settlement world back-references are invalid")

    native_object = _read_u64(read, game + 0x10)
    game_global = _read_u64(read, game + 0x48)
    global_settlement = _read_u64(read, global_simulation + 0x50)
    global_game = _read_u64(read, global_simulation + 0xE8)
    raw_has_setup = read(game + 0x100, 1)
    if not native_object:
        raise RuntimeError("GameController has been destroyed")
    if game_global != global_simulation or global_settlement != settlement_address:
        raise RuntimeError("GameController points to a different active world")
    if global_game != game:
        raise RuntimeError("GlobalSimulation/GameController cycle is invalid")
    if raw_has_setup != b"\x01":
        raise RuntimeError("GameController is not fully set up")

    entry = {
        "settlement": f"0x{settlement_address:016X}",
        "settlement_class": f"0x{settlement_class:016X}",
        "game_controller": f"0x{game:016X}",
        "global_simulation": f"0x{global_simulation:016X}",
        "productions": {},
    }
    for field_offset, (name, resource_type) in PRODUCTION_LAYOUT.items():
        pointer = _read_u64(read, settlement_address + field_offset)
        if not pointer or pointer & 7:
            raise RuntimeError(f"Production pointer {name} is invalid")
        if _read_i32(read, pointer + 0x10) != resource_type:
            raise RuntimeError(f"Production type mismatch for {name}")
        item = {
            "object": f"0x{pointer:016X}",
            "resource_type": resource_type,
        }
        if name in STANDALONE_PRODUCTIONS:
            total_address = pointer + 0x280
            raw_total = read(total_address, 4)
            if len(raw_total) != 4:
                raise RuntimeError(f"Unable to read production total for {name}")
            item["total_address"] = f"0x{total_address:016X}"
            item["total"] = struct.unpack("<f", raw_total)[0]
        entry["productions"][name] = item
    return entry


def resolve_settlement_from_gameassembly(
    handle: int, pid: int, module_base: int | None = None,
    type_info_rva: int = STEAM_MANAGER_TYPE_INFO_RVA,
) -> dict:
    """Resolve the active settlement through a persistent native singleton.

    Native control flow for build 24931318 establishes this chain:

      GameAssembly + 0x3D13B90 -> SteamManager Il2CppClass
      Il2CppClass + 0xB8       -> static fields
      static fields + 0x8      -> SteamManager.s_instance
      SteamManager + 0x50      -> SteamLaunchHandler
      SteamLaunchHandler +0x28 -> current IScenarioLauncher (GameController)

    ``GameController.SetUpGame`` refreshes the last field after every scene
    load.  Following it requires only a handful of reads and avoids scanning
    private memory.  The resulting world is still passed through the complete
    bidirectional-cycle and production-layout validation before use.
    """
    if module_base is None:
        module_base = find_module_base(pid, GAME_ASSEMBLY_MODULE)
    if module_base <= 0 or module_base & 0xFFF:
        raise RuntimeError("GameAssembly module base is invalid")

    def process_pointer(address: int, label: str) -> int:
        raw = read_memory(handle, address, 8)
        if len(raw) != 8:
            raise RuntimeError(f"Unable to read {label}")
        value = struct.unpack("<Q", raw)[0]
        if not value or value & 7:
            raise RuntimeError(f"{label} is not ready")
        return value

    steam_manager_class = process_pointer(
        module_base + type_info_rva,
        "SteamManager type info",
    )
    static_fields = process_pointer(
        steam_manager_class + IL2CPP_CLASS_STATIC_FIELDS_OFFSET,
        "SteamManager static fields",
    )
    steam_manager = process_pointer(
        static_fields + STEAM_MANAGER_INSTANCE_STATIC_OFFSET,
        "SteamManager instance",
    )
    if process_pointer(steam_manager, "SteamManager object class") != steam_manager_class:
        raise RuntimeError("SteamManager singleton class validation failed")
    process_pointer(steam_manager + 0x10, "SteamManager native object")
    launch_handler = process_pointer(
        steam_manager + STEAM_MANAGER_LAUNCH_OFFSET,
        "Steam launch handler",
    )
    game = process_pointer(
        launch_handler + STEAM_LAUNCH_SCENARIO_LAUNCHER_OFFSET,
        "active scenario launcher",
    )

    def read(address: int, size: int) -> bytes:
        # This path starts at a verified module-relative static root rather
        # than an untrusted heap candidate.  Canonical-address and exact-length
        # checks plus the complete object-cycle validation below are sufficient,
        # and avoid enumerating the entire virtual address space every tick.
        if address < 0x10000 or size <= 0 or address + size > 0x800000000000:
            return b""
        return read_memory(handle, address, size)

    global_simulation = _read_u64(read, game + 0x48)
    settlement = _read_u64(read, global_simulation + 0x50)
    entry = build_settlement_candidate(read, settlement)
    if int(entry["game_controller"], 0) != game:
        raise RuntimeError("Stable root points to a different GameController")
    entry["gameassembly_base"] = f"0x{module_base:016X}"
    entry["binding_source"] = "steam_manager_scenario_launcher"
    return entry


def follow_active_settlement(read, candidate: dict) -> dict:
    """Resolve the current settlement through a candidate's GameController."""
    game_text = candidate.get("game_controller")
    if game_text:
        game = int(game_text, 0)
    else:
        old_settlement = int(candidate["settlement"], 0)
        game = _read_u64(read, old_settlement + 0x10)

    if not game or game & 7:
        raise RuntimeError("Cached GameController is invalid")
    if not _read_u64(read, game + 0x10):
        raise RuntimeError("Cached GameController has been destroyed")
    current_global = _read_u64(read, game + 0x48)
    if _read_u64(read, current_global + 0xE8) != game:
        raise RuntimeError("Current GlobalSimulation does not reference the cached game")
    current_settlement = _read_u64(read, current_global + 0x50)
    return build_settlement_candidate(read, current_settlement)


def refresh_settlement_candidate(handle: int, candidate: dict) -> dict:
    """Follow the cached GameController to the current active settlement.

    This is the fast rebind path used after a save reload or level change.  It
    normally reads only a few memory pages and therefore avoids a full heap
    scan when the GameController survives the transition.
    """
    regions = list(readable_private_regions(handle))
    if not regions:
        raise RuntimeError("No committed private memory regions found")
    contains = private_region_lookup(regions)
    return follow_active_settlement(cached_reader(handle, contains), candidate)


def locate_nearby_settlement_candidate(
    handle: int, candidate: dict, radius: int = 128 * 1024 * 1024
) -> dict | None:
    """Find a recreated active settlement near the previous managed object.

    Some scene changes recreate ``GameController`` itself, so the normal pointer
    chain cannot be followed.  IL2CPP instances retain the same class pointer
    for the life of the process.  Search only the nearby managed-heap window for
    that exact pointer, then apply the complete active-world and resource-layout
    validation before returning an address.  This is a bounded recovery path;
    callers still use the full locator when the new object is allocated farther
    away or the result is ambiguous.
    """
    if radius <= 0:
        raise ValueError("Nearby settlement scan radius must be positive")

    try:
        old_settlement = int(candidate["settlement"], 0)
    except (KeyError, TypeError, ValueError):
        return None

    class_text = candidate.get("settlement_class")
    try:
        settlement_class = int(class_text, 0) if class_text else 0
    except (TypeError, ValueError):
        settlement_class = 0
    if not settlement_class:
        raw_class = read_memory(handle, old_settlement, 8)
        if len(raw_class) == 8:
            settlement_class = struct.unpack("<Q", raw_class)[0]
    if not settlement_class or settlement_class & 7:
        return None

    regions = list(readable_private_regions(handle))
    if not regions:
        return None
    contains = private_region_lookup(regions)
    read = cached_reader(handle, contains)
    signature = struct.pack("<Q", settlement_class)
    lower = max(0, old_settlement - radius)
    upper = old_settlement + radius
    chunk_size = 4 * 1024 * 1024
    matches: dict[int, dict] = {}

    for region_base, region_size in regions:
        start = max(region_base, lower)
        end = min(region_base + region_size, upper)
        if start >= end:
            continue
        start = (start + 7) & ~7
        cursor = start
        while cursor + 8 <= end:
            primary_size = min(chunk_size, end - cursor)
            request_size = min(primary_size + 7, end - cursor)
            data = read_memory(handle, cursor, request_size)
            if len(data) < 8:
                cursor += primary_size
                continue
            search_from = 0
            while True:
                offset = data.find(signature, search_from)
                if offset < 0 or offset >= primary_size:
                    break
                object_address = cursor + offset
                search_from = offset + 1
                if object_address & 7:
                    continue
                try:
                    entry = build_settlement_candidate(read, object_address)
                except (KeyError, RuntimeError, ValueError, struct.error):
                    continue
                matches[object_address] = entry
                if len(matches) > 1:
                    return None
            cursor += primary_size

    if len(matches) == 1:
        return next(iter(matches.values()))
    return None


def read_il2cpp_reference_list(read, list_address: int, limit: int = 64) -> list[int]:
    """Read a validated IL2CPP ``List<T>`` whose items are object references."""
    if not list_address or list_address & 7:
        raise RuntimeError("Managed list address is null or unaligned")
    items = _read_u64(read, list_address + 0x10)
    size = _read_i32(read, list_address + 0x18)
    if size < 0 or size > limit:
        raise RuntimeError(f"Managed list size {size} is outside the safe limit {limit}")
    if size == 0:
        return []
    if not items or items & 7:
        raise RuntimeError("Managed list items array is invalid")
    capacity = _read_u64(read, items + 0x18)
    if capacity < size or capacity > max(limit, 256):
        raise RuntimeError(
            f"Managed list capacity {capacity} is inconsistent with size {size}"
        )
    result = []
    for index in range(size):
        value = _read_u64(read, items + 0x20 + index * 8)
        if not value or value & 7:
            raise RuntimeError(f"Managed list item {index} is null or unaligned")
        result.append(value)
    return result


def read_player_soldiers(read, candidate: dict) -> list[dict]:
    """Return validated player MovingSoldier objects from the active world.

    Enemy units do not live in ``GlobalSimulation.soldiers``.  The manager and
    every soldier/design back-reference are checked before an address is
    returned, so the writer cannot accidentally walk an unrelated managed list.
    """
    settlement = int(candidate["settlement"], 0)
    game = int(candidate.get("game_controller", "0"), 0)
    global_simulation = int(candidate.get("global_simulation", "0"), 0)
    if not game:
        game = _read_u64(read, settlement + 0x10)
    if not global_simulation:
        global_simulation = _read_u64(read, settlement + 0x18)

    manager = _read_u64(read, global_simulation + 0x20)
    if not manager or manager & 7:
        raise RuntimeError("MovingSoldierManager pointer is invalid")
    if _read_u64(read, manager + 0xA0) != global_simulation:
        raise RuntimeError("MovingSoldierManager global back-reference is invalid")
    if _read_u64(read, manager + 0xA8) != game:
        raise RuntimeError("MovingSoldierManager game back-reference is invalid")

    soldier_list = _read_u64(read, manager + 0x10)
    soldiers = read_il2cpp_reference_list(read, soldier_list)
    result = []
    class_pointer = 0
    for index, soldier in enumerate(soldiers):
        current_class = _read_u64(read, soldier)
        if not current_class:
            raise RuntimeError(f"Soldier {index} has no IL2CPP class pointer")
        if class_pointer and current_class != class_pointer:
            raise RuntimeError("Player soldier list contains mixed object classes")
        class_pointer = current_class

        design = _read_u64(read, soldier + 0xB8)
        if not design or _read_u64(read, design + 0x10) != soldier:
            raise RuntimeError(f"Soldier {index} design back-reference is invalid")
        state = _read_i32(read, soldier + 0xAC)
        if not 0 <= state <= 10:
            raise RuntimeError(f"Soldier {index} state {state} is invalid")
        dead_raw = read(soldier + 0x8C, 1)
        if dead_raw not in (b"\x00", b"\x01"):
            raise RuntimeError(f"Soldier {index} death flag is invalid")

        current_zone = _read_u64(read, soldier + 0x30)
        from_zone = _read_u64(read, soldier + 0x38)
        raw_turns = read(soldier + 0x78, 4)
        raw_max_turns = read(soldier + 0x84, 4)
        if len(raw_turns) != 4 or len(raw_max_turns) != 4:
            raise RuntimeError(f"Unable to read movement timers for soldier {index}")
        turns = struct.unpack("<f", raw_turns)[0]
        max_turns = struct.unpack("<f", raw_max_turns)[0]
        if not math.isfinite(turns) or not math.isfinite(max_turns):
            raise RuntimeError(f"Soldier {index} movement timers are not finite")

        is_moving = bool(current_zone and from_zone and current_zone != from_zone)
        timer_is_integral = abs(turns - round(turns)) <= 0.0001
        max_timer_is_integral = abs(max_turns - round(max_turns)) <= 0.0001
        can_accelerate = (
            dead_raw == b"\x00"
            and is_moving
            and turns > 1.0
            and max_turns >= turns
            and timer_is_integral
            and max_timer_is_integral
        )
        result.append(
            {
                "index": index,
                "object": soldier,
                "state": state,
                "is_dead": dead_raw == b"\x01",
                "current_zone": current_zone,
                "from_zone": from_zone,
                "design": design,
                "turns_address": soldier + 0x78,
                "turns": turns,
                "max_turns": max_turns,
                "can_accelerate": can_accelerate,
            }
        )
    return result


@session_log.audit
def write_memory(handle: int, address: int, data: bytes) -> None:
    buffer = ctypes.create_string_buffer(data, len(data))
    written = ctypes.c_size_t()
    ok = kernel32.WriteProcessMemory(
        handle, ctypes.c_void_p(address), buffer, len(data), ctypes.byref(written)
    )
    if not ok or written.value != len(data):
        fail_win32(
            f"WriteProcessMemory failed at 0x{address:016X}; "
            f"wrote {written.value} of {len(data)} bytes"
        )


def parse_named_values(items: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Expected NAME=INTEGER, got: {item}")
        name, raw_value = item.split("=", 1)
        name = name.strip()
        if not name:
            raise ValueError(f"Empty name in: {item}")
        result[name] = int(raw_value.strip(), 0)
    return result


def patterns_for(values: dict[str, int]):
    patterns: dict[bytes, dict] = {}
    for label, value in values.items():
        if value == 0:
            continue
        encodings = {
            "int32": struct.pack("<i", value),
            "float32": struct.pack("<f", float(value)),
        }
        for kind, pattern in encodings.items():
            item = patterns.setdefault(
                pattern,
                {"kind": kind, "value": value, "labels": [], "addresses": []},
            )
            item["labels"].append(label)
    return patterns


def append_matches(data: bytes, absolute_base: int, primary_size: int, patterns: dict):
    for pattern, item in patterns.items():
        start = 0
        while True:
            found = data.find(pattern, start)
            if found < 0:
                break
            if found >= primary_size:
                break
            address = absolute_base + found
            if address % 4 == 0:
                item["addresses"].append(address)
            start = found + 1


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_addresses(path: Path, addresses: list[int]) -> None:
    with path.open("wb") as stream:
        for address in addresses:
            stream.write(struct.pack("<Q", address))


def read_addresses(path: Path):
    with path.open("rb") as stream:
        while True:
            raw = stream.read(8)
            if not raw:
                return
            if len(raw) != 8:
                raise ValueError(f"Truncated address file: {path}")
            yield struct.unpack("<Q", raw)[0]


def initial_scan(args: argparse.Namespace) -> int:
    values = parse_named_values(args.value)
    skipped_zero = [name for name, value in values.items() if value == 0]
    patterns = patterns_for(values)
    if not patterns:
        raise ValueError("No non-zero values to scan.")

    pid = find_process(args.process)
    handle = open_read_only(pid)
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    scanned = 0
    failures = 0
    chunk_size = 4 * 1024 * 1024

    print(f"Attached read-only: {args.process} (PID {pid})")
    print("Scanning committed private memory for aligned int32/float32 values...")
    try:
        for region_base, region_size in readable_private_regions(handle):
            offset = 0
            while offset < region_size:
                primary_size = min(chunk_size, region_size - offset)
                request_size = min(primary_size + 3, region_size - offset)
                data = read_memory(handle, region_base + offset, request_size)
                if data:
                    append_matches(data, region_base + offset, primary_size, patterns)
                    scanned += min(primary_size, len(data))
                else:
                    failures += 1
                offset += primary_size
            if scanned and scanned % (256 * 1024 * 1024) < region_size:
                print(f"  scanned {scanned / (1024**2):.0f} MiB")
    finally:
        kernel32.CloseHandle(handle)

    manifest = {
        "format": 1,
        "mode": "initial-read-only",
        "created_local": time.strftime("%Y-%m-%d %H:%M:%S"),
        "process": args.process,
        "pid": pid,
        "scanned_bytes": scanned,
        "read_failures": failures,
        "elapsed_seconds": round(time.time() - started, 3),
        "values": values,
        "skipped_zero_values": skipped_zero,
        "game_build": args.game_build,
        "game_assembly": str(Path(args.game_assembly).resolve()) if args.game_assembly else None,
        "game_assembly_sha256": sha256_file(Path(args.game_assembly)) if args.game_assembly else None,
        "candidate_sets": [],
    }

    for index, item in enumerate(patterns.values(), start=1):
        filename = f"candidates_{index:02d}_{item['kind']}_{item['value']}.bin"
        write_addresses(output_dir / filename, item["addresses"])
        manifest["candidate_sets"].append(
            {
                "labels": item["labels"],
                "kind": item["kind"],
                "value": item["value"],
                "count": len(item["addresses"]),
                "file": filename,
            }
        )
        print(
            f"  {','.join(item['labels'])}: {item['kind']}={item['value']} -> "
            f"{len(item['addresses']):,} candidates"
        )

    manifest_path = output_dir / "snapshot.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if skipped_zero:
        print(
            "Skipped zero-value initial scan (too many false matches): "
            + ", ".join(skipped_zero)
        )
    print(f"Snapshot saved: {manifest_path}")
    print(f"Read-only scan complete in {manifest['elapsed_seconds']:.1f}s")
    return 0


def candidate_set_for_label(manifest: dict, label: str):
    sets = [item for item in manifest["candidate_sets"] if label in item["labels"]]
    if not sets:
        raise KeyError(f"No initial candidates for label: {label}")
    return sets


def refine_exact(args: argparse.Namespace) -> int:
    snapshot_path = Path(args.snapshot).resolve()
    snapshot_dir = snapshot_path.parent
    manifest = json.loads(snapshot_path.read_text(encoding="utf-8"))
    updates = parse_named_values(args.value)
    pid = find_process(manifest["process"])
    handle = open_read_only(pid)
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    result_sets = []

    print(f"Attached read-only: {manifest['process']} (PID {pid})")
    try:
        for label, new_value in updates.items():
            for source in candidate_set_for_label(manifest, label):
                kind = source["kind"]
                expected = (
                    struct.pack("<i", new_value)
                    if kind == "int32"
                    else struct.pack("<f", float(new_value))
                )
                matches: list[int] = []
                current_page = None
                page_data = b""
                for address in read_addresses(snapshot_dir / source["file"]):
                    page = address & ~0xFFF
                    if page != current_page:
                        current_page = page
                        page_data = read_memory(handle, page, 0x1000)
                    offset = address - page
                    if page_data[offset : offset + 4] == expected:
                        matches.append(address)
                filename = f"{label}_{kind}_{new_value}.bin"
                write_addresses(output_dir / filename, matches)
                result_sets.append(
                    {
                        "labels": [label],
                        "kind": kind,
                        "value": new_value,
                        "count": len(matches),
                        "file": filename,
                        "source_file": source["file"],
                    }
                )
                print(
                    f"  {label}: {kind} {source['count']:,} -> {len(matches):,} candidates "
                    f"(new value {new_value})"
                )
    finally:
        kernel32.CloseHandle(handle)

    result = {
        "format": 1,
        "mode": "refine-exact-read-only",
        "created_local": time.strftime("%Y-%m-%d %H:%M:%S"),
        "process": manifest["process"],
        "pid": pid,
        "parent_snapshot": str(snapshot_path),
        "values": updates,
        "candidate_sets": result_sets,
        "game_build": manifest.get("game_build"),
        "game_assembly_sha256": manifest.get("game_assembly_sha256"),
    }
    result_path = output_dir / "snapshot.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Refined snapshot saved: {result_path}")
    return 0


def inspect_nearby(args: argparse.Namespace) -> int:
    pid = find_process(args.process)
    handle = open_read_only(pid)
    address = int(args.address, 0)
    before = max(0, args.before)
    after = max(4, args.after)
    start = address - before
    size = before + after
    try:
        data = read_memory(handle, start, size)
    finally:
        kernel32.CloseHandle(handle)
    if len(data) != size:
        raise RuntimeError(f"Could only read {len(data)} of {size} requested bytes")

    print(f"Read-only inspection: {args.process} (PID {pid})")
    print(f"Target address: 0x{address:016X}")
    print("offset  address             hex       int32        float32")
    first = (before % 4)
    for offset in range(first, len(data) - 3, 4):
        absolute = start + offset
        raw = data[offset : offset + 4]
        relative = absolute - address
        integer = struct.unpack("<i", raw)[0]
        floating = struct.unpack("<f", raw)[0]
        marker = " <==" if relative == 0 else ""
        print(
            f"{relative:+6d}  0x{absolute:016X}  {raw.hex(' ')}  "
            f"{integer:11d}  {floating:13.6g}{marker}"
        )
    return 0


def locate_settlement(args: argparse.Namespace) -> int:
    """Locate WorldSettlementSimulator by its IL2CPP field layout.

    The layout comes from build 24931318 metadata.  We first look for a heap
    object containing plausible production-object pointers at the documented
    offsets, then verify each target object's ResourceType field at +0x10.
    """
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("locate-settlement requires numpy") from exc

    pid = find_process(args.process)
    handle = open_read_only(pid)
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    chunk_size = 4 * 1024 * 1024

    try:
        regions = list(readable_private_regions(handle))
        if not regions:
            raise RuntimeError("No committed private memory regions found")
        contains = private_region_lookup(regions)
        cached_read = cached_reader(handle, contains)
        low = min(base for base, _ in regions)
        high = max(base + size for base, size in regions)
        candidates: list[dict] = []
        scanned = 0
        max_field = max(PRODUCTION_LAYOUT) + 8

        print(f"Attached read-only: {args.process} (PID {pid})")
        print("Locating WorldSettlementSimulator from IL2CPP production layout...")

        for region_base, region_size in regions:
            offset = 0
            while offset < region_size:
                primary_size = min(chunk_size, region_size - offset)
                request_size = min(primary_size + max_field, region_size - offset)
                data = read_memory(handle, region_base + offset, request_size)
                if len(data) >= max_field:
                    usable = len(data) - (len(data) % 8)
                    words = np.frombuffer(data[:usable], dtype="<u8")
                    count = min(primary_size // 8, len(words) - (max_field // 8))
                    if count > 0:
                        # A fast vector pass: seven documented fields must all
                        # look like aligned heap pointers before exact checks.
                        mask = np.ones(count, dtype=bool)
                        for field_offset in (0x30, 0x38, 0x40, 0x80, 0x98, 0xB0, 0x200):
                            values = words[field_offset // 8 : field_offset // 8 + count]
                            mask &= (values >= low) & (values < high) & ((values & 7) == 0)

                        for word_index in np.flatnonzero(mask):
                            object_address = region_base + offset + int(word_index) * 8
                            try:
                                entry = build_settlement_candidate(cached_read, object_address)
                            except (KeyError, RuntimeError, ValueError, struct.error):
                                continue
                            candidates.append(entry)
                scanned += min(primary_size, len(data))
                offset += primary_size
            if scanned and scanned % (256 * 1024 * 1024) < region_size:
                print(f"  scanned {scanned / (1024**2):.0f} MiB")
    finally:
        kernel32.CloseHandle(handle)

    result = {
        "format": 1,
        "mode": "locate-world-settlement-read-only",
        "created_local": time.strftime("%Y-%m-%d %H:%M:%S"),
        "process": args.process,
        "pid": pid,
        "metadata_layout": "build_24931318_metadata_v31",
        "scanned_bytes": scanned,
        "elapsed_seconds": round(time.time() - started, 3),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Found {len(candidates)} structurally verified settlement candidate(s)")
    for candidate in candidates:
        print(f"  settlement {candidate['settlement']}")
        for name in ("manpower", "water", "wood", "authority"):
            item = candidate["productions"][name]
            print(
                f"    {name:9s} total={item.get('total')!r} "
                f"at {item.get('total_address', 'n/a')}"
            )
    print(f"Structure report saved: {output_path}")
    return 0


def write_float32_checked(args: argparse.Namespace) -> int:
    if args.confirm != "WRITE-ONE-FLOAT32":
        raise ValueError("Refusing write: exact --confirm WRITE-ONE-FLOAT32 is required")
    pid = find_process(args.process)
    handle = open_read_write(pid)
    address = int(args.address, 0)
    expected_raw = struct.pack("<f", float(args.expected))
    new_raw = struct.pack("<f", float(args.value))
    try:
        before = read_memory(handle, address, 4)
        if before != expected_raw:
            actual = struct.unpack("<f", before)[0] if len(before) == 4 else None
            raise RuntimeError(
                f"Expected {args.expected} at 0x{address:016X}, found {actual!r}; no write performed"
            )
        write_memory(handle, address, new_raw)
        after = read_memory(handle, address, 4)
        if after != new_raw:
            raise RuntimeError("Write verification failed")
    finally:
        kernel32.CloseHandle(handle)

    record = {
        "format": 1,
        "mode": "checked-float32-write",
        "created_local": time.strftime("%Y-%m-%d %H:%M:%S"),
        "process": args.process,
        "pid": pid,
        "address": f"0x{address:016X}",
        "before": float(args.expected),
        "after": float(args.value),
        "before_hex": expected_raw.hex(),
        "after_hex": new_raw.hex(),
        "restore_command": (
            f"write-float32 --process \"{args.process}\" --address 0x{address:016X} "
            f"--expected {args.value} --value {args.expected} --confirm WRITE-ONE-FLOAT32"
        ),
    }
    if args.log:
        log_path = Path(args.log).resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Write record saved: {log_path}")
    print(
        f"Checked float32 write complete: 0x{address:016X} "
        f"{args.expected} -> {args.value} (PID {pid})"
    )
    return 0


def write_int32_checked(args: argparse.Namespace) -> int:
    if args.confirm != "WRITE-ONE-INT32":
        raise ValueError("Refusing write: exact --confirm WRITE-ONE-INT32 is required")
    pid = find_process(args.process)
    handle = open_read_write(pid)
    address = int(args.address, 0)
    expected_raw = struct.pack("<i", int(args.expected))
    new_raw = struct.pack("<i", int(args.value))
    try:
        before = read_memory(handle, address, 4)
        if before != expected_raw:
            actual = struct.unpack("<i", before)[0] if len(before) == 4 else None
            raise RuntimeError(
                f"Expected {args.expected} at 0x{address:016X}, found {actual!r}; no write performed"
            )
        write_memory(handle, address, new_raw)
        after = read_memory(handle, address, 4)
        if after != new_raw:
            raise RuntimeError("Write verification failed")
    finally:
        kernel32.CloseHandle(handle)

    record = {
        "format": 1,
        "mode": "checked-int32-write",
        "created_local": time.strftime("%Y-%m-%d %H:%M:%S"),
        "process": args.process,
        "pid": pid,
        "address": f"0x{address:016X}",
        "before": int(args.expected),
        "after": int(args.value),
        "before_hex": expected_raw.hex(),
        "after_hex": new_raw.hex(),
        "restore_command": (
            f"write-int32 --process \"{args.process}\" --address 0x{address:016X} "
            f"--expected {args.value} --value {args.expected} --confirm WRITE-ONE-INT32"
        ),
    }
    if args.log:
        log_path = Path(args.log).resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Write record saved: {log_path}")
    print(
        f"Checked int32 write complete: 0x{address:016X} "
        f"{args.expected} -> {args.value} (PID {pid})"
    )
    return 0


def parse_float32_write_specs(items: list[str]) -> list[dict]:
    result = []
    seen_addresses = set()
    for item in items:
        if "=" not in item:
            raise ValueError(f"Expected NAME=ADDRESS,EXPECTED,VALUE, got: {item}")
        name, raw_values = item.split("=", 1)
        parts = [part.strip() for part in raw_values.split(",")]
        if len(parts) != 3:
            raise ValueError(f"Expected NAME=ADDRESS,EXPECTED,VALUE, got: {item}")
        address = int(parts[0], 0)
        if address in seen_addresses:
            raise ValueError(f"Duplicate address in batch: 0x{address:016X}")
        seen_addresses.add(address)
        result.append(
            {
                "name": name.strip(),
                "address": address,
                "expected": float(parts[1]),
                "value": float(parts[2]),
            }
        )
    if not result:
        raise ValueError("At least one --write item is required")
    return result


def write_float32_batch_checked(args: argparse.Namespace) -> int:
    if args.confirm != "WRITE-FLOAT32-BATCH":
        raise ValueError("Refusing batch: exact --confirm WRITE-FLOAT32-BATCH is required")
    items = parse_float32_write_specs(args.write)
    pid = find_process(args.process)
    handle = open_read_write(pid)
    written: list[dict] = []
    try:
        # Transaction-style preflight: no write occurs until every old value
        # matches its caller-supplied expected float32 bytes.
        for item in items:
            expected_raw = struct.pack("<f", item["expected"])
            before = read_memory(handle, item["address"], 4)
            if before != expected_raw:
                actual = struct.unpack("<f", before)[0] if len(before) == 4 else None
                raise RuntimeError(
                    f"Preflight failed for {item['name']} at 0x{item['address']:016X}: "
                    f"expected {item['expected']}, found {actual!r}; no writes performed"
                )
            item["expected_raw"] = expected_raw
            item["value_raw"] = struct.pack("<f", item["value"])

        try:
            for item in items:
                write_memory(handle, item["address"], item["value_raw"])
                after = read_memory(handle, item["address"], 4)
                if after != item["value_raw"]:
                    raise RuntimeError(f"Verification failed for {item['name']}")
                written.append(item)
        except Exception:
            for item in reversed(written):
                write_memory(handle, item["address"], item["expected_raw"])
            raise
    finally:
        kernel32.CloseHandle(handle)

    record_items = []
    for item in items:
        record_items.append(
            {
                "name": item["name"],
                "address": f"0x{item['address']:016X}",
                "before": struct.unpack("<f", item["expected_raw"])[0],
                "after": struct.unpack("<f", item["value_raw"])[0],
                "before_hex": item["expected_raw"].hex(),
                "after_hex": item["value_raw"].hex(),
            }
        )
    record = {
        "format": 1,
        "mode": "checked-float32-batch-write",
        "created_local": time.strftime("%Y-%m-%d %H:%M:%S"),
        "process": args.process,
        "pid": pid,
        "items": record_items,
        "rollback_on_write_failure": True,
    }
    if args.log:
        log_path = Path(args.log).resolve()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Batch write record saved: {log_path}")
    print(f"Checked float32 batch complete: {len(items)} values (PID {pid})")
    for item in record_items:
        print(f"  {item['name']}: {item['before']} -> {item['after']} at {item['address']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    initial = subparsers.add_parser("initial", help="Scan current exact non-zero values")
    initial.add_argument("--process", default="After Inc. Revival.exe")
    initial.add_argument("--value", action="append", required=True, help="NAME=INTEGER")
    initial.add_argument("--output", required=True)
    initial.add_argument("--game-build", default=None)
    initial.add_argument("--game-assembly", default=None)
    initial.set_defaults(func=initial_scan)

    refine = subparsers.add_parser("refine", help="Filter a snapshot by new exact values")
    refine.add_argument("--snapshot", required=True)
    refine.add_argument("--value", action="append", required=True, help="NAME=NEW_INTEGER")
    refine.add_argument("--output", required=True)
    refine.set_defaults(func=refine_exact)

    inspect = subparsers.add_parser("inspect", help="Read and display values near one address")
    inspect.add_argument("--process", default="After Inc. Revival.exe")
    inspect.add_argument("--address", required=True, help="Decimal or 0x-prefixed address")
    inspect.add_argument("--before", type=int, default=64)
    inspect.add_argument("--after", type=int, default=128)
    inspect.set_defaults(func=inspect_nearby)

    locate = subparsers.add_parser(
        "locate-settlement",
        help="Read-only search for WorldSettlementSimulator using IL2CPP field layout",
    )
    locate.add_argument("--process", default="After Inc. Revival.exe")
    locate.add_argument("--output", required=True)
    locate.set_defaults(func=locate_settlement)

    write_float = subparsers.add_parser(
        "write-float32", help="Checked, logged write of exactly one float32 value"
    )
    write_float.add_argument("--process", default="After Inc. Revival.exe")
    write_float.add_argument("--address", required=True)
    write_float.add_argument("--expected", type=float, required=True)
    write_float.add_argument("--value", type=float, required=True)
    write_float.add_argument("--confirm", required=True)
    write_float.add_argument("--log", default=None)
    write_float.set_defaults(func=write_float32_checked)

    write_int = subparsers.add_parser(
        "write-int32", help="Checked, logged write of exactly one int32 value"
    )
    write_int.add_argument("--process", default="After Inc. Revival.exe")
    write_int.add_argument("--address", required=True)
    write_int.add_argument("--expected", type=int, required=True)
    write_int.add_argument("--value", type=int, required=True)
    write_int.add_argument("--confirm", required=True)
    write_int.add_argument("--log", default=None)
    write_int.set_defaults(func=write_int32_checked)

    write_batch = subparsers.add_parser(
        "write-float32-batch",
        help="Preflight, write, verify, and log a small float32 batch",
    )
    write_batch.add_argument("--process", default="After Inc. Revival.exe")
    write_batch.add_argument(
        "--write",
        action="append",
        required=True,
        help="NAME=ADDRESS,EXPECTED,VALUE",
    )
    write_batch.add_argument("--confirm", required=True)
    write_batch.add_argument("--log", default=None)
    write_batch.set_defaults(func=write_float32_batch_checked)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
