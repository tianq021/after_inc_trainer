"""Build-checked player soldier upgrades dispatched on the game's simulation thread."""
import json
import session_log
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
DIAG = struct.Struct('<12i5Q')
DIAG_KEYS = ('hook_calls runs_started identity_fails stage event_found engaged_before '
             'has_upgrades_left opt_has_value opt_is_object created_count last_status '
             'reserved last_manager last_game last_global opt_value opt_object_value').split()
STAGE_TEXT = {
    1: '事件对象校验（events 归属或所在区域）',
    2: '游戏正在屏蔽事件（blockGameEvents）',
    3: '事件表结构校验（allEvents 或 GameEvent 归属）',
    4: '事件表里没有 SoldierUpgrade',
    5: '事件表里找到多个 SoldierUpgrade',
    6: '待处理升级列表结构异常',
    7: '已有待处理升级',
    8: 'TryFire 没有返回可用的升级标记',
    9: '生成的升级标记里事件数不是 1',
    10: '成功',
}
MANAGER_RVA = 75878720
SIMULATE_RVA = 0x7CAC10
VTABLE_SLOT = 0x138 + 4 * 16
ACTIONS = {'upgrade': 1, 'weapon': 2, 'squad': 3}
# How long to let the game's simulation thread pick the request up before
# reporting back. The game pauses while its window is unfocused, so a click in
# the trainer would otherwise look like a request that never ran.
RESULT_WAIT_SECONDS = 8.0
LOCK = threading.Lock()
# Remembers the last armed request so a stuck one can be explained precisely.
LAST_REQUEST = {}


def dll_path():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))/'native'/DLL_NAME


def log_folder():
    return session_log.operation_dir(Path(os.environ['LOCALAPPDATA'])/'AfterIncTrainer/logs')


def write_log(prefix, payload):
    try:
        folder = log_folder()
        folder.mkdir(parents=True, exist_ok=True)
        (folder/f'{prefix}_{time.time_ns()}.json').write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    except OSError:
        pass


def decode(raw):
    magic, base, manager, game, glob, soldier, design, status, action, before, after = STATE.unpack(raw)
    if magic != MAGIC or status not in range(-9, 4):
        raise RuntimeError('战士扩展状态校验失败，请重启游戏')
    return dict(base=base, manager=manager, game=game, global_simulation=glob,
                soldier=soldier, design=design, status=status, action=action, before=before, after=after)


def decode_diag(raw):
    if raw is None:
        return None
    return dict(zip(DIAG_KEYS, DIAG.unpack(raw)))


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


def pending_message(diag):
    """Explain a request that is still waiting for the game's simulation thread."""
    armed = LAST_REQUEST.get('hook_calls')
    if diag and armed is not None and diag['hook_calls'] == armed:
        return ('游戏没有推进升级：挂钩已装好，但游戏线程一次都没有调用模拟函数。'
                '切换到游戏窗口并让时间前进一下（窗口失焦时游戏会暂停），再点“读取战士”。')
    return '已有升级等待执行，请短暂继续游戏或取消等待'


def result_payload(state, diag, action):
    payload = dict(flow='result', action=action, status=state['status'],
                   before=state['before'], after=state['after'])
    if state['status'] < 0:
        payload['stage'] = STAGE_TEXT.get((diag or {}).get('stage'), '未知阶段')
    if diag:
        payload['diag'] = diag
        payload['hook_calls_since_arm'] = (diag['hook_calls'] - LAST_REQUEST.get('hook_calls', 0)
                                           if LAST_REQUEST else None)
    return payload


def await_result(handle, address, diag_address, deadline):
    """Poll until the game's simulation thread settles the pending request."""
    while time.monotonic() < deadline:
        time.sleep(0.2)
        try:
            state = decode(mem.read_memory(handle, address, STATE.size))
        except RuntimeError:
            continue  # the game thread was writing the state while we read it
        if state['status'] not in (1, 2):
            raw = mem.read_memory(handle, diag_address, DIAG.size) if diag_address else None
            return state, decode_diag(raw)
    return None


