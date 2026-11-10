"""Checked team-capacity edits for the fingerprinted 25479909 build.

GlobalSimulation + C0 -> UnifiedConstructionZoneJobManager; +10 is
Dictionary<string,int> builderCount. GetBuilderCapacity reads this dictionary;
SetBuilderCapacity assigns it without other effects for nonnegative values.
Only existing scoutingQueue/defaultQueue value slots are changed.
"""
import json
import session_log
import os
from pathlib import Path
import struct
import time

import game_build
import memory_scan as mem

MANAGER_TYPE_RVA = 64247336
QUEUES = {"explore": "scoutingQueue", "build": "defaultQueue"}
MAX_TEAMS = 20


def resolve(read, candidate, base, manager_type_rva=MANAGER_TYPE_RVA):
    def exact(address, size):
        raw = read(address, size)
        if len(raw) != size:
            raise RuntimeError("队伍数据读取不完整，请重新进入关卡")
        return raw

    def ptr(address):
        value = struct.unpack('<Q', exact(address, 8))[0]
        if not 0x10000 <= value < 0x800000000000 or value & 7:
            raise RuntimeError("队伍对象尚未就绪")
        return value

    def integer(address):
        return struct.unpack('<i', exact(address, 4))[0]

    game = int(candidate['game_controller'], 0)
    glob = int(candidate['global_simulation'], 0)
    manager = ptr(glob + 0xC0)
    if ptr(manager) != ptr(base + manager_type_rva) or ptr(manager + 0x30) != game:
        raise RuntimeError("队伍管理器类型或关卡验证失败")
    dictionary = ptr(manager + 0x10)
    entries = ptr(dictionary + 0x18)
    count, free_list, free_count, version = struct.unpack('<iiii', exact(dictionary + 0x20, 16))
    capacity = struct.unpack('<Q', exact(entries + 0x18, 8))[0]
    if not (0 <= free_count <= count <= capacity <= 256):
        raise RuntimeError("队伍容量表结构异常")
    result = dict(game=game, global_simulation=glob, manager=manager,
                  dictionary=dictionary, entries=entries, count=count,
                  free_list=free_list, free_count=free_count, version=version, teams={})
    for index in range(count):
        address = entries + 0x20 + index * 24
        hash_code, next_index, key, value = struct.unpack('<iiQi', exact(address, 20))
        if hash_code < 0:
            continue
        if key < 0x10000 or key >= 0x800000000000 or key & 7:
            raise RuntimeError("队伍名称指针异常")
        length = integer(key + 0x10)
        if not 1 <= length <= 128:
            raise RuntimeError("队伍名称长度异常")
        name = exact(key + 0x14, length * 2).decode('utf-16-le')
        for kind, queue in QUEUES.items():
            if name == queue:
                if kind in result['teams'] or not 0 <= value <= MAX_TEAMS:
                    raise RuntimeError("队伍数量异常或超出支持范围（0–20）")
                result['teams'][kind] = dict(count=value, address=address + 16, key=key)
    if set(result['teams']) != set(QUEUES):
        raise RuntimeError("未找到探索或建设队伍，请先进入关卡")
    if exact(dictionary + 0x20, 16) != struct.pack('<iiii', count, free_list, free_count, version):
        raise RuntimeError("队伍容量表正在变化，请重试")
    return result


def change_checked(snapshot, write, kind, expected=None, before_write=None, target=None):
    if kind not in QUEUES:
        raise ValueError("未知队伍类型")
    before = snapshot()
    entry = before['teams'][kind]
    previous = entry['count']
    if expected is not None and previous != expected:
        raise RuntimeError("当前队伍数量已变化，未执行增加")
    if target is not None and (type(target) is not int or not 1 <= target <= MAX_TEAMS):
        raise ValueError('队伍目标必须是 1–20 的整数')
    if target is not None and previous >= target:
        return before
    if previous >= MAX_TEAMS:
        raise RuntimeError("队伍数量已达上限 20")
    wanted_count = previous + 1 if target is None else target
    if before_write:
        before_write(before, wanted_count)
    if snapshot() != before:
        raise RuntimeError("关卡或队伍数量已变化，请重试")
    write(entry['address'], struct.pack('<i', wanted_count))
    after = snapshot()
    wanted = dict(before, teams={k: dict(v) for k, v in before['teams'].items()})
    wanted['teams'][kind]['count'] = wanted_count
    if after != wanted:
        raise RuntimeError("已尝试写入，但回读不一致；请读取数量后再操作")
    return dict(after, changed=kind, previous=previous)


@session_log.audit
def operate(kind=None, expected=None, log_dir=None, target=None):
    if kind is not None and kind not in QUEUES:
        raise ValueError("未知队伍类型")
    pid = mem.find_process('After Inc. Revival.exe')
    profile = game_build.verified(pid)
    if 'teams' not in profile:
        raise RuntimeError("队伍功能目前仅支持构建 25479909 / 25936576 / 26049821")
    handle = (mem.open_read_only if kind is None else mem.open_read_write)(pid)
    log_path = None
    try:
        read = lambda address, size: mem.read_memory(handle, address, size)
        def snapshot():
            candidate = mem.resolve_settlement_from_gameassembly(
                handle, pid, profile['base'], profile['root'])
            return resolve(read, candidate, profile['base'], profile['teams'])
        def record_before(before, target):
            nonlocal log_path
            folder = Path(log_dir) if log_dir else session_log.operation_dir(Path(os.environ['LOCALAPPDATA']) / 'AfterIncTrainer' / 'logs')
            folder.mkdir(parents=True, exist_ok=True)
            log_path = folder / f'teams_{time.time_ns()}.json'
            log_path.write_text(json.dumps(dict(status='prepared', pid=pid,
                build=profile['build'], kind=kind, target=target, before=before),
                ensure_ascii=False, indent=2), encoding='utf-8')
        result = snapshot() if kind is None else change_checked(
            snapshot, lambda a, b: mem.write_memory(handle, a, b), kind, expected, record_before, target)
        result.update(pid=pid, build=profile['build'])
        if log_path:
            try:
                record = json.loads(log_path.read_text(encoding='utf-8'))
                record.update(status='verified', after=result)
                log_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
            except OSError:
                result['log_warning'] = '已增加，但结果日志保存失败'
        return result
    finally:
        mem.kernel32.CloseHandle(handle)
