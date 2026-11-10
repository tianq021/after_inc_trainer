from __future__ import annotations

import struct
import unittest
from unittest import mock

import memory_scan


class FakeMemory:
    def __init__(self) -> None:
        self.bytes: dict[int, int] = {}

    def put(self, address: int, data: bytes) -> None:
        for offset, value in enumerate(data):
            self.bytes[address + offset] = value

    def put_u64(self, address: int, value: int) -> None:
        self.put(address, struct.pack("<Q", value))

    def put_i32(self, address: int, value: int) -> None:
        self.put(address, struct.pack("<i", value))

    def put_f32(self, address: int, value: float) -> None:
        self.put(address, struct.pack("<f", value))

    def read(self, address: int, size: int) -> bytes:
        try:
            return bytes(self.bytes[address + offset] for offset in range(size))
        except KeyError:
            return b""


def add_world(
    memory: FakeMemory,
    *,
    game: int,
    global_simulation: int,
    settlement: int,
    production_base: int,
) -> None:
    memory.put_u64(settlement, 0x88000000)  # WorldSettlementSimulator Il2CppClass
    memory.put_u64(game + 0x10, 0x90000000)  # UnityEngine.Object.m_CachedPtr
    memory.put_u64(game + 0x48, global_simulation)
    memory.put(game + 0x100, b"\x01")  # GameController.hasSetup
    memory.put_u64(global_simulation + 0x50, settlement)
    memory.put_u64(global_simulation + 0xE8, game)
    memory.put_u64(settlement + 0x10, game)
    memory.put_u64(settlement + 0x18, global_simulation)

    for index, (field_offset, (_, resource_type)) in enumerate(
        memory_scan.PRODUCTION_LAYOUT.items()
    ):
        production = production_base + index * 0x1000
        memory.put_u64(settlement + field_offset, production)
        memory.put_i32(production + 0x10, resource_type)
        memory.put_f32(production + 0x280, float(index))


def add_player_soldiers(
    memory: FakeMemory,
    *,
    game: int,
    global_simulation: int,
    specs: list[dict],
) -> None:
    manager = 0xA00000
    soldier_list = 0xA10000
    items = 0xA20000
    memory.put_u64(global_simulation + 0x20, manager)
    memory.put_u64(manager + 0x10, soldier_list)
    memory.put_u64(manager + 0xA0, global_simulation)
    memory.put_u64(manager + 0xA8, game)
    memory.put_u64(soldier_list + 0x10, items)
    memory.put_i32(soldier_list + 0x18, len(specs))
    memory.put_u64(items + 0x18, len(specs))

    for index, spec in enumerate(specs):
        soldier = 0xB00000 + index * 0x1000
        design = 0xC00000 + index * 0x1000
        memory.put_u64(items + 0x20 + index * 8, soldier)
        memory.put_u64(soldier, 0xD00000)
        memory.put_u64(soldier + 0x30, spec["current_zone"])
        memory.put_u64(soldier + 0x38, spec["from_zone"])
        memory.put_f32(soldier + 0x78, spec["turns"])
        memory.put_f32(soldier + 0x84, spec.get("max_turns", spec["turns"]))
        memory.put(soldier + 0x8C, bytes([spec.get("is_dead", 0)]))
        memory.put_i32(soldier + 0xAC, spec.get("state", 3))
        memory.put_u64(soldier + 0xB8, design)
        memory.put_u64(design + 0x10, soldier)


