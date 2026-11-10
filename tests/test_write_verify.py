"""Write-then-verify behaviour: short game-side races must not abort every lock."""

from __future__ import annotations

import struct
import threading
import unittest
from unittest import mock

import memory_scan
from trainer_gui import TrainerApp, TrainerError, TrainerTransientError


class FakeGameMemory:
    """Byte store that can mimic the game rewriting a field right after a write."""

    def __init__(
        self,
        values: dict[int, bytes] | None = None,
        foreign: bytes | None = None,
        clobbers: int | None = 0,
        blind_reads: int = 0,
        only_addresses: tuple[int, ...] | None = None,
    ) -> None:
        self.values = dict(values or {})
        self.foreign = foreign
        self.clobbers = clobbers  # None means "the game wins every write"
        self.blind_reads = blind_reads
        self.only_addresses = (
            set(only_addresses) if only_addresses is not None else None
        )
        self.writes: list[tuple[int, bytes]] = []

    def _contested(self, address: int) -> bool:
        if self.only_addresses is not None and address not in self.only_addresses:
            return False
        return self.foreign is not None and (self.clobbers is None or self.clobbers > 0)

    def read(self, _handle: int, address: int, size: int) -> bytes:
        if self.blind_reads > 0:
            self.blind_reads -= 1
            return b""
        return self.values.get(address, b"")[:size]

    def write(self, _handle: int, address: int, data: bytes) -> None:
        self.writes.append((address, data))
        if self._contested(address):
            if self.clobbers is not None:
                self.clobbers -= 1
            self.values[address] = self.foreign
        else:
            self.values[address] = data


class WriteVerifiedTests(unittest.TestCase):
    def test_accepts_first_verified_write(self) -> None:
        memory = FakeGameMemory()
        target = struct.pack("<f", 100.0)
        with (
            mock.patch.object(memory_scan, "read_memory", side_effect=memory.read),
            mock.patch.object(memory_scan, "write_memory", side_effect=memory.write),
        ):
            outcome = memory_scan.write_verified(99, 0x2000, target, retry_delay=0)
        self.assertTrue(outcome["verified"])
        self.assertEqual(outcome["attempts"], 1)
        self.assertEqual(memory.values[0x2000], target)

    def test_rewrites_after_the_game_wins_the_race(self) -> None:
        foreign = struct.pack("<f", 98.0)
        memory = FakeGameMemory(foreign=foreign, clobbers=1)
        target = struct.pack("<f", 100.0)
        with (
            mock.patch.object(memory_scan, "read_memory", side_effect=memory.read),
            mock.patch.object(memory_scan, "write_memory", side_effect=memory.write),
        ):
            outcome = memory_scan.write_verified(99, 0x2000, target, retry_delay=0)
        self.assertTrue(outcome["verified"])
        self.assertEqual(outcome["attempts"], 2)
        self.assertEqual(memory.values[0x2000], target)

    def test_reports_conflict_with_the_observed_bytes(self) -> None:
        foreign = struct.pack("<f", 98.0)
        memory = FakeGameMemory(foreign=foreign, clobbers=None)
        with (
            mock.patch.object(memory_scan, "read_memory", side_effect=memory.read),
            mock.patch.object(memory_scan, "write_memory", side_effect=memory.write),
        ):
            outcome = memory_scan.write_verified(99, 0x2000, struct.pack("<f", 100.0), retry_delay=0)
        self.assertFalse(outcome["verified"])
        self.assertEqual(outcome["observed"], foreign)
        self.assertEqual(outcome["attempts"], memory_scan.WRITE_VERIFY_ATTEMPTS)
        self.assertEqual(len(memory.writes), memory_scan.WRITE_VERIFY_ATTEMPTS)

    def test_tolerates_one_failed_readback(self) -> None:
        memory = FakeGameMemory(blind_reads=1)
        target = struct.pack("<f", 100.0)
        with (
            mock.patch.object(memory_scan, "read_memory", side_effect=memory.read),
            mock.patch.object(memory_scan, "write_memory", side_effect=memory.write),
        ):
            outcome = memory_scan.write_verified(99, 0x2000, target, retry_delay=0)
        self.assertTrue(outcome["verified"])
        self.assertEqual(outcome["attempts"], 1)
        self.assertEqual(memory.values[0x2000], target)


