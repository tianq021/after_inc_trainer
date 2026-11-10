"""Build-checked player soldier upgrades dispatched on the game's simulation thread."""
import json
import os
from pathlib import Path
import struct
import sys
import threading
import time
import game_build
import memory_scan as mem
import task_extension as bridge

DLL_NAME = 'AfterIncSoldierUpgrade.dll'
MAGIC = 0x315055524549444C
STATE = struct.Struct('<7Qiiff')
MANAGER_RVA = 75878720
SIMULATE_RVA = 0x7CABB0
VTABLE_SLOT = 0x138 + 4 * 16
ACTIONS = {'experience': 1, 'weapon': 2, 'squad': 3}
LOCK = threading.Lock()


def dll_path():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))/'native'/DLL_NAME


def decode(raw):
    magic, base, manager, game, glob, soldier, design, status, action, before, after = STATE.unpack(raw)
    if magic != MAGIC or status not in (-4, -3, -2, -1, 0, 1, 2, 3):
        raise RuntimeError('战士扩展状态校验失败，请重启游戏')
    return dict(base=base, manager=manager, game=game, global_simulation=glob,
                soldier=soldier, design=design, status=status, action=action, before=before, after=after)


def snapshot(handle, pid, profile):
    candidate = mem.resolve_settlement_from_gameassembly(handle, pid, profile['base'], profile['root'])
    read = lambda a, n: mem.read_memory(handle, a, n)
    game = int(candidate['game_controller'], 0)
    glob = int(candidate['global_simulation'], 0)
    manager = mem._read_u64(read, glob+0x20)
    klass = mem._read_u64(read, manager)
    if klass != mem._read_u64(read, profile['base']+MANAGER_RVA):
        raise RuntimeError('战士管理器类型不匹配')
    result = []
    for soldier in mem.read_player_soldiers(read, candidate):
        if soldier['is_dead']:
            continue
        obj, design = soldier['object'], soldier['design']
        exp, squads, weapons, strength = struct.unpack('<fiif', read(design+0x30, 16))
        size = struct.unpack('<f', read(obj+0x88, 4))[0]
        if not (0 <= exp <= 1000 and 0 <= squads <= 20 and 0 <= weapons <= 20 and
                0 <= strength <= 20 and 0.25 <= size <= 20):
            raise RuntimeError('战士数值超出本版本支持范围，已停止操作')
        ident_ptr = mem._read_u64(read, obj+0x10)
        length = mem._read_i32(read, ident_ptr+0x10)
        if not 0 < length <= 128:
            raise RuntimeError('战士标识异常')
        ident = read(ident_ptr+0x14, length*2).decode('utf-16-le')
        result.append(dict(object=obj, design=design, ident=ident, exp=exp,
                           squads=squads, weapons=weapons, strength=strength, size=size))
    return dict(pid=pid, manager=manager, game=game, global_simulation=glob,
                slot=klass+VTABLE_SLOT, soldiers=result)


def operate(action='read', selected=None):
    if action not in ('read', 'cancel', *ACTIONS):
        raise ValueError(action)
    with LOCK:
        pid = mem.find_process('After Inc. Revival.exe')
        profile = game_build.verified(pid)
        if profile['build'] != '25936576':
            raise RuntimeError('战士升级目前仅支持构建 25936576')
        handle = mem.kernel32.OpenProcess(0x410 if action == 'read' else 0xC3A, False, pid)
        if not handle:
            mem.fail_win32('无法连接游戏，请以管理员身份运行')
        try:
            current = snapshot(handle, pid, profile)
            loaded = bridge.extension_module(pid, DLL_NAME)
            if not loaded and action in ('read', 'cancel'):
                return dict(current, request=None)
            if action in ACTIONS:
                if not selected or (selected['pid'], selected['game'], selected['manager']) != (
                        pid, current['game'], current['manager']):
                    raise RuntimeError('关卡已变化，请重新读取并选择战士')
                match = next((s for s in current['soldiers'] if s['object'] == selected['object']
                              and s['design'] == selected['design'] and s['ident'] == selected['ident']), None)
                if not match:
                    raise RuntimeError('战士已变化或离场，请重新读取')
                if not loaded:
                    original = mem._read_u64(lambda a,n: mem.read_memory(handle,a,n), current['slot'])
                    if original != profile['base']+SIMULATE_RVA:
                        raise RuntimeError('战士模拟入口已变化，已停止操作')
                    bridge.backup()
                    loaded = bridge.ensure_loaded(handle, pid, DLL_NAME, dll_path())
            dll_base, path = loaded
            if path.read_bytes() != dll_path().read_bytes():
                raise RuntimeError('游戏仍加载旧版战士扩展，请重启游戏')
            symbols = bridge.exports(path)
            address, hook = dll_base+symbols['SoldierState'], dll_base+symbols['SoldierSimulate']
            read = lambda a,n: mem.read_memory(handle,a,n)
            state = decode(read(address, STATE.size))
            if state['base'] not in (0, profile['base']):
                raise RuntimeError('战士扩展模块基址不匹配')
            if action == 'read':
                return dict(current, request=state)
            with bridge.suspended(handle):
                state = decode(read(address, STATE.size))
                if action == 'cancel':
                    if state['status'] == 2:
                        raise RuntimeError('升级正在执行，请稍后读取结果')
                    if state['status'] == 1:
                        mem.write_memory(handle,address+56,struct.pack('<i',0))
                    return dict(current, request=decode(read(address,STATE.size)))
                if state['status'] in (1,2):
                    raise RuntimeError('已有升级等待执行，请短暂继续游戏或取消等待')
                fresh = snapshot(handle,pid,profile)
                if (fresh['game'],fresh['manager'],fresh['soldiers']) != (
                        current['game'],current['manager'],current['soldiers']):
                    raise RuntimeError('战士状态已变化，请重新读取后再试')
                slot_before = read(current['slot'],8)
                if struct.unpack('<Q',slot_before)[0] not in (profile['base']+SIMULATE_RVA,hook):
                    raise RuntimeError('战士模拟入口被其他程序修改')
                raw_before = read(address,STATE.size)
                raw = STATE.pack(MAGIC,profile['base'],current['manager'],current['game'],
                                 current['global_simulation'],match['object'],match['design'],
                                 1,ACTIONS[action],0,0)
                folder=Path(os.environ['LOCALAPPDATA'])/'AfterIncTrainer/logs'
                folder.mkdir(parents=True,exist_ok=True)
                (folder/f'soldier_{time.time_ns()}.json').write_text(json.dumps(
                    dict(action=action,before=match,pid=pid,build=profile['build']),ensure_ascii=False,indent=2),encoding='utf-8')
                try:
                    mem.write_memory(handle,address,raw)
                    bridge.write_code(handle,current['slot'],struct.pack('<Q',hook))
                    if read(address,STATE.size)!=raw or read(current['slot'],8)!=struct.pack('<Q',hook):
                        raise RuntimeError('升级请求回读失败')
                except Exception:
                    bridge.write_code(handle,current['slot'],slot_before)
                    mem.write_memory(handle,address,raw_before)
                    raise
            return dict(current,request=decode(raw))
        finally:
            mem.kernel32.CloseHandle(handle)


if __name__ == '__main__':
    print(json.dumps(operate(),ensure_ascii=False,indent=2))
