"""Native coverage for the build-26049821 soldier upgrade request.

native_upgrade_test.cpp builds a fake Il2Cpp object graph and reroutes every game
address in soldier_upgrade.cpp through testResolve(), so these cases run the real
native dispatch, guards and rejection codes without the game. Build it first:

    native\\build_native_test.cmd
"""
import ctypes
import struct
import unittest
from pathlib import Path

import soldier_upgrade as s

DLL_NAME = 'AfterIncSoldierUpgradeTest.dll'
DLL_PATH = Path(__file__).resolve().parent.parent / 'native' / DLL_NAME
SCENE = struct.Struct('<5Q')
CALLS = struct.Struct('<5i')
DIAG = struct.Struct('<12i5Q')
DIAG_FIELDS = ('hook_calls runs_started identity_fails stage event_found engaged_before '
               'has_upgrades_left opt_has_value opt_is_object created_count last_status '
               'reserved last_manager last_game last_global opt_value opt_object_value').split()
STAGES = {'events': 1, 'blocked': 2, 'list': 3, 'notfound': 4, 'ambiguous': 5,
          'engaged': 6, 'pending': 7, 'empty': 8, 'count': 9, 'ok': 10, 'left': 11}

# scenario -> (action, expected status, expected stage)
SCENARIOS = {
    0: (1, 3, 'ok'),
    1: (1, -7, 'events'),
    2: (1, -7, 'blocked'),
    3: (1, -7, 'notfound'),
    4: (1, -6, 'pending'),
    5: (1, -5, 'left'),
    6: (1, 3, 'ok'),
    7: (1, -8, 'count'),
    8: (1, -1, None),
    9: (1, -2, None),
    10: (1, -3, None),
    11: (1, -3, None),
    12: (2, -4, None),
    13: (1, -7, 'list'),
    14: (1, -7, 'events'),
    15: (3, -4, None),
    16: (1, -8, 'empty'),
    17: (1, -5, 'left'),
}


class NativeUpgradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DLL_PATH.is_file():
            raise unittest.SkipTest(f'{DLL_NAME} 未构建，请先运行 native\\build_native_test.cmd')
        cls.dll = ctypes.WinDLL(str(DLL_PATH))
        cls.dll.PrepareScene.argtypes = [ctypes.c_int]
        cls.dll.PrepareScene.restype = None
        cls.dll.HarvestCalls.argtypes = []
        cls.dll.HarvestCalls.restype = None
        cls.dll.SoldierSimulate.argtypes = [ctypes.c_void_p] * 4
        cls.dll.SoldierSimulate.restype = None
        cls.state = (ctypes.c_char * s.STATE.size).in_dll(cls.dll, 'SoldierState')
        cls.scene = (ctypes.c_char * SCENE.size).in_dll(cls.dll, 'TestScene')
        cls.calls = (ctypes.c_char * CALLS.size).in_dll(cls.dll, 'TestCalls')
        cls.diag = (ctypes.c_char * DIAG.size).in_dll(cls.dll, 'SoldierDiag')

    def dispatch(self, scenario, action, status=1):
        """Seed the request, run the real native entry point, read the outcome."""
        self.dll.PrepareScene(scenario)
        manager, game, glob, soldier, design = SCENE.unpack(bytes(self.scene))
        ctypes.memmove(self.state, s.STATE.pack(
            s.MAGIC, 0, manager, game, glob, soldier, design, status, action, 0.0, 0.0),
            s.STATE.size)
        self.dll.SoldierSimulate(manager, game, glob, None)
        self.dll.HarvestCalls()
        report = dict(zip(DIAG_FIELDS, DIAG.unpack(bytes(self.diag))))
        return s.decode(bytes(self.state)), CALLS.unpack(bytes(self.calls)), report

    def test_status_and_stage_for_every_scenario(self):
        for scenario, (action, expected, stage) in SCENARIOS.items():
            with self.subTest(scenario=scenario):
                state, _, report = self.dispatch(scenario, action)
                self.assertEqual(state['status'], expected)
                if stage is not None:
                    self.assertEqual(report['stage'], STAGES[stage])

    def test_upgrade_request_reaches_the_native_event_once(self):
        _, calls, report = self.dispatch(0, 1)
        self.assertEqual(calls[1], 1)   # native event invoked
        self.assertEqual(calls[2], 1)   # original simulate still runs first
        self.assertEqual(report['event_found'], 1)
        self.assertEqual(report['engaged_before'], 0)
        self.assertEqual(report['opt_has_value'], 1)
        self.assertEqual(report['created_count'], 1)
        self.assertEqual(report['has_upgrades_left'], 1)
        self.assertEqual(report['last_status'], 3)

    def test_pending_upgrade_never_reaches_the_native_event(self):
        _, calls, report = self.dispatch(4, 1)
        self.assertEqual(calls[1], 0)
        self.assertEqual(calls[0], 0)
        self.assertEqual(report['engaged_before'], 1)

    def test_exhausted_rewards_never_reach_the_native_event(self):
        _, calls, report = self.dispatch(17, 1)
        self.assertEqual(calls[1], 0)              # never fired
        self.assertEqual(calls[0], 1)              # the option table was consulted
        self.assertEqual(report['has_upgrades_left'], 0)
        self.assertEqual(report['created_count'], -1)

    def test_optional_payload_is_used_even_without_has_value(self):
        # An empty hasValue flag must not hide a structurally valid cluster.
        _, _, report = self.dispatch(6, 1)
        self.assertEqual(report['opt_has_value'], 0)
        self.assertEqual(report['created_count'], 1)

    def test_weapon_and_squad_still_apply_to_the_selected_soldier(self):
        state, calls, _ = self.dispatch(0, 2)
        self.assertEqual(calls[3], 1)
        self.assertEqual(state['before'], 1.0)
        self.assertEqual(state['after'], 1.25)
        state, calls, _ = self.dispatch(0, 3)
        self.assertEqual(calls[4], 1)
        self.assertEqual(state['before'], 1.0)
        self.assertEqual(state['after'], 1.25)

    def test_out_of_range_action_is_refused(self):
        state, calls, _ = self.dispatch(0, 4)
        self.assertEqual(state['status'], -4)
        self.assertEqual(calls[1], 0)

    def test_idle_state_does_not_dispatch(self):
        state, calls, _ = self.dispatch(0, 1, status=0)
        self.assertEqual(state['status'], 0)
        self.assertEqual(calls[0], 0)
        self.assertEqual(calls[1], 0)
        self.assertEqual(calls[2], 1)

    def test_running_state_is_left_alone(self):
        state, _, _ = self.dispatch(0, 1, status=2)
        self.assertEqual(state['status'], 2)

    def test_hook_calls_are_counted(self):
        before = dict(zip(DIAG_FIELDS, DIAG.unpack(bytes(self.diag))))['hook_calls']
        self.dispatch(0, 1)
        after = dict(zip(DIAG_FIELDS, DIAG.unpack(bytes(self.diag))))['hook_calls']
        self.assertEqual(after, before + 1)

    def test_every_rejection_code_has_a_chinese_message(self):
        source = (Path(s.__file__).resolve().parent / 'trainer_gui.py').read_text(encoding='utf-8')
        for code in range(-9, 0):
            with self.subTest(code=code):
                self.assertRegex(source, rf'{code}:\s*[\'"]\S')


if __name__ == '__main__':
    unittest.main()
