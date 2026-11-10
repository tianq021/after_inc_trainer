import struct
import unittest

import teams
import game_build


class TeamTests(unittest.TestCase):
    def setUp(self):
        self.data = bytearray(0xA0000)
        self.base = 0x10000000
        self.candidate = dict(game_controller='0x10000', global_simulation='0x20000')
        self.type_slot = struct.pack('<Q', 0x30000)
        for address, value in ((0x200C0, 0x40000), (0x40000, 0x30000),
                               (0x40030, 0x10000), (0x40010, 0x50000),
                               (0x50018, 0x60000), (0x60018, 3)):
            self.put(address, '<Q', value)
        self.put(0x50020, '<iiii', 3, -1, 0, 3)
        for i, (name, count) in enumerate((('scoutingQueue', 1), ('researchQueue', 7), ('defaultQueue', 1))):
            key = 0x70000 + i * 0x100
            self.put(0x60020 + i * 24, '<iiQi', i + 1, -1, key, count)
            self.put(key + 0x10, '<i', len(name))
            raw = name.encode('utf-16-le')
            self.data[key + 0x14:key + 0x14 + len(raw)] = raw
        self.writes = []

    def put(self, address, fmt, *values):
        raw = struct.pack(fmt, *values)
        self.data[address:address + len(raw)] = raw

    def read(self, address, size):
        if address == self.base + teams.MANAGER_TYPE_RVA:
            return self.type_slot[:size]
        return bytes(self.data[address:address + size])

    def write(self, address, raw):
        self.writes.append((address, raw))
        self.data[address:address + len(raw)] = raw

    def snapshot(self):
        return teams.resolve(self.read, self.candidate, self.base)

    def test_new_build_uses_its_own_type_slot(self):
        profile = next(p for p in game_build.PROFILES.values() if p['build'] == '25936576')
        def read(address, size):
            if address == self.base + profile['teams']:
                return self.type_slot[:size]
            if address == self.base + teams.MANAGER_TYPE_RVA:
                return b'\x00' * size
            return self.read(address, size)
        result = teams.resolve(read, self.candidate, self.base, profile['teams'])
        self.assertEqual(result['teams']['build']['count'], 1)
        with self.assertRaises(RuntimeError):
            teams.resolve(read, self.candidate, self.base)

    def test_reads_named_queues_and_preserves_other_entries(self):
        before = bytes(self.data)
        result = teams.change_checked(self.snapshot, self.write, 'build', expected=1)
        self.assertEqual(result['teams']['build']['count'], 2)
        self.assertEqual(result['teams']['explore']['count'], 1)
        expected = bytearray(before)
        struct.pack_into('<i', expected, 0x60060, 2)
        self.assertEqual(self.data, expected)
        self.assertEqual(len(self.writes), 1)

    def test_exploration_addition(self):
        result = teams.change_checked(self.snapshot, self.write, 'explore')
        self.assertEqual(result['teams']['explore']['count'], 2)
        self.assertEqual(result['teams']['build']['count'], 1)

    def test_cap_and_expected_value_block_writes(self):
        for value, expected in ((20, None), (1, 2), (-1, None), (21, None)):
            self.put(0x60030, '<i', value)
            with self.assertRaises(RuntimeError):
                teams.change_checked(self.snapshot, self.write, 'explore', expected)
        self.assertFalse(self.writes)

    def test_bad_class_back_reference_and_array_size_block(self):
        for address, bad in ((0x40000, 0x30008), (0x40030, 0x10008), (0x60018, 2)):
            previous = self.read(address, 8)
            self.put(address, '<Q', bad)
            with self.assertRaises(RuntimeError):
                teams.change_checked(self.snapshot, self.write, 'build')
            self.data[address:address + 8] = previous
        self.assertFalse(self.writes)

    def test_scene_change_blocks_write(self):
        calls = 0
        def snapshot():
            nonlocal calls
            calls += 1
            result = self.snapshot()
            if calls == 2:
                result['game'] += 8
            return result
        with self.assertRaises(RuntimeError):
            teams.change_checked(snapshot, self.write, 'build')
        self.assertFalse(self.writes)

    def test_failed_write_is_not_success(self):
        with self.assertRaises(RuntimeError):
            teams.change_checked(self.snapshot, lambda a, b: None, 'build')

    def test_log_failure_blocks_write(self):
        def fail(*args):
            raise OSError('disk full')
        with self.assertRaises(OSError):
            teams.change_checked(self.snapshot, self.write, 'build', before_write=fail)
        self.assertFalse(self.writes)

    def test_deleted_or_missing_key_blocks_write(self):
        self.put(0x60020, '<i', -1)
        with self.assertRaises(RuntimeError):
            teams.change_checked(self.snapshot, self.write, 'build')
        self.assertFalse(self.writes)

    def test_truncated_read_blocks_write(self):
        with self.assertRaises(RuntimeError):
            teams.resolve(lambda a, n: b'', self.candidate, self.base)


if __name__ == '__main__':
    unittest.main()
