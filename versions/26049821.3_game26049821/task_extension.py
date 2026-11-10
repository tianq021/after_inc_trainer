"""Checked session-only task extension. No game installation files are edited."""
import ctypes
import session_log
from ctypes import wintypes as w
import json
import hashlib
import os
from pathlib import Path
import secrets
import shutil
import struct
import sys
import threading
import time
from contextlib import contextmanager

import game_build
import memory_scan as mem

MAX_TASKS = 5
DLL_NAME = 'AfterIncTaskExtension.dll'
MAGIC = 0x31534B5341544641
STATE = struct.Struct('<QQiiii10iQii')
CAMPAIGN_RVA = 0x3D6DD30
ORIGINAL_RVA = 0x69FD60
POINT_INSTRUCTION = 0x635A8F
TASK_PROFILES = {
    '26049821': dict(campaign=0x48F4420, original=0x766DB0,
                     point=0x6E036F, invoke=0x3170),
    '25479909': dict(campaign=CAMPAIGN_RVA, original=ORIGINAL_RVA,
                     point=POINT_INSTRUCTION, invoke=0x3050),
    '25936576': dict(campaign=0x48F4420, original=0x766D50,
                     point=0x6E030F, invoke=0x3170),
}
LOCK = threading.Lock()
k = mem.kernel32
k.VirtualAllocEx.argtypes = [w.HANDLE, ctypes.c_void_p, ctypes.c_size_t, w.DWORD, w.DWORD]
k.VirtualAllocEx.restype = ctypes.c_void_p
k.VirtualFreeEx.argtypes = [w.HANDLE, ctypes.c_void_p, ctypes.c_size_t, w.DWORD]
k.VirtualFreeEx.restype = w.BOOL
k.VirtualProtectEx.argtypes = [w.HANDLE, ctypes.c_void_p, ctypes.c_size_t, w.DWORD, ctypes.POINTER(w.DWORD)]
k.VirtualProtectEx.restype = w.BOOL
k.CreateRemoteThread.argtypes = [w.HANDLE, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p, w.DWORD, ctypes.c_void_p]
k.CreateRemoteThread.restype = w.HANDLE
k.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
k.WaitForSingleObject.restype = w.DWORD
k.FlushInstructionCache.argtypes = [w.HANDLE, ctypes.c_void_p, ctypes.c_size_t]
k.FlushInstructionCache.restype = w.BOOL
nt = ctypes.WinDLL('ntdll')
for name in ('NtSuspendProcess', 'NtResumeProcess'):
    getattr(nt, name).argtypes = [w.HANDLE]
    getattr(nt, name).restype = ctypes.c_long

def exports(path):
    """Read PE32+ exports without loading an untrusted DLL in the trainer."""
    data = Path(path).read_bytes()
    pe = struct.unpack_from('<I', data, 0x3C)[0]
    if data[pe:pe+4] != b'PE\0\0':
        raise ValueError('Invalid PE')
    sections, opt_size = struct.unpack_from('<H', data, pe+6)[0], struct.unpack_from('<H', data, pe+20)[0]
    optional = pe+24
    if struct.unpack_from('<H', data, optional)[0] != 0x20B:
        raise ValueError('Expected x64 DLL')
    table = optional+opt_size
    def offset(rva):
        for i in range(sections):
            vs, va, raw_size, raw = struct.unpack_from('<IIII', data, table+i*40+8)
            if va <= rva < va+max(vs, raw_size):
                return raw+rva-va
        raise ValueError('RVA outside sections')
    export_rva, export_size = struct.unpack_from('<II', data, optional+112)
    e = offset(export_rva)
    count, funcs, names, ordinals = struct.unpack_from('<IIII', data, e+24)
    result = {}
    for i in range(count):
        nrva = struct.unpack_from('<I', data, offset(names)+4*i)[0]
        no = offset(nrva)
        name = data[no:data.index(b'\0', no)].decode('ascii')
        ordinal = struct.unpack_from('<H', data, offset(ordinals)+2*i)[0]
        rva = struct.unpack_from('<I', data, offset(funcs)+4*ordinal)[0]
        if export_rva <= rva < export_rva+export_size:
            continue  # forwarded exports are not executable addresses
        result[name] = rva
    return result

def parse_count(value):
    text = str(value).strip()
    if not text.isascii() or not text.isdecimal() or not 1 <= int(text) <= MAX_TASKS:
        raise ValueError(f'请输入 1–{MAX_TASKS} 的整数')
    return int(text)

def plan_seeds(existing, count):
    count = parse_count(count)
    if len(existing)+count > MAX_TASKS:
        raise ValueError(f'本次最多保留 {MAX_TASKS} 个添加任务，请先清除再添加')
    result = list(existing)
    while len(result) < len(existing)+count:
        seed = 20000+secrets.randbelow(40000)
        if seed not in result:
            result.append(seed)
    return result

def decode_state(raw):
    magic, base, count, generated, calls, error, *tail = STATE.unpack(raw)
    if magic != MAGIC or not 0 <= count <= MAX_TASKS:
        raise RuntimeError('任务扩展状态校验失败')
    return dict(base=base, count=count, generated=generated, calls=calls,
                error=error, seeds=tail[:count], last_list=tail[-3], activity=tail[-2], build=tail[-1])