@session_log.audit
def operate(action='read', selected=None):
    if action not in ('read', 'cancel', *ACTIONS):
        raise ValueError(action)
    with LOCK:
        pid = mem.find_process('After Inc. Revival.exe')
        profile = game_build.verified(pid)
        if profile['build'] != '26049821':
            raise RuntimeError('战士升级目前仅支持构建 26049821')
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
                    original = mem._read_u64(lambda a, n: mem.read_memory(handle, a, n), current['slot'])
                    if original != profile['base']+SIMULATE_RVA:
                        raise RuntimeError('战士模拟入口已变化，已停止操作')
                    bridge.backup()
                    loaded = bridge.ensure_loaded(handle, pid, DLL_NAME, dll_path())
            dll_base, path = loaded
            if path.read_bytes() != dll_path().read_bytes():
                raise RuntimeError('游戏仍加载旧版战士扩展，请重启游戏')
            symbols = bridge.exports(path)
            address, hook = dll_base+symbols['SoldierState'], dll_base+symbols['SoldierSimulate']
            diag_address = dll_base+symbols['SoldierDiag'] if 'SoldierDiag' in symbols else None
            read = lambda a, n: mem.read_memory(handle, a, n)
            state = decode(read(address, STATE.size))
            diag = decode_diag(read(diag_address, DIAG.size) if diag_address else None)
            if state['base'] not in (0, profile['base']):
                raise RuntimeError('战士扩展模块基址不匹配')
            if action == 'read':
                if state['status'] not in (1, 2) and LAST_REQUEST.get('status') == 1:
                    write_log('soldier-result', result_payload(state, diag, LAST_REQUEST.get('action')))
                    LAST_REQUEST['status'] = state['status']
                return dict(current, request=state, diag=diag)
            with bridge.suspended(handle):
                state = decode(read(address, STATE.size))
                diag = decode_diag(read(diag_address, DIAG.size) if diag_address else None)
                if action == 'cancel':
                    if state['status'] == 2:
                        raise RuntimeError('升级正在执行，请稍后读取结果')
                    if state['status'] == 1:
                        mem.write_memory(handle, address+56, struct.pack('<i', 0))
                    LAST_REQUEST.clear()
                    return dict(current, request=decode(read(address, STATE.size)), diag=diag)
                if state['status'] in (1, 2):
                    if LAST_REQUEST.get('status') == 1:
                        write_log('soldier-result', result_payload(state, diag, LAST_REQUEST.get('action')))
                    raise RuntimeError(pending_message(diag))
                if state['status'] != 0 and LAST_REQUEST.get('status') == 1:
                    write_log('soldier-result', result_payload(state, diag, LAST_REQUEST.get('action')))
                fresh = snapshot(handle, pid, profile)
                if (fresh['game'], fresh['manager'], fresh['soldiers']) != (
                        current['game'], current['manager'], current['soldiers']):
                    raise RuntimeError('战士状态已变化，请重新读取后再试')
                slot_before = read(current['slot'], 8)
                if struct.unpack('<Q', slot_before)[0] not in (profile['base']+SIMULATE_RVA, hook):
                    raise RuntimeError('战士模拟入口被其他程序修改')
                raw_before = read(address, STATE.size)
                raw = STATE.pack(MAGIC, profile['base'], current['manager'], current['game'],
                                 current['global_simulation'], match['object'], match['design'],
                                 1, ACTIONS[action], 0, 0)
                write_log('soldier', dict(action=action, before=match, pid=pid, build=profile['build'],
                                          hook_calls=(diag or {}).get('hook_calls')))
                try:
                    mem.write_memory(handle, address, raw)
                    bridge.write_code(handle, current['slot'], struct.pack('<Q', hook))
                    if read(address, STATE.size) != raw or read(current['slot'], 8) != struct.pack('<Q', hook):
                        raise RuntimeError('升级请求回读失败')
                except Exception:
                    bridge.write_code(handle, current['slot'], slot_before)
                    mem.write_memory(handle, address, raw_before)
                    raise
            LAST_REQUEST.clear()
            LAST_REQUEST.update(status=1, action=action, hook_calls=(diag or {}).get('hook_calls'))
            settled = await_result(handle, address, diag_address,
                                   time.monotonic()+RESULT_WAIT_SECONDS)
            if settled:
                state, diag = settled
                write_log('soldier-result', result_payload(state, diag, action))
                LAST_REQUEST['status'] = state['status']
                return dict(current, request=state, diag=diag)
            return dict(current, request=decode(raw), diag=diag)
        finally:
            mem.kernel32.CloseHandle(handle)


if __name__ == '__main__':
    print(json.dumps(operate(), ensure_ascii=False, indent=2))
