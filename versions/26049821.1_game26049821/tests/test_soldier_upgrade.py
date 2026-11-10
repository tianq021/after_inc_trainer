import ctypes
import unittest
from unittest.mock import patch
import soldier_upgrade as s


class SoldierTests(unittest.TestCase):
    def test_native_state_abi(self):
        dll=ctypes.WinDLL(str(s.dll_path()))
        raw=bytes((ctypes.c_char*s.STATE.size).in_dll(dll,'SoldierState'))
        self.assertEqual(s.STATE.size,72)
        state=s.decode(raw)
        self.assertEqual((state['status'],state['base'],state['action']),(0,0,0))

    def test_unknown_version_never_opens_process(self):
        with patch.object(s.mem,'find_process',return_value=1), \
             patch.object(s.game_build,'verified',return_value={'build':'25479909'}), \
             patch.object(s.mem.kernel32,'OpenProcess') as opened:
            with self.assertRaises(RuntimeError):
                s.operate('upgrade',{})
            opened.assert_not_called()

    def test_reload_rejects_stale_soldier_before_loading_extension(self):
        with patch.object(s.mem,'find_process',return_value=1), \
             patch.object(s.game_build,'verified',return_value={'build':'26049821','base':0x10000}), \
             patch.object(s.mem.kernel32,'OpenProcess',return_value=1), \
             patch.object(s.mem.kernel32,'CloseHandle'), \
             patch.object(s,'snapshot',return_value={'game':200,'manager':300,'soldiers':[]}), \
             patch.object(s.bridge,'extension_module',return_value=None), \
             patch.object(s.bridge,'ensure_loaded') as loaded:
            with self.assertRaisesRegex(RuntimeError,'关卡已变化'):
                s.operate('squad',{'pid':1,'game':199,'manager':300})
            loaded.assert_not_called()

    def test_corrupt_state_is_rejected(self):
        for magic,status in [(0,0),(s.MAGIC,99)]:
            raw=s.STATE.pack(magic,0,0,0,0,0,0,status,0,0,0)
            with self.assertRaises(RuntimeError):
                s.decode(raw)
