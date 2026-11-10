"""Check compiled native RVA selection against actual IL2CPP overload signatures.

Requires the project's existing build dumps, and native/build_task_test.cmd.
Do not reduce a list of overloads to a dictionary keyed only by method name.
"""
import ctypes
import json
from pathlib import Path
import re
import unittest


class TaskSignatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.release = Path(__file__).resolve().parents[1]
        cls.project = next(p for p in cls.release.parents if (p / 'il2cpp_dump').is_dir()) if not (cls.release / 'il2cpp_dump').is_dir() else cls.release
        cls.dll = ctypes.WinDLL(str(cls.release / 'native/AfterIncTaskAddressTest.dll'))
        cls.dll.TestMapped.argtypes = [ctypes.c_long, ctypes.c_uint64]
        cls.dll.TestMapped.restype = ctypes.c_uint64
        cls.dumps = {
            build: json.loads((cls.project / f'il2cpp_dump/build_{build}/script.json').read_text(encoding='utf-8'))
            for build in (25479909, 25936576, 26049821)
        }

    @staticmethod
    def signature(method):
        return re.sub(r'MethodInfo_[0-9A-Fa-f]+', 'MethodInfo', method['Signature'])

    def test_all_named_native_calls_preserve_exact_overload(self):
        # The other mappings refer to runtime thunks or metadata slots, not methods.
        for source in (0x69FD60, 0x6CB4A0, 0x8CB6B0, 0x8E8200, 0x8CAF50, 0x5FEA40):
            originals = [m for m in self.dumps[25479909]['ScriptMethod'] if m['Address'] == source]
            self.assertEqual(len(originals), 1)
            original = originals[0]
            for build in self.dumps:
                with self.subTest(source=hex(source), build=build):
                    selected = self.dll.TestMapped(build, source)
                    matches = [m for m in self.dumps[build]['ScriptMethod']
                               if m['Name'] == original['Name']
                               and self.signature(m) == self.signature(original)]
                    self.assertEqual(len(matches), 1, 'missing or ambiguous exact signature')
                    self.assertEqual(selected, matches[0]['Address'],
                                     f'Wrong overload: {original["Signature"]}')

    def test_previous_broken_addresses_are_wrong_overloads(self):
        methods = self.dumps[26049821]['ScriptMethod']
        for good, bad in ((0x985060, 0x9850E0), (0x984900, 0x984700)):
            correct = next(m for m in methods if m['Address'] == good)
            incorrect = next(m for m in methods if m['Address'] == bad)
            self.assertEqual(correct['Name'], incorrect['Name'])
            self.assertNotEqual(self.signature(correct), self.signature(incorrect))

    def test_unknown_build_never_calls_game(self):
        self.dll.TestMapped(0, 0)
        self.dll.TaskLevels.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self.dll.TaskLevels.restype = ctypes.c_void_p
        self.assertIsNone(self.dll.TaskLevels(None, None))
