from __future__ import annotations

import threading
import unittest
from unittest import mock

import trainer_gui


class TrainerConnectionTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(trainer_gui.game_build, 'verified', return_value={'root': 0x3D13B90})
        patcher.start()
        self.addCleanup(patcher.stop)

    def make_app(self) -> trainer_gui.TrainerApp:
        app = trainer_gui.TrainerApp.__new__(trainer_gui.TrainerApp)
        app.pid = 41
        app.candidate = {
            "settlement": "0x0000000000001000",
            "game_controller": "0x0000000000002000",
        }
        app.memory_lock = threading.RLock()
        app._post_status = mock.Mock()
        return app

    def test_same_process_uses_fast_rebind(self) -> None:
        app = self.make_app()
        refreshed = {
            "settlement": "0x0000000000003000",
            "game_controller": "0x0000000000002000",
            "productions": {},
        }
        app._locate_full_locked = mock.Mock()

        with (
            mock.patch.object(trainer_gui.memory_scan, "find_process", return_value=41),
            mock.patch.object(trainer_gui.memory_scan, "open_read_only", return_value=99),
            mock.patch.object(
                trainer_gui.memory_scan,
                "resolve_settlement_from_gameassembly",
                side_effect=RuntimeError("root is not ready"),
            ),
            mock.patch.object(
                trainer_gui.memory_scan,
                "refresh_settlement_candidate",
                return_value=refreshed,
            ),
            mock.patch.object(trainer_gui.memory_scan.kernel32, "CloseHandle"),
        ):
            mode = app._ensure_attached()

        self.assertEqual(mode, "rebound")
        self.assertIs(app.candidate, refreshed)
        app._locate_full_locked.assert_not_called()

    def test_stable_gameassembly_root_rebinds_without_scan(self) -> None:
        app = self.make_app()
        refreshed = {
            "settlement": "0x0000000000009000",
            "game_controller": "0x000000000000A000",
            "gameassembly_base": "0x0000000180000000",
            "productions": {},
        }
        app._locate_full_locked = mock.Mock()

        with (
            mock.patch.object(trainer_gui.memory_scan, "find_process", return_value=41),
            mock.patch.object(trainer_gui.memory_scan, "open_read_only", return_value=99),
            mock.patch.object(
                trainer_gui.memory_scan,
                "resolve_settlement_from_gameassembly",
                return_value=refreshed,
            ),
            mock.patch.object(
                trainer_gui.memory_scan, "refresh_settlement_candidate"
            ) as fast_rebind,
            mock.patch.object(trainer_gui.memory_scan.kernel32, "CloseHandle"),
        ):
            mode = app._ensure_attached()

        self.assertEqual(mode, "rebound")
        self.assertIs(app.candidate, refreshed)
        fast_rebind.assert_not_called()
        app._locate_full_locked.assert_not_called()

    def test_restart_uses_stable_root_without_full_locator(self) -> None:
        app = self.make_app()
        refreshed = {
            "settlement": "0x000000000000B000",
            "game_controller": "0x000000000000C000",
            "gameassembly_base": "0x0000000180000000",
            "productions": {},
        }
        app._locate_full_locked = mock.Mock()

        with (
            mock.patch.object(trainer_gui.memory_scan, "find_process", return_value=84),
            mock.patch.object(trainer_gui.memory_scan, "open_read_only", return_value=99),
            mock.patch.object(
                trainer_gui.memory_scan,
                "resolve_settlement_from_gameassembly",
                return_value=refreshed,
            ),
            mock.patch.object(trainer_gui.memory_scan.kernel32, "CloseHandle"),
        ):
            mode = app._ensure_attached()

        self.assertEqual(mode, "rooted")
        self.assertEqual(app.pid, 84)
        self.assertIs(app.candidate, refreshed)
        app._locate_full_locked.assert_not_called()

    def test_scene_loading_waits_without_automatic_full_scan(self) -> None:
        app = self.make_app()
        original_candidate = app.candidate
        app._locate_full_locked = mock.Mock()

        with (
            mock.patch.object(trainer_gui.memory_scan, "find_process", return_value=41),
            mock.patch.object(trainer_gui.memory_scan, "open_read_only", return_value=99),
            mock.patch.object(
                trainer_gui.memory_scan,
                "resolve_settlement_from_gameassembly",
                side_effect=RuntimeError("scenario launcher is not ready"),
            ),
            mock.patch.object(
                trainer_gui.memory_scan,
                "refresh_settlement_candidate",
                side_effect=RuntimeError("old controller destroyed"),
            ),
            mock.patch.object(trainer_gui.memory_scan.kernel32, "CloseHandle"),
        ):
            with self.assertRaisesRegex(
                trainer_gui.TrainerTransientError, "等待稳定根指针"
            ):
                app._ensure_attached()

        self.assertIs(app.candidate, original_candidate)
        app._locate_full_locked.assert_not_called()

    def test_forced_scan_still_uses_full_locator(self) -> None:
        app = self.make_app()

        def install_new_binding(expected_pid: int) -> None:
            app.pid = expected_pid
            app.candidate = {"settlement": "0x5000", "productions": {}}

        app._locate_full_locked = mock.Mock(side_effect=install_new_binding)
        with mock.patch.object(trainer_gui.memory_scan, "find_process", return_value=84):
            mode = app._ensure_attached(force_scan=True)

        self.assertEqual(mode, "scanned")
        self.assertEqual(app.pid, 84)
        app._locate_full_locked.assert_called_once_with(84)


if __name__ == "__main__":
    unittest.main()