def pointer(handle, address):
    value = mem._read_u64(lambda a, n: mem.read_memory(handle, a, n), address)
    if value < 0x10000 or value >= 0x800000000000 or value & 7:
        raise RuntimeError('地图任务对象尚未就绪，请进入世界地图')
    return value

def delegate_address(handle, base, layout=None):
    layout = layout or TASK_PROFILES['25479909']
    klass = pointer(handle, base+layout['campaign'])
    campaign = pointer(handle, pointer(handle, klass+0xB8))
    delegate = pointer(handle, campaign+0x80)
    if pointer(handle, delegate+0x18) != base+layout['invoke']:
        raise RuntimeError('任务生成入口校验失败')
    return delegate+0x10

def extension_module(pid, dll_name=DLL_NAME):
    return next(((base, path) for name, base, path in game_build.modules(pid)
                 if name.lower() == dll_name.lower()), None)

def dll_path():
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    return root/'native'/DLL_NAME

def ensure_loaded(handle, pid, dll_name=DLL_NAME, source=None):
    found = extension_module(pid, dll_name)
    source = source or dll_path()
    if found:
        if found[1].read_bytes() != source.read_bytes():
            raise RuntimeError('游戏中仍加载着另一版任务扩展，请重启游戏后再试')
        return found
    # Resolve LoadLibraryW from the target's own kernel32 export table.
    remote_kernel = next((b, p) for n, b, p in game_build.modules(pid) if n.lower() == 'kernel32.dll')
    load_address = remote_kernel[0]+exports(remote_kernel[1])['LoadLibraryW']
    payload = source.read_bytes()
    cache = Path(os.environ.get('LOCALAPPDATA', Path.home()))/'AfterIncTrainer/native'/hashlib.sha256(payload).hexdigest()
    cache.mkdir(parents=True, exist_ok=True)
    cached_dll = cache/dll_name
    if not cached_dll.exists():
        cached_dll.write_bytes(payload)
    if cached_dll.read_bytes() != payload:
        raise RuntimeError('任务扩展缓存校验失败')
    raw = (str(cached_dll.resolve())+'\0').encode('utf-16-le')
    address = k.VirtualAllocEx(handle, None, len(raw), 0x3000, 4)
    if not address:
        mem.fail_win32('无法为任务扩展分配内存')
    thread = None
    finished = False
    try:
        mem.write_memory(handle, address, raw)
        thread = k.CreateRemoteThread(handle, None, 0, load_address, address, 0, None)
        if not thread:
            mem.fail_win32('无法加载任务扩展')
        if k.WaitForSingleObject(thread, 10000) != 0:
            raise RuntimeError('加载任务扩展超时；请稍后读取状态，不要连续点击')
        finished = True
        found = extension_module(pid, dll_name)
        if not found:
            raise RuntimeError('任务扩展未能加载')
        return found
    finally:
        if thread:
            k.CloseHandle(thread)
        if finished or thread is None:
            k.VirtualFreeEx(handle, address, 0, 0x8000)

@contextmanager
def suspended(handle):
    if nt.NtSuspendProcess(handle) < 0:
        raise RuntimeError('无法暂停游戏以安全更新任务入口')
    try:
        yield
    finally:
        if nt.NtResumeProcess(handle) < 0:
            raise RuntimeError('恢复游戏运行失败，请重新启动游戏')

def write_code(handle, address, raw):
    previous = w.DWORD()
    if not k.VirtualProtectEx(handle, address, len(raw), 0x40, ctypes.byref(previous)):
        mem.fail_win32('无法更新地图排布参数')
    try:
        mem.write_memory(handle, address, raw)
        if not k.FlushInstructionCache(handle, address, len(raw)):
            mem.fail_win32('无法刷新地图代码缓存')
    finally:
        ignored = w.DWORD()
        if not k.VirtualProtectEx(handle, address, len(raw), previous.value, ctypes.byref(ignored)):
            mem.fail_win32('无法恢复地图内存保护')

def backup():
    root = Path(os.environ.get('LOCALAPPDATA', Path.home()))/'AfterIncTrainer'
    target = root/'backups'/time.strftime('%Y%m%d-%H%M%S-before-tasks')
    target.mkdir(parents=True, exist_ok=False)
    source = Path.home()/'AppData/LocalLow/Ndemic Creations/After Inc. Revival'
    if source.is_dir():
        # Sentry owns locked diagnostic files while the game is running; these
        # are not saves and must not prevent the pre-write save backup.
        shutil.copytree(source, target/'LocalLow', ignore=shutil.ignore_patterns(
            'Player*.log', '.sentry-native', 'sentry-unity.lock'))
    steam = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)'))/'Steam/userdata'
    for source in steam.glob('*/3337140'):
        shutil.copytree(source, target/'Steam'/source.parent.name/'3337140')
    return str(target)