class WriteKeyConflictTests(unittest.TestCase):
    ADDRESS = 0x2000

    def _app(self, changes: list[dict]):
        app = TrainerApp.__new__(TrainerApp)
        app.memory_lock = threading.RLock()
        app.pid = 123
        app._ensure_attached = lambda: None
        app._build_changes = lambda _handle, _key, _target: [dict(item) for item in changes]
        return app

    def _change(self, address: int, before: float, after: float) -> dict:
        return {
            "name": "manpower",
            "address": address,
            "before": struct.pack("<f", before),
            "after": struct.pack("<f", after),
        }

    def _run(self, app, memory: FakeGameMemory, **kwargs):
        with (
            mock.patch.object(memory_scan, "open_read_write", return_value=99),
            mock.patch.object(memory_scan, "read_memory", side_effect=memory.read),
            mock.patch.object(memory_scan, "write_memory", side_effect=memory.write),
            mock.patch.object(memory_scan, "WRITE_VERIFY_RETRY_SECONDS", 0),
            mock.patch.object(memory_scan.kernel32, "CloseHandle", return_value=True),
        ):
            return app._write_key("manpower", 100.0, **kwargs)

    def test_lock_conflict_retries_instead_of_stopping(self) -> None:
        memory = FakeGameMemory(
            values={self.ADDRESS: struct.pack("<f", 84.0)},
            foreign=struct.pack("<f", 98.0),
            clobbers=None,
        )
        app = self._app([self._change(self.ADDRESS, 84.0, 100.0)])
        with self.assertRaises(TrainerTransientError):
            self._run(app, memory, log_change=False)

    def test_manual_conflict_reports_a_plain_error(self) -> None:
        memory = FakeGameMemory(
            values={self.ADDRESS: struct.pack("<f", 84.0)},
            foreign=struct.pack("<f", 98.0),
            clobbers=None,
        )
        app = self._app([self._change(self.ADDRESS, 84.0, 100.0)])
        with self.assertRaises(TrainerError) as context:
            self._run(app, memory, log_change=True)
        self.assertNotIsInstance(context.exception, TrainerTransientError)
        self.assertIn("暂停", str(context.exception))

    def test_one_lost_race_still_sets_the_value(self) -> None:
        memory = FakeGameMemory(
            values={self.ADDRESS: struct.pack("<f", 84.0)},
            foreign=struct.pack("<f", 98.0),
            clobbers=1,
        )
        app = self._app([self._change(self.ADDRESS, 84.0, 100.0)])
        self._run(app, memory, log_change=False)
        self.assertEqual(memory.values[self.ADDRESS], struct.pack("<f", 100.0))

    def test_failed_batch_restores_earlier_writes(self) -> None:
        first = 0x2000
        second = 0x2004
        memory = FakeGameMemory(
            values={first: struct.pack("<f", 84.0), second: struct.pack("<f", 90.0)},
            foreign=struct.pack("<f", 98.0),
            clobbers=None,
            only_addresses=(second,),
        )
        app = self._app(
            [self._change(first, 84.0, 100.0), self._change(second, 90.0, 100.0)]
        )
        with self.assertRaises(TrainerTransientError):
            self._run(app, memory, log_change=False)
        self.assertEqual(memory.values[first], struct.pack("<f", 84.0))


class FastMoveConflictTests(unittest.TestCase):
    def test_game_advancing_the_journey_is_transient(self) -> None:
        app = TrainerApp.__new__(TrainerApp)
        app.memory_lock = threading.RLock()
        app.pid = 123
        app.candidate = {}
        app._ensure_attached = lambda: None

        soldier = 0x100000
        design = 0x200000
        current_zone = 0x300000
        from_zone = 0x400000
        timer_address = soldier + 0x78
        memory = FakeGameMemory(
            values={
                timer_address: struct.pack("<f", 5.0),
                soldier + 0x8C: b"\x00",
                soldier + 0x30: struct.pack("<Q", current_zone),
                soldier + 0x38: struct.pack("<Q", from_zone),
                soldier + 0xB8: struct.pack("<Q", design),
                design + 0x10: struct.pack("<Q", soldier),
            },
            foreign=struct.pack("<f", 4.0),
            clobbers=None,
        )
        app._read_player_soldiers = lambda handle: [
            {
                "index": 0,
                "object": soldier,
                "state": 3,
                "is_dead": False,
                "current_zone": current_zone,
                "from_zone": from_zone,
                "design": design,
                "turns_address": timer_address,
                "turns": 5.0,
                "max_turns": 5.0,
                "can_accelerate": True,
            }
        ]

        with (
            mock.patch.object(memory_scan, "open_read_write", return_value=99),
            mock.patch.object(memory_scan, "read_memory", side_effect=memory.read),
            mock.patch.object(memory_scan, "write_memory", side_effect=memory.write),
            mock.patch.object(memory_scan, "WRITE_VERIFY_RETRY_SECONDS", 0),
            mock.patch.object(memory_scan.kernel32, "CloseHandle", return_value=True),
        ):
            with self.assertRaises(TrainerTransientError):
                app._accelerate_moving_soldiers(log_change=False)


if __name__ == "__main__":
    unittest.main()
