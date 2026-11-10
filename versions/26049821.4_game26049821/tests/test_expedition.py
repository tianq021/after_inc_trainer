import struct
import unittest

import expedition as e


class ExpeditionTests(unittest.TestCase):
    def setUp(self):
        self.base = 0x180000000
        self.data = {}
        for addr, value in ((self.base + e.SETTINGS_RVA, 0x10000),
                            (0x100B8, 0x20000), (0x20000, 0x30000),
                            (0x30000, 0x10000), (0x30108, 0x40000),
                            (0x40000, 0x50000),
                            (self.base + e.SEEDING_RVA, 0x50000)):
            self.data[addr] = struct.pack('<Q', value)
        self.data[0x40018] = struct.pack('<i', 0)
        self.writes = []

    def read(self, address, size):
        return self.data.get(address, b'')[:size]

    def write(self, address, raw):
        self.writes.append((address, raw))
        self.data[address] = raw

    def test_advance_and_reset_only_touch_day_field(self):
        for expected in (1, 2):
            self.assertEqual(e.change_checked(self.read, self.write, self.base)['days'], expected)
        self.assertEqual(e.change_checked(self.read, self.write, self.base, True)['days'], 0)
        self.assertEqual([a for a, _ in self.writes], [0x40018] * 3)

    def test_invalid_class_blocks_write(self):
        self.data[0x40000] = struct.pack('<Q', 0x60000)
        with self.assertRaises(RuntimeError):
            e.change_checked(self.read, self.write, self.base)
        self.assertEqual(self.writes, [])

    def test_changed_object_blocks_write(self):
        calls = 0
        def changing_read(address, size):
            nonlocal calls
            if address == self.base + e.SETTINGS_RVA:
                calls += 1
                if calls == 2:
                    self.data[0x40018] = struct.pack('<i', 1)
            return self.read(address, size)
        with self.assertRaises(RuntimeError):
            e.change_checked(changing_read, self.write, self.base)
        self.assertEqual(self.writes, [])

    def test_cap_blocks_advance_but_allows_reset(self):
        self.data[0x40018] = struct.pack('<i', e.MAX_DAYS)
        with self.assertRaises(RuntimeError):
            e.change_checked(self.read, self.write, self.base)
        self.assertEqual(self.writes, [])
        self.assertEqual(e.change_checked(self.read, self.write, self.base, True)['days'], 0)

    def test_short_read_blocks_write(self):
        self.data[0x30108] = b''
        with self.assertRaises(RuntimeError):
            e.change_checked(self.read, self.write, self.base)
        self.assertEqual(self.writes, [])

    def test_failed_write_is_not_reported_successful(self):
        with self.assertRaises(RuntimeError):
            e.change_checked(self.read, lambda a, b: None, self.base)


if __name__ == '__main__':
    unittest.main()
