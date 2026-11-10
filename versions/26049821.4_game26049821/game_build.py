"""Exact executable fingerprints; never infer compatibility from field names."""
import ctypes
import hashlib
from functools import lru_cache
from pathlib import Path

import memory_scan as mem

PROFILES = {
    '08719a4423f94c5563cec3d82bdc647ff44a09345bc2c9e88f222cdd5eae782a':
        dict(build='26049821', root=76270776, settings=76112208, seeding=76049200,
             teams=76461704),
    '81ded46998713b8e79d877dca14e0d50791603e9a7d3a407b59365883942b6b8':
        dict(build='24931318', root=0x3D13B90, settings=0x3D09078, seeding=64516904),
    '7f9284bff31468de4e07e11a9750339990f79b9837b733fcaf1200cabcc4d664':
        dict(build='25479909', root=0x3D1E9A8, settings=0x3D13AF8, seeding=0x3D920A0,
             teams=64247336),
    'c99f927e5590681f3a3790cb81dc6808fc519ac8d0e5486cdf1376578fc8f169':
        dict(build='25936576', root=76270776, settings=76112208, seeding=76049200,
             teams=76461704),
}

def modules(pid):
    snapshot = mem.kernel32.CreateToolhelp32Snapshot(0x18, pid)
    if snapshot == ctypes.c_void_p(-1).value:
        mem.fail_win32('无法读取游戏模块，请以管理员身份运行修改器')
    try:
        entry = mem.MODULEENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = mem.kernel32.Module32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            yield entry.szModule, int(entry.modBaseAddr), Path(entry.szExePath)
            ok = mem.kernel32.Module32NextW(snapshot, ctypes.byref(entry))
    finally:
        mem.kernel32.CloseHandle(snapshot)

@lru_cache(maxsize=8)
def file_hash(path, size, mtime):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def verified(pid):
    for name, base, path in modules(pid):
        if name.lower() == 'gameassembly.dll':
            st = path.stat()
            digest = file_hash(str(path), st.st_size, st.st_mtime_ns)
            if digest not in PROFILES:
                raise RuntimeError('游戏版本尚未适配，已停止操作')
            return dict(PROFILES[digest], base=base, path=path, sha256=digest)
    raise RuntimeError('游戏模块尚未加载')
