import struct
import unittest
from unittest import mock
import task_extension as t


class TaskExtensionTests(unittest.TestCase):
    def test_unsupported_build_rejects_extension_before_opening_process(self):
        with mock.patch.object(t.mem, 'find_process', return_value=123), \
             mock.patch.object(t.game_build, 'verified', return_value={'build': '24931318'}), \
             mock.patch.object(t.k, 'OpenProcess') as opened:
            with self.assertRaises(RuntimeError):
                t.operate('add', 1)
            opened.assert_not_called()

    def test_count_rejects_invalid_inputs(self):
        for value in ('', '0', '-1', '6', '1.5', '1e2', '１２', True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                t.parse_count(value)
        self.assertEqual(t.parse_count(' 5 '), 5)

    def test_add_keeps_existing_seeds_and_avoids_duplicates(self):
        with mock.patch.object(t.secrets, 'randbelow', side_effect=[7, 8, 8, 9]):
            self.assertEqual(t.plan_seeds([20007], 2), [20007, 20008, 20009])

    def test_session_limit_is_enforced(self):
        with self.assertRaises(ValueError):
            t.plan_seeds([20001, 20002, 20003, 20004], 2)

    def test_dll_state_layout_matches_export(self):
        dll = t.ctypes.WinDLL(str(t.dll_path()))
        data = (t.ctypes.c_char*t.STATE.size).in_dll(dll, 'TaskState')
        status = t.decode_state(bytes(data))
        self.assertEqual(status['count'], 0)
        self.assertEqual(status['activity'], 0)
        self.assertEqual(status['base'], 0)
        self.assertEqual(t.STATE.size, 88)

    def test_invalid_state_is_rejected(self):
        raw = t.STATE.pack(0, 0, 0, 0, 0, 0, *([0]*10), 0, 0, 0)
        with self.assertRaises(RuntimeError):
            t.decode_state(raw)

    def test_suspend_resumes_even_when_update_fails(self):
        with mock.patch.object(t.nt, 'NtSuspendProcess', return_value=0), mock.patch.object(t.nt, 'NtResumeProcess', return_value=0) as resume:
            with self.assertRaises(ValueError):
                with t.suspended(123):
                    raise ValueError('simulated write failure')
            resume.assert_called_once_with(123)

    def test_failed_suspend_does_not_run_update(self):
        with mock.patch.object(t.nt, 'NtSuspendProcess', return_value=-1), mock.patch.object(t.nt, 'NtResumeProcess') as resume:
            with self.assertRaises(RuntimeError):
                with t.suspended(123):
                    self.fail('must not write without suspension')
            resume.assert_not_called()

if __name__ == '__main__':
    unittest.main()
