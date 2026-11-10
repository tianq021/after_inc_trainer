import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import session_log as logs
from trainer_gui import TrainerApp


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.game = self.root / 'Player.log'
        self.game.write_bytes(b'initial\n')
        self.session = logs.Session(self.root / 'logs', 'test', self.game, .01)
        self.patch = patch.object(logs, 'CURRENT', self.session)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.addCleanup(self.session.finish)

    def events(self):
        return [json.loads(line) for f in sorted(self.session.folder.glob('events.*.log'))
                for line in f.read_text(encoding='utf-8').splitlines()]

    def test_each_launch_has_its_own_folder(self):
        other = logs.Session(self.root / 'logs', 'test', self.game)
        self.assertNotEqual(other.folder, self.session.folder)
        other.finish()

    def test_actions_and_errors_are_correlated(self):
        @logs.audit
        def change(value):
            if value < 0:
                raise ValueError('invalid target')
            return dict(before=0, after=value)
        self.assertEqual(change(8)['after'], 8)
        with self.assertRaises(ValueError):
            change(-1)
        rows = self.events()[1:]
        self.assertEqual([r['event'] for r in rows],
                         ['operation_start', 'operation_complete', 'operation_start', 'operation_error'])
        self.assertEqual(rows[0]['id'], rows[1]['id'])
        self.assertEqual(rows[2]['id'], rows[3]['id'])

    def test_incremental_game_log_and_truncation(self):
        self.session.read_game_log()
        with self.game.open('ab') as f:
            f.write(b'new error\n')
        self.session.read_game_log()
        self.session.read_game_log()
        self.game.write_bytes(b'new session\n')
        self.session.read_game_log()
        self.assertEqual((self.session.folder / 'game_player.0000.log').read_bytes(),
                         b'initial\nnew error\nnew session\n')
        self.assertIn('game_log_rotated', [r['event'] for r in self.events()])

    def test_monitor_stops_and_writes_end(self):
        polled = threading.Event()
        with patch.object(self.session, 'poll', side_effect=polled.set):
            self.session.start()
            self.assertTrue(polled.wait(2))
            self.session.finish()
        self.assertFalse(self.session.thread.is_alive())
        self.assertEqual(self.events()[-1]['event'], 'session_end')

    def test_log_disk_error_does_not_mask_game_operation(self):
        @logs.audit
        def action():
            return 42
        with patch.object(self.session, 'append', side_effect=OSError('disk full')):
            self.assertEqual(action(), 42)
        self.assertEqual(self.session.last_error, 'disk full')

    def test_close_waits_for_worker_finally_and_rejects_new_work(self):
        class Var:
            def set(self, value):
                self.value = value
        class Root:
            destroyed = False
            def after(self, delay, callback):
                self.callback = callback
            def destroy(self):
                self.destroyed = True
        app = TrainerApp.__new__(TrainerApp)
        app.root = Root()
        app._closing = False
        app._workers = set()
        app.freeze_vars = {}
        app.team_keep_var = Var()
        app.fast_move_var = Var()
        app.status_var = Var()
        release = threading.Event()
        resumed = threading.Event()
        def worker():
            try:
                release.wait(2)
            finally:
                resumed.set()
        app._start_worker(worker)
        app._on_close()
        self.assertFalse(app.root.destroyed)
        new_work = threading.Event()
        app._start_worker(new_work.set)
        release.set()
        for thread in app._workers:
            thread.join(2)
        app._finish_close()
        self.assertTrue(resumed.is_set())
        self.assertTrue(app.root.destroyed)
        self.assertFalse(new_work.is_set())