@session_log.audit
def operate(action='read', count=1):
    if action not in ('read', 'add', 'clear'):
        raise ValueError(action)
    if action == 'add':
        count = parse_count(count)
    with LOCK:
        pid = mem.find_process('After Inc. Revival.exe')
        profile = game_build.verified(pid)
        if profile['build'] not in TASK_PROFILES:
            raise RuntimeError('添加任务实验版仅支持 Steam 构建 25479909 / 25936576 / 26049821')
        layout = TASK_PROFILES[profile['build']]
        rights = 0x410 if action == 'read' else 0xC3A
        handle = k.OpenProcess(rights, False, pid)
        if not handle:
            mem.fail_win32('无法连接游戏，请以管理员身份运行修改器')
        try:
            base = profile['base']
            entry = delegate_address(handle, base, layout)
            found = extension_module(pid)
            if not found:
                if pointer(handle, entry) != base+layout['original']:
                    raise RuntimeError('任务入口已被其他程序修改，已停止操作')
                if mem.read_memory(handle, base+layout['point'], 6) != b'\x41\xb9\x06\x00\x00\x00':
                    raise RuntimeError('地图排布指令不匹配，已停止操作')
            if action == 'read' and not found:
                return dict(pid=pid, count=0, generated=0, calls=0, error=0, seeds=[], active=False)
            if action == 'clear' and not found:
                return dict(pid=pid, count=0, generated=0, calls=0, error=0, seeds=[], active=False)
            backup_path = None
            if action == 'add' and not found:
                backup_path = backup()
                found = ensure_loaded(handle, pid)
            dll_base, path = found
            if not path.is_file():
                raise RuntimeError('测试扩展的文件已移动，请重启游戏后使用新版修改器')
            if path.read_bytes() != dll_path().read_bytes():
                raise RuntimeError('游戏仍加载着之前的测试版扩展，请重启游戏后使用新版修改器')
            symbols = exports(path)
            state_address, hook = dll_base+symbols['TaskState'], dll_base+symbols['TaskLevels']
            raw_before = mem.read_memory(handle, state_address, STATE.size)
            state = decode_state(raw_before)
            if state['base'] not in (0, base) or state['build'] not in (0, int(profile['build'])):
                raise RuntimeError('任务扩展版本不匹配')
            current = pointer(handle, entry)
            if current not in (base+layout['original'], hook):
                raise RuntimeError('任务入口已被其他程序修改，已停止操作')
            if action == 'read':
                return dict(state, pid=pid, active=current == hook)
            seeds = plan_seeds(state['seeds'], count) if action == 'add' else []
            instruction = base+layout['point']
            expected_instruction = b'\x41\xb9'+struct.pack('<I', 6+state['count'])
            if mem.read_memory(handle, instruction, 6) != expected_instruction:
                raise RuntimeError('地图排布指令不匹配，已停止操作')
            new_state = STATE.pack(MAGIC, base, len(seeds), 0, state['calls'], 0,
                                   *(seeds+[0]*(10-len(seeds))), 0, 0, int(profile['build']))
            new_entry = struct.pack('<Q', hook if seeds else base+layout['original'])
            with suspended(handle):
                # Recheck after pausing, so read/preflight cannot race the game.
                if pointer(handle, entry) != current or delegate_address(handle, base, layout) != entry:
                    raise RuntimeError('地图状态发生变化，请重试')
                if mem.read_memory(handle, instruction, 6) != expected_instruction:
                    raise RuntimeError('地图排布参数发生变化，请重试')
                raw_before = mem.read_memory(handle, state_address, STATE.size)
                if decode_state(raw_before)['activity']:
                    raise RuntimeError('游戏正在生成任务，请稍后重试')
                try:
                    mem.write_memory(handle, state_address, new_state)
                    write_code(handle, instruction+2, struct.pack('<I', 6+len(seeds)))
                    mem.write_memory(handle, entry, new_entry)
                    if (mem.read_memory(handle, state_address, STATE.size) != new_state or
                            mem.read_memory(handle, entry, 8) != new_entry or
                            mem.read_memory(handle, instruction+2, 4) != struct.pack('<I', 6+len(seeds))):
                        raise RuntimeError('任务配置回读校验失败')
                except Exception:
                    mem.write_memory(handle, entry, struct.pack('<Q', current))
                    write_code(handle, instruction+2, expected_instruction[2:])
                    mem.write_memory(handle, state_address, raw_before)
                    raise
            result = dict(decode_state(new_state), pid=pid, active=bool(seeds), backup=backup_path, action=action)
            logs = session_log.operation_dir(Path(os.environ.get('LOCALAPPDATA', Path.home()))/'AfterIncTrainer/logs')
            try:
                logs.mkdir(parents=True, exist_ok=True)
                (logs/f'tasks-{time.time_ns()}.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            except OSError:
                result['log_warning'] = '操作成功，但日志保存失败'
            return result
        finally:
            k.CloseHandle(handle)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['read', 'add', 'clear'])
    parser.add_argument('--count', default='1')
    args = parser.parse_args()
    print(json.dumps(operate(args.action, args.count), ensure_ascii=False, indent=2))
