"""Checked, process-local expedition date adjustment for build 24931318."""
import ctypes
import hashlib
import struct
from functools import lru_cache
from pathlib import Path

import memory_scan as mem
import game_build

EXPECTED_HASH = "81ded46998713b8e79d877dca14e0d50791603e9a7d3a407b59365883942b6b8"
SETTINGS_RVA = 0x3D09078
SEEDING_RVA = 64516904
MAX_DAYS = 3650


@lru_cache(maxsize=4)
def _hash_file(path, size, modified):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verified_module(pid):
    snapshot = mem.kernel32.CreateToolhelp32Snapshot(
        mem.TH32CS_SNAPMODULE | mem.TH32CS_SNAPMODULE32, pid
    )
    if snapshot == ctypes.c_void_p(-1).value:
        mem.fail_win32("无法读取游戏模块；请使用与游戏相同的权限运行修改器")
    try:
        entry = mem.MODULEENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = mem.kernel32.Module32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            if entry.szModule.casefold() == "gameassembly.dll":
                path = Path(entry.szExePath)
                stat = path.stat()
                if _hash_file(str(path), stat.st_size, stat.st_mtime_ns) != EXPECTED_HASH:
                    raise RuntimeError("游戏版本不匹配，已停止远征任务操作")
                return int(entry.modBaseAddr)
            ok = mem.kernel32.Module32NextW(snapshot, ctypes.byref(entry))
    finally:
        mem.kernel32.CloseHandle(snapshot)
    raise RuntimeError("游戏模块尚未加载")


def resolve(read, base, settings_rva=SETTINGS_RVA, seeding_rva=SEEDING_RVA):
    def pointer(address):
        value = mem._read_u64(read, address)
        if value < 0x10000 or value >= 0x800000000000 or value & 7:
            raise RuntimeError("远征对象尚未就绪")
        return value

    klass = pointer(base + settings_rva)
    settings = pointer(pointer(klass + 0xB8))
    if pointer(settings) != klass:
        raise RuntimeError("游戏设置对象验证失败")
    seeding = pointer(settings + 0x108)
    if pointer(seeding) != pointer(base + seeding_rva):
        raise RuntimeError("远征种子对象验证失败")
    days = mem._read_i32(read, seeding + 0x18)
    if not 0 <= days <= MAX_DAYS:
        raise RuntimeError("虚拟日期超出支持范围，已停止操作")
    return {"settings": settings, "seeding": seeding,
            "address": seeding + 0x18, "days": days}


def change_checked(read, write, base, reset=False, **layout):
    before = resolve(read, base, **layout)
    target = 0 if reset else before["days"] + 1
    if target > MAX_DAYS:
        raise RuntimeError("已达到推进上限，请先恢复真实日期")
    if resolve(read, base, **layout) != before:
        raise RuntimeError("远征状态发生变化，请重试")
    if target != before["days"]:
        raw = struct.pack("<i", target)
        write(before["address"], raw)
        after = resolve(read, base, **layout)
        if after != dict(before, days=target):
            raise RuntimeError("远征写入后状态验证失败，请重新读取状态")
    return dict(before, days=target, previous_days=before["days"])


def operate(action="read"):
    if action not in ("read", "advance", "reset"):
        raise ValueError(action)
    pid = mem.find_process("After Inc. Revival.exe")
    profile = game_build.verified(pid)
    base = profile['base']
    layout = dict(settings_rva=profile['settings'], seeding_rva=profile['seeding'])
    handle = (mem.open_read_only if action == "read" else mem.open_read_write)(pid)
    try:
        read = lambda address, size: mem.read_memory(handle, address, size)
        if action == "read":
            result = resolve(read, base, **layout)
        else:
            result = change_checked(
                read, lambda address, raw: mem.write_memory(handle, address, raw),
                base, reset=action == "reset", **layout,
            )
        return dict(result, pid=pid, action=action)
    finally:
        mem.kernel32.CloseHandle(handle)
