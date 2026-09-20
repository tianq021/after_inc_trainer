from __future__ import annotations

import struct
import threading
import unittest
from unittest import mock

import memory_scan
from trainer_gui import TrainerApp


class TrainerFastMoveTests(unittest.TestCase):
    def test_checked_writer_reduces_timer_to_one(self) -> None:
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
        memory = {
            timer_address: struct.pack("<f", 5.0),
            soldier + 0x8C: b"\x00",
            soldier + 0x30: struct.pack("<Q", current_zone),
            soldier + 0x38: struct.pack("<Q", from_zone),
            soldier + 0xB8: struct.pack("<Q", design),
            design + 0x10: struct.pack("<Q", soldier),
        }
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

        def read_memory(_handle: int, address: int, size: int) -> bytes:
            return memory.get(address, b"")[:size]

        def write_memory(_handle: int, address: int, data: bytes) -> None:
            memory[address] = data

        with (
            mock.patch.object(memory_scan, "open_read_write", return_value=99),
            mock.patch.object(memory_scan, "read_memory", side_effect=read_memory),
            mock.patch.object(memory_scan, "write_memory", side_effect=write_memory),
            mock.patch.object(memory_scan.kernel32, "CloseHandle", return_value=True),
        ):
            changed = app._accelerate_moving_soldiers(log_change=False)

        self.assertEqual(changed, 1)
        self.assertEqual(memory[timer_address], struct.pack("<f", 1.0))


if __name__ == "__main__":
    unittest.main()