class AutoRebindTests(unittest.TestCase):
    def test_active_world_is_fully_validated(self) -> None:
        memory = FakeMemory()
        add_world(
            memory,
            game=0x100000,
            global_simulation=0x200000,
            settlement=0x300000,
            production_base=0x400000,
        )

        candidate = memory_scan.build_settlement_candidate(memory.read, 0x300000)

        self.assertEqual(candidate["game_controller"], "0x0000000000100000")
        self.assertEqual(candidate["global_simulation"], "0x0000000000200000")
        self.assertEqual(candidate["settlement_class"], "0x0000000088000000")
        self.assertEqual(candidate["productions"]["water"]["resource_type"], 13)
        self.assertEqual(candidate["productions"]["wood"]["total"], 16.0)

    def test_save_reload_follows_game_controller_to_new_world(self) -> None:
        memory = FakeMemory()
        game = 0x100000
        add_world(
            memory,
            game=game,
            global_simulation=0x200000,
            settlement=0x300000,
            production_base=0x400000,
        )
        old_candidate = memory_scan.build_settlement_candidate(memory.read, 0x300000)

        add_world(
            memory,
            game=game,
            global_simulation=0x600000,
            settlement=0x700000,
            production_base=0x800000,
        )
        refreshed = memory_scan.follow_active_settlement(memory.read, old_candidate)

        self.assertEqual(refreshed["settlement"], "0x0000000000700000")
        self.assertEqual(refreshed["global_simulation"], "0x0000000000600000")
        self.assertNotEqual(
            refreshed["productions"]["manpower"]["total_address"],
            old_candidate["productions"]["manpower"]["total_address"],
        )

    def test_destroyed_game_controller_is_rejected(self) -> None:
        memory = FakeMemory()
        add_world(
            memory,
            game=0x100000,
            global_simulation=0x200000,
            settlement=0x300000,
            production_base=0x400000,
        )
        memory.put_u64(0x100000 + 0x10, 0)

        with self.assertRaisesRegex(RuntimeError, "destroyed"):
            memory_scan.build_settlement_candidate(memory.read, 0x300000)

    def test_recreated_game_controller_is_found_in_nearby_heap(self) -> None:
        memory = FakeMemory()
        add_world(
            memory,
            game=0x100000,
            global_simulation=0x200000,
            settlement=0x300000,
            production_base=0x400000,
        )
        old_candidate = memory_scan.build_settlement_candidate(memory.read, 0x300000)
        memory.put_u64(0x100000 + 0x10, 0)
        add_world(
            memory,
            game=0x110000,
            global_simulation=0x600000,
            settlement=0x700000,
            production_base=0x800000,
        )

        def dense_read(_handle: int, address: int, size: int) -> bytes:
            return bytes(memory.bytes.get(address + offset, 0) for offset in range(size))

        with (
            mock.patch.object(memory_scan, "readable_private_regions", return_value=[(0x100000, 0x900000)]),
            mock.patch.object(memory_scan, "read_memory", side_effect=dense_read),
        ):
            refreshed = memory_scan.locate_nearby_settlement_candidate(
                99, old_candidate, radius=0x500000
            )

        self.assertIsNotNone(refreshed)
        assert refreshed is not None
        self.assertEqual(refreshed["settlement"], "0x0000000000700000")
        self.assertEqual(refreshed["game_controller"], "0x0000000000110000")

    def test_gameassembly_static_root_resolves_active_world(self) -> None:
        memory = FakeMemory()
        game = 0x100000
        add_world(
            memory,
            game=game,
            global_simulation=0x200000,
            settlement=0x300000,
            production_base=0x400000,
        )
        module_base = 0x180000000
        steam_manager_class = 0x500000
        static_fields = 0x510000
        steam_manager = 0x520000
        launch_handler = 0x530000
        memory.put_u64(
            module_base + memory_scan.STEAM_MANAGER_TYPE_INFO_RVA,
            steam_manager_class,
        )
        memory.put_u64(
            steam_manager_class + memory_scan.IL2CPP_CLASS_STATIC_FIELDS_OFFSET,
            static_fields,
        )
        memory.put_u64(
            static_fields + memory_scan.STEAM_MANAGER_INSTANCE_STATIC_OFFSET,
            steam_manager,
        )
        memory.put_u64(steam_manager, steam_manager_class)
        memory.put_u64(steam_manager + 0x10, 0x90001000)
        memory.put_u64(
            steam_manager + memory_scan.STEAM_MANAGER_LAUNCH_OFFSET,
            launch_handler,
        )
        memory.put_u64(
            launch_handler + memory_scan.STEAM_LAUNCH_SCENARIO_LAUNCHER_OFFSET,
            game,
        )

        def dense_read(_handle: int, address: int, size: int) -> bytes:
            return bytes(memory.bytes.get(address + offset, 0) for offset in range(size))

        with (
            mock.patch.object(
                memory_scan,
                "readable_private_regions",
                return_value=[(0x100000, 0x500000)],
            ),
            mock.patch.object(memory_scan, "read_memory", side_effect=dense_read),
        ):
            resolved = memory_scan.resolve_settlement_from_gameassembly(
                99, 1234, module_base
            )

        self.assertEqual(resolved["settlement"], "0x0000000000300000")
        self.assertEqual(resolved["game_controller"], "0x0000000000100000")
        self.assertEqual(resolved["gameassembly_base"], "0x0000000180000000")
        self.assertEqual(
            resolved["binding_source"], "steam_manager_scenario_launcher"
        )

    def test_only_active_player_journeys_are_accelerated(self) -> None:
        memory = FakeMemory()
        game = 0x100000
        global_simulation = 0x200000
        settlement = 0x300000
        add_world(
            memory,
            game=game,
            global_simulation=global_simulation,
            settlement=settlement,
            production_base=0x400000,
        )
        add_player_soldiers(
            memory,
            game=game,
            global_simulation=global_simulation,
            specs=[
                {"current_zone": 0xE00000, "from_zone": 0xE01000, "turns": 5.0},
                {"current_zone": 0xE02000, "from_zone": 0xE03000, "turns": 1.0},
                {"current_zone": 0xE04000, "from_zone": 0xE04000, "turns": 5.0},
                {
                    "current_zone": 0xE05000,
                    "from_zone": 0xE06000,
                    "turns": 5.0,
                    "is_dead": 1,
                },
            ],
        )
        candidate = memory_scan.build_settlement_candidate(memory.read, settlement)

        soldiers = memory_scan.read_player_soldiers(memory.read, candidate)

        self.assertEqual(len(soldiers), 4)
        self.assertEqual(
            [entry["index"] for entry in soldiers if entry["can_accelerate"]], [0]
        )
        self.assertEqual(soldiers[0]["turns_address"], 0xB00000 + 0x78)

    def test_suspicious_movement_timer_is_not_writable(self) -> None:
        memory = FakeMemory()
        game = 0x100000
        global_simulation = 0x200000
        settlement = 0x300000
        add_world(
            memory,
            game=game,
            global_simulation=global_simulation,
            settlement=settlement,
            production_base=0x400000,
        )
        add_player_soldiers(
            memory,
            game=game,
            global_simulation=global_simulation,
            specs=[
                {
                    "current_zone": 0xE00000,
                    "from_zone": 0xE01000,
                    "turns": 2.5,
                    "max_turns": 3.0,
                }
            ],
        )
        candidate = memory_scan.build_settlement_candidate(memory.read, settlement)

        soldiers = memory_scan.read_player_soldiers(memory.read, candidate)

        self.assertFalse(soldiers[0]["can_accelerate"])


if __name__ == "__main__":
    unittest.main()
