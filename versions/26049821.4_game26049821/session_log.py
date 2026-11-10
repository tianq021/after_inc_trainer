"""Per-launch local audit log and read-only game monitoring."""
import datetime
import functools
import json
import os
from pathlib import Path
import threading
import traceback
import uuid

CURRENT = None


def timestamp():
    return datetime.datetime.now().astimezone().isoformat(timespec='milliseconds')


def safe(value):
    if isinstance(value, bytes):
        return dict(length=len(value), hex=value[:64].hex(), truncated=len(value) > 64)
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value[:100]]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def emit(event, **data):
    if CURRENT:
        CURRENT.emit(event, **data)


def operation_dir(default):
    return CURRENT.folder / 'operations' if CURRENT else Path(default)


def audit(function):
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        if not CURRENT:
            return function(*args, **kwargs)
        ident = uuid.uuid4().hex[:12]
        values = args[1:] if args and hasattr(args[0], 'root') else args
        emit('operation_start', operation=function.__module__ + '.' + function.__qualname__,
             id=ident, args=values, kwargs=kwargs)
        try:
            result = function(*args, **kwargs)
        except BaseException as exc:
            emit('operation_error', id=ident, error=str(exc), traceback=traceback.format_exc())
            raise
        emit('operation_complete', id=ident, result=result)
        return result
    return wrapped


class Session:
    def __init__(self, root, version, player_log=None, interval=3):
        self.folder = Path(root) / (datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + f'_{os.getpid()}_' + uuid.uuid4().hex[:6])
        (self.folder / 'operations').mkdir(parents=True)
        self.player_log = Path(player_log) if player_log else Path.home() / 'AppData/LocalLow/Ndemic Creations/After Inc. Revival/Player.log'
        self.interval = interval
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.sequence = {}
        self.last_error = None
        self.offset = 0
        self.identity = None
        self.thread = None
        self.closed = False
        self.emit('session_start', version=version, trainer_pid=os.getpid(),
                  session=str(self.folder), game_app_id=3337140, supported_build=26049821)

    def append(self, name, data):
        # Lossless numbered chunks, 8 MiB each; no automatic deletion of history.
        with self.lock:
            index = self.sequence.get(name, 0)
            path = self.folder / f'{name}.{index:04d}.log'
            if path.exists() and path.stat().st_size + len(data) > 8 * 1024 * 1024:
                index += 1
                self.sequence[name] = index
                path = self.folder / f'{name}.{index:04d}.log'
            with path.open('ab') as stream:
                stream.write(data)

    def emit(self, event, **data):
        if self.closed:
            return
        try:
            row = dict(time=timestamp(), event=event, thread=threading.current_thread().name, **safe(data))
            self.append('events', (json.dumps(row, ensure_ascii=False) + '\n').encode('utf-8'))
        except OSError as exc:
            self.last_error = str(exc)

    def read_game_log(self):
        try:
            with self.player_log.open('rb') as source:
                stat = os.fstat(source.fileno())
                identity = (stat.st_ino, stat.st_ctime_ns)
                if self.identity is None:
                    # Record only the tail of existing history, then all new bytes.
                    self.offset = max(0, stat.st_size - 65536)
                    self.emit('game_log_initial_tail', offset=self.offset)
                elif identity != self.identity or stat.st_size < self.offset:
                    self.offset = 0
                    self.emit('game_log_rotated')
                self.identity = identity
                source.seek(self.offset)
                data = source.read(1024 * 1024)
                if data:
                    self.append('game_player', data)
                    self.offset += len(data)
                    self.emit('game_log_bytes', count=len(data), offset=self.offset)
        except FileNotFoundError:
            pass

    def poll(self):
        import psutil
        processes = []
        for process in psutil.process_iter(['pid', 'name', 'ppid', 'create_time']):
            name = (process.info['name'] or '').lower()
            if name not in ('after inc. revival.exe', 'afterincrevivaltrainer_cn.exe', 'unitycrashhandler64.exe') and process.pid != os.getpid():
                continue
            row = dict(process.info)
            try:
                row.update(cpu_seconds=sum(process.cpu_times()[:2]), rss=process.memory_info().rss,
                           status=process.status(), path=process.exe())
            except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                row['read_error'] = type(exc).__name__
            processes.append(row)
        self.emit('process_snapshot', processes=processes)
        self.read_game_log()

    def start(self):
        def monitor():
            while not self.stop_event.is_set():
                try:
                    self.poll()
                except Exception as exc:
                    self.emit('monitor_error', error=str(exc))
                self.stop_event.wait(self.interval)
        self.thread = threading.Thread(target=monitor, name='session-monitor', daemon=False)
        self.thread.start()

    def request_stop(self):
        self.stop_event.set()

    def finish(self):
        self.request_stop()
        if self.thread:
            self.thread.join()
        self.emit('session_end', reason='normal_close')
        self.closed = True
