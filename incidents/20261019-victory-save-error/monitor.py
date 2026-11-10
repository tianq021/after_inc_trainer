"""Thirty-minute read-only desktop process/log monitor. Stop with STOP file."""
import datetime
import json
from pathlib import Path
import time
import psutil

OUT = Path(__file__).resolve().parent
LOG = Path.home() / 'AppData/LocalLow/Ndemic Creations/After Inc. Revival/Player.log'
def now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
def emit(value):
    with (OUT / 'monitor.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(dict(time=now(), **value), ensure_ascii=False) + '\n')

offset = 0
identity = None
emit(dict(event='started', monitor_pid=__import__('os').getpid(), duration_minutes=30))
until = time.monotonic() + 1800
while time.monotonic() < until and not (OUT / 'STOP').exists():
    found = []
    for p in psutil.process_iter(['pid', 'name', 'ppid', 'create_time']):
        if not any(n in (p.info['name'] or '').lower() for n in ('after inc', 'afterincrevivaltrainer', 'unitycrashhandler')):
            continue
        row = dict(p.info)
        try:
            row.update(cpu=p.cpu_times().user + p.cpu_times().system,
                       rss=p.memory_info().rss, exe=p.exe())
        except (psutil.AccessDenied, psutil.NoSuchProcess) as e:
            row['inspection_error'] = type(e).__name__
        found.append(row)
    emit(dict(event='processes', processes=found))
    try:
        with LOG.open('rb') as f:
            st = LOG.stat()
            current = (st.st_ino, st.st_ctime_ns)
            if identity != current or st.st_size < offset:
                offset = 0
                identity = current
                emit(dict(event='log_open_or_rotation'))
            f.seek(offset)
            data = f.read()
            offset = f.tell()
        if data:
            with (OUT / 'live_player.log').open('ab') as f:
                f.write(data)
            emit(dict(event='log_growth', bytes=len(data), offset=offset))
    except OSError as e:
        emit(dict(event='log_error', error=str(e)))
    time.sleep(2)
emit(dict(event='stopped'))
