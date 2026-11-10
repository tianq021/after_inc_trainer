"""Read-only installed-build smoke test; never injects or changes game state."""
import json
from pathlib import Path
import game_build
import memory_scan as mem
import soldier_upgrade
import task_extension
import teams
import expedition


def verify():
    pid = mem.find_process('After Inc. Revival.exe')
    profile = game_build.verified(pid)
    assert profile['build'] == '26049821', profile['build']
    handle = mem.open_read_only(pid)
    try:
        world = mem.resolve_settlement_from_gameassembly(
            handle, pid, profile['base'], profile['root'])
        soldiers = soldier_upgrade.snapshot(handle, pid, profile)
        original = mem._read_u64(
            lambda a, n: mem.read_memory(handle, a, n), soldiers['slot'])
        assert original == profile['base'] + soldier_upgrade.SIMULATE_RVA, hex(original)
    finally:
        mem.kernel32.CloseHandle(handle)
    report = dict(pid=pid, build=profile['build'], sha256=profile['sha256'],
                  world=world, soldiers=soldiers, teams=teams.operate(),
                  expedition=expedition.operate('read'),
                  tasks=task_extension.operate('read'), writes_performed=False)
    Path(__file__).with_name('live_readonly_verification.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    verify()
