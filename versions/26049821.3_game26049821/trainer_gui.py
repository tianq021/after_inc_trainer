#!/usr/bin/env python3
"""Small Chinese GUI trainer for After Inc: Revival, Steam build 24931318."""

from __future__ import annotations
import session_log

import sys
import contextlib
import io
import json
import math
import os
from pathlib import Path
import struct
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import memory_scan
import expedition
import game_build
import task_extension
import teams
import soldier_upgrade


PROCESS_NAME = "After Inc. Revival.exe"
SUPPORTED_BUILD = "24931318 / 25479909 / 25936576 / 26049821"
TRAINER_VERSION = "26049821.3"
APP_DATA = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "AfterIncTrainer"
STRUCTURE_REPORT = APP_DATA / "last_structure.json"
LOG_DIR = APP_DATA / "logs"
AUTO_CHECK_MS = 500

RESOURCE_ROWS = (
    ("manpower", "人力", "100"),
    ("food", "食物", "7"),
    ("water", "水", "7"),
    ("wood", "木材", "8"),
    ("fuel", "燃料", "8"),
    ("authority", "权威", "100"),
    ("patience", "目标耐心", "365"),
)

FOOD_PARTS = ("forage", "grain", "fruit", "vegetable", "deer", "sheep", "cow")
FUEL_PARTS = ("firewood", "coal")
AUTHORITY_SOURCE_OFFSETS = tuple(range(0x298, 0x2F0, 8))


class TrainerError(RuntimeError):
    pass


class TrainerTransientError(TrainerError):
    """Temporary game/loading state that should be retried automatically."""


class TrainerApp:
    def __init__(self, root: tk.Tk) -> None:
        self._closing = False
        self._workers = set()
        self.root = root
        self.root.title(f"After Inc: Revival 修改器 {TRAINER_VERSION}")
        self.root.geometry("600x540")
        self.root.minsize(600, 540)

        self.pid: int | None = None
        self.candidate: dict | None = None
        self.scanning = False
        self.connection_worker_running = False
        self.lock_worker_running = False
        self.memory_lock = threading.RLock()

        self.status_var = tk.StringVar(value="尚未连接游戏")
        self.current_vars = {key: tk.StringVar(value="—") for key, _, _ in RESOURCE_ROWS}
        self.target_vars = {key: tk.StringVar(value=default) for key, _, default in RESOURCE_ROWS}
        self.freeze_vars = {key: tk.BooleanVar(value=False) for key, _, _ in RESOURCE_ROWS}
        self.fast_move_var = tk.BooleanVar(value=False)
        self.fast_move_status_var = tk.StringVar(value="未启用")
        self.expedition_status_var = tk.StringVar(value="选关界面可用")
        self.expedition_busy = False
        self.tasks_busy = False
        self.teams_busy = False
        self.team_targets = {}
        self.team_keep_var = tk.BooleanVar(value=True)
        self.team_restore_busy = False
        self.soldier_busy = False
        self.soldier_options = []
        self.soldier_status_var = tk.StringVar(value='升级机会：在所选战士区域生成图标，点击后选择全局战士加成')
        self.teams_status_var = tk.StringVar(value="进入关卡后读取队伍总数")
        self.tasks_count_var = tk.StringVar(value="1")
        self.tasks_status_var = tk.StringVar(value="最多 5 个；添加后切换赛季或重进地图")

        self.root.protocol('WM_DELETE_WINDOW', self._on_close)
        self._build_ui()
        for key, variable in dict(self.freeze_vars, fast_move=self.fast_move_var, team_keep=self.team_keep_var).items():
            variable.trace_add('write', lambda *_args, k=key, v=variable: session_log.emit('toggle', key=k, enabled=v.get()))
        self._log_health_tick()
        self.root.after(800, self._lock_tick)
        self.root.after(350, self._connection_tick)
        self.root.after(1500, self._team_restore_tick)

    def _start_worker(self, task):
        if getattr(self, '_closing', False):
            return
        if not hasattr(self, '_workers'):
            self._workers = set()
        self._workers = {t for t in self._workers if t.is_alive()}
        def run():
            try:
                task()
            except BaseException as exc:
                session_log.emit('worker_error', error=str(exc))
                raise
        thread = threading.Thread(target=run, daemon=False)
        self._workers.add(thread)
        thread.start()

    def _log_health_tick(self):
        if self._closing:
            return
        logger = session_log.CURRENT
        if logger and logger.last_error:
            self.status_var.set('日志写入失败：' + logger.last_error)
        self.root.after(2000, self._log_health_tick)

    def _on_close(self):
        if self._closing:
            return
        self._closing = True
        session_log.emit('close_requested', active_workers=sum(t.is_alive() for t in self._workers))
        self.stop_all_locks()
        self.fast_move_var.set(False)
        if session_log.CURRENT:
            session_log.CURRENT.request_stop()
        self._finish_close()

    def _finish_close(self):
        # Keep Tk dispatching while existing workers finish their callbacks and
        # NtResumeProcess finally blocks. Never join a Tk-calling worker here.
        logger = session_log.CURRENT
        if any(t.is_alive() for t in self._workers) or (logger and logger.thread and logger.thread.is_alive()):
            self.status_var.set('正在关闭：等待当前操作完成并恢复游戏运行……')
            self.root.after(100, self._finish_close)
            return
        session_log.emit('workers_finished')
        self.root.destroy()

    def _build_ui(self) -> None:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")

        outer = ttk.Frame(self.root, padding=6)
        outer.pack(fill="both", expand=True)

        heading = ttk.Frame(outer)
        heading.pack(fill="x", pady=(0, 4))
        ttk.Label(heading, text="After Inc: Revival", font=("Microsoft YaHei UI", 11, "bold")).pack(side="left")
        ttk.Button(heading, text="使用说明", command=self.show_instructions).pack(side="right")

        connection = ttk.Frame(outer)
        connection.pack(fill="x")
        top_line = ttk.Frame(connection)
        top_line.pack(fill="x")
        self.scan_button = ttk.Button(top_line, text="完整扫描", command=self.start_scan)
        self.scan_button.pack(side="left")
        ttk.Button(top_line, text="刷新数值", command=self.start_refresh).pack(side="left", padx=5)
        ttk.Label(connection, textvariable=self.status_var, wraplength=530).pack(anchor="w", pady=(2, 0))
        self.progress = ttk.Progressbar(top_line, mode="indeterminate", length=80)
        self.progress.pack(side="right")

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True, pady=5)
        resources_tab = ttk.Frame(notebook, padding=4)
        teams_tab = ttk.Frame(notebook, padding=4)
        map_tab = ttk.Frame(notebook, padding=4)
        notebook.add(resources_tab, text="资源")
        notebook.add(teams_tab, text="队伍与升级")
        notebook.add(map_tab, text="远征与地图")
        ttk.Label(resources_tab, text="设置目标值；勾选锁定后持续补回。启动不会自动修改资源。").pack(anchor="w")
        values = ttk.LabelFrame(resources_tab, text="资源", padding=4)
        values.pack(fill="x", pady=3)
        headers = ("项目", "当前值", "目标值", "操作", "锁定")
        for column, header in enumerate(headers):
            ttk.Label(values, text=header, font=("Microsoft YaHei UI", 9, "bold")).grid(
                row=0, column=column, padx=5, pady=(0, 4), sticky="w"
            )
        values.columnconfigure(1, weight=1)
        values.columnconfigure(2, weight=1)

        for row_index, (key, label, _) in enumerate(RESOURCE_ROWS, start=1):
            ttk.Label(values, text=label).grid(row=row_index, column=0, padx=5, pady=2, sticky="w")
            ttk.Label(values, textvariable=self.current_vars[key]).grid(
                row=row_index, column=1, padx=5, pady=2, sticky="w"
            )
            ttk.Entry(values, textvariable=self.target_vars[key], width=12).grid(
                row=row_index, column=2, padx=5, pady=2, sticky="ew"
            )
            ttk.Button(
                values,
                text="设置",
                command=lambda selected=key: self.start_set_one(selected),
                width=7,
            ).grid(row=row_index, column=3, padx=5, pady=2)
            ttk.Checkbutton(values, variable=self.freeze_vars[key]).grid(
                row=row_index, column=4, padx=12, pady=2
            )

        team_frame = ttk.LabelFrame(teams_tab, text="队伍与战士", padding=4)
        team_frame.pack(fill="x", pady=(0, 3))
        team_buttons = ttk.Frame(team_frame)
        team_buttons.pack(fill="x")
        self.teams_buttons = []
        for label, kind in (("读取队伍", None), ("探索 +1", "explore"), ("建设 +1", "build")):
            button = ttk.Button(team_buttons, text=label, width=9, command=lambda k=kind: self.start_teams(k))
            button.pack(side="left", padx=(0, 4))
            self.teams_buttons.append(button)
        team_status = ttk.Frame(team_frame)
        team_status.pack(fill="x", pady=(2, 0))
        ttk.Label(team_status, textvariable=self.teams_status_var, wraplength=360).pack(side="left")
        ttk.Checkbutton(
            team_buttons,
            text="战士快移",
            variable=self.fast_move_var,
            command=self._fast_move_toggled,
        ).pack(side="right")
        ttk.Label(team_status, textvariable=self.fast_move_status_var).pack(side="right")
        ttk.Checkbutton(team_frame, text='保持本次设置的队伍数量（读档/切关后自动补回）',
                        variable=self.team_keep_var).pack(anchor='w')

        soldiers = ttk.LabelFrame(teams_tab, text='战士升级', padding=4)
        soldiers.pack(fill='x', pady=(0,3))
        self.soldier_picker = ttk.Combobox(soldiers, state='readonly', width=65)
        self.soldier_picker.pack(fill='x')
        soldier_row = ttk.Frame(soldiers)
        soldier_row.pack(fill='x', pady=3)
        self.soldier_buttons = []
        for label, action in [('读取战士','read'),('升级机会 +1','upgrade'),
                              ('武器 +0.25','weapon'),('小队 +0.25','squad'),('取消等待','cancel')]:
            button=ttk.Button(soldier_row,text=label,width=12,command=lambda a=action:self.start_soldier(a))
            button.pack(side='left',padx=(0,3))
            self.soldier_buttons.append(button)
        ttk.Label(soldiers,textvariable=self.soldier_status_var,wraplength=570).pack(anchor='w')
        ttk.Label(soldiers,text='升级机会由游戏提供选择；武器/小队直接增加所选战士属性。\n点完必须切回游戏窗口并让时间前进一下（窗口失焦时游戏会暂停，请求会一直等待）。\n已有升级图标时不会重复生成。',wraplength=550).pack(anchor='w',pady=4)

        expeditions = ttk.LabelFrame(map_tab, text="远征与随机任务", padding=4)
        expeditions.pack(fill="x", pady=(0, 3))
        expedition_buttons = ttk.Frame(expeditions)
        expedition_buttons.pack(fill="x")
        self.expedition_buttons = []
        for label, action in (("读取远征", "read"), ("刷新（+1天）", "advance"),
                              ("恢复日期", "reset")):
            button = ttk.Button(expedition_buttons, text=label,
                                command=lambda a=action: self.start_expedition(a))
            button.pack(side="left", padx=(0, 8))
            self.expedition_buttons.append(button)
        ttk.Label(expeditions, textvariable=self.expedition_status_var,
                  wraplength=520).pack(anchor="w", pady=(2, 0))

        tasks = ttk.Frame(expeditions)
        tasks.pack(fill="x", pady=(4, 0))
        row = ttk.Frame(tasks)
        row.pack(fill="x")
        ttk.Label(row, text="随机任务").pack(side="left")
        ttk.Spinbox(row, from_=1, to=5, textvariable=self.tasks_count_var, width=4).pack(side="left", padx=6)
        self.tasks_buttons = []
        for label, action in (("添加", "add"), ("读取", "read"), ("清除添加", "clear")):
            button = ttk.Button(row, text=label, width=9, command=lambda a=action: self.start_tasks(a))
            button.pack(side="left", padx=(0, 6))
            self.tasks_buttons.append(button)
        ttk.Label(tasks, textvariable=self.tasks_status_var, wraplength=520).pack(anchor="w", pady=(2, 0))
        ttk.Label(tasks, text="退出游戏失效；清除不撤销奖励。详情见使用说明。", wraplength=520).pack(anchor="w")

        actions = ttk.Frame(outer)
        actions.pack(fill="x")
        ttk.Button(actions, text="全部设置", command=self.start_set_all).pack(side="left")
        ttk.Button(actions, text="停止锁定", command=self.stop_all_locks).pack(
            side="left", padx=8
        )
        ttk.Button(actions, text="日志", command=self.open_log_directory).pack(side="right")

    def show_instructions(self) -> None:
        messagebox.showinfo(
            "介绍与使用说明",
            f"After Inc: Revival 修改器 {TRAINER_VERSION}\nSteam App ID 3337140；基础功能适用构建 {SUPPORTED_BUILD}。\n\n"
            "战士升级（仅构建 26049821）\n读取并选择战士，点击升级机会 +1，在该区域生成原生升级图标。"
            "点击游戏图标选择全局战士加成；不会直接给单个战士加经验或替你选择。已有待处理升级或奖励耗尽时拒绝重复添加。"
            "武器和小队按钮只修改所选战士。暂停时请短暂继续游戏，再读取结果。\n\n"
            "连接与资源\n进入关卡后自动连接，读档或切关后自动重新定位。完整扫描仅用于手动诊断。"
            "输入目标值后点击设置；持续锁定可自动补回消耗。暂停时界面可能需要短暂推进才显示新值。\n\n"
            "战士快速移动\n将玩家战士的剩余路程缩短到 1 回合，下一次推进正常触发到达。\n\n"
            "探索与建设队伍\n支持 25479909 / 25936576 / 26049821。读取当前关卡队伍总数；每次点击 +1 增加一队，最多 20 队。"
            "暂停时可短暂继续游戏刷新界面；切关后请重新读取，存档保留情况尚未验证。\n\n"
            "远征任务\n在选关界面点击读取状态，然后点击刷新任务，每次推进虚拟日期 1 天。"
            "操作后返回世界地图并重新进入选关，必要时切换赛季。恢复真实日期将偏移归零，"
            "不会撤销已完成的任务或奖励，也不修改电脑系统时间。\n\n"
            "添加随机任务（实验）\n支持构建 25479909 / 25936576 / 26049821。输入数量后点击添加，再切换赛季或重新进入地图。"
            "不推进日期；每次游戏运行最多保留 5 个新增任务。首次添加自动备份本地存档。"
            "清除后需再次刷新地图，且不撤销已完成的记录或奖励。\n\n"
            "连接权限与日志\n权限不足时以与游戏相同的权限运行修改器。操作记录可通过打开日志目录查看。",
            parent=self.root,
        )

    def _set_status(self, text: str) -> None:
        session_log.emit('ui_status', message=text)
        self.status_var.set(text)

    def _post_status(self, text: str) -> None:
        """Update Tk state safely from a background worker."""
        self.root.after(0, lambda value=text: self._set_status(value))

    def _clear_binding(self) -> None:
        self.pid = None
        self.candidate = None

    def _run_background(self, task, success_message: str | None = None) -> None:
        def worker():
            try:
                result = task()
                self.root.after(0, lambda: self._background_success(result, success_message))
            except Exception as exc:  # UI boundary: show a concise actionable error.
                self.root.after(0, lambda error=exc: self._background_error(error))

        self._start_worker(worker)

    def _background_success(self, result, success_message: str | None) -> None:
        if isinstance(result, dict):
            self._apply_current_values(result)
        if success_message:
            self._set_status(success_message)

    def _background_error(self, error: Exception) -> None:
        self._set_status(f"失败：{error}")
        messagebox.showerror("操作失败", str(error), parent=self.root)

    def _locate_full_locked(self, expected_pid: int) -> None:
        """Run the read-only structural locator and atomically install its result."""
        self._post_status("正在自动定位当前关卡，通常需要约30秒……")
        APP_DATA.mkdir(parents=True, exist_ok=True)
        args = type(
            "LocateArgs",
            (),
            {"process": PROCESS_NAME, "output": str(STRUCTURE_REPORT)},
        )()
        captured = io.StringIO()
        try:
            with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
                memory_scan.locate_settlement(args)
        except (OSError, RuntimeError) as exc:
            self._clear_binding()
            if "requires numpy" in str(exc):
                raise TrainerError("修改器缺少结构扫描组件 numpy") from exc
            raise TrainerTransientError("游戏正在退出或切换关卡，将自动重试") from exc
        report = json.loads(STRUCTURE_REPORT.read_text(encoding="utf-8"))
        if report.get("candidate_count") != 1:
            self._clear_binding()
            raise TrainerTransientError(
                f"当前关卡仍在加载，活动结构候选数为 {report.get('candidate_count')}"
            )
        report_pid = int(report["pid"])
        try:
            current_pid = memory_scan.find_process(PROCESS_NAME)
        except RuntimeError as exc:
            self._clear_binding()
            raise TrainerTransientError("游戏进程已关闭，等待重新启动") from exc
        if report_pid != expected_pid or current_pid != expected_pid:
            self._clear_binding()
            raise TrainerTransientError("定位期间游戏进程发生变化，将自动重试")
        self.pid = report_pid
        self.candidate = report["candidates"][0]

    def _ensure_attached(self, force_scan: bool = False) -> str:
        """Validate the active world and automatically repair a stale binding.

        Callers hold ``memory_lock`` so a read/write cannot overlap a rebind.
        Returns validated, rooted, rebound, or scanned for UI reporting.
        """
        try:
            current_pid = memory_scan.find_process(PROCESS_NAME)
        except RuntimeError as exc:
            self._clear_binding()
            raise TrainerTransientError("等待游戏启动……") from exc

        profile = game_build.verified(current_pid)

        if not force_scan:
            old_settlement = (
                self.candidate.get("settlement")
                if self.pid == current_pid and self.candidate is not None
                else None
            )
            cached_base = None
            if self.pid == current_pid and self.candidate is not None:
                base_text = self.candidate.get("gameassembly_base")
                if base_text:
                    try:
                        cached_base = int(base_text, 0)
                    except (TypeError, ValueError):
                        cached_base = None

            handle = memory_scan.open_read_only(current_pid)
            try:
                rooted = memory_scan.resolve_settlement_from_gameassembly(
                    handle, current_pid, cached_base, type_info_rva=profile['root']
                )
            except Exception:
                rooted = None
            finally:
                memory_scan.kernel32.CloseHandle(handle)
            if rooted is not None:
                self.pid = current_pid
                self.candidate = rooted
                if old_settlement is None:
                    return "rooted"
                return "rebound" if rooted.get("settlement") != old_settlement else "validated"

            # During setup the persistent launch handler may still be null or
            # may reference the just-destroyed GameController.  If the old
            # controller remains valid, its short pointer chain is still a safe
            # secondary path until SetUpGame publishes the new controller.
            if self.pid == current_pid and self.candidate is not None:
                handle = memory_scan.open_read_only(current_pid)
                try:
                    refreshed = memory_scan.refresh_settlement_candidate(
                        handle, self.candidate
                    )
                except Exception:
                    refreshed = None
                finally:
                    memory_scan.kernel32.CloseHandle(handle)
                if refreshed is not None:
                    self.candidate = refreshed
                    return (
                        "rebound"
                        if refreshed.get("settlement") != old_settlement
                        else "validated"
                    )

            # A full private-memory scan is deliberately not automatic any
            # more.  The native singleton is updated by SetUpGame, so polling
            # it is both faster and safer while a scene is loading.  The user
            # can still request the full diagnostic locator with the button.
            if self.pid != current_pid:
                self.candidate = None
            self.pid = current_pid
            self._post_status("等待当前关卡完成初始化，稳定根指针会自动更新……")
            raise TrainerTransientError("关卡加载中，等待稳定根指针")

        self._clear_binding()
        self._locate_full_locked(current_pid)
        return "scanned"

    def start_scan(self) -> None:
        if self.scanning or self.connection_worker_running:
            self._set_status("自动连接任务正在运行，请稍候……")
            return
        self.scanning = True
        self.connection_worker_running = True
        self.scan_button.configure(state="disabled")
        self.progress.start(12)
        self._set_status("正在强制重新定位当前关卡……")

        def task():
            with self.memory_lock:
                self._ensure_attached(force_scan=True)
                return self._read_current_values_locked()

        def worker():
            try:
                result = task()
                self.root.after(0, lambda: self._scan_finished(result, None))
            except Exception as exc:
                self.root.after(0, lambda error=exc: self._scan_finished(None, error))

        self._start_worker(worker)

    def _scan_finished(self, result: dict | None, error: Exception | None) -> None:
        self.scanning = False
        self.connection_worker_running = False
        self.scan_button.configure(state="normal")
        self.progress.stop()
        if error is not None:
            self._background_error(error)
            return
        self._apply_current_values(result or {})
        self._set_status(f"已连接 PID {self.pid}，结构验证通过")

    def _connection_tick(self) -> None:
        if getattr(self, '_closing', False):
            return
        """Continuously validate/rebind without showing transient error popups."""
        if not self.connection_worker_running and not self.scanning:
            self.connection_worker_running = True

            def worker():
                try:
                    with self.memory_lock:
                        mode = self._ensure_attached()
                        values = self._read_current_values_locked()
                    self.root.after(
                        0, lambda current=values, result_mode=mode:
                        self._auto_connection_finished(current, result_mode, None)
                    )
                except Exception as exc:
                    self.root.after(
                        0, lambda error=exc: self._auto_connection_finished(None, None, error)
                    )

            self._start_worker(worker)
        self.root.after(AUTO_CHECK_MS, self._connection_tick)

    def _auto_connection_finished(
        self, values: dict | None, mode: str | None, error: Exception | None
    ) -> None:
        self.connection_worker_running = False
        if error is not None:
            if isinstance(error, TrainerTransientError):
                self._set_status(str(error))
            else:
                self._set_status(f"自动重连失败，将继续重试：{error}")
            return
        self._apply_current_values(values or {})
        if mode in ("rooted", "rebound", "scanned"):
            self._set_status(f"已自动连接 PID {self.pid}，当前关卡结构验证通过")

    @staticmethod
    def _unpack_float(raw: bytes) -> float:
        if len(raw) != 4:
            raise TrainerError("读取 float32 失败")
        return struct.unpack("<f", raw)[0]

    @staticmethod
    def _unpack_int(raw: bytes) -> int:
        if len(raw) != 4:
            raise TrainerError("读取 int32 失败")
        return struct.unpack("<i", raw)[0]

    @staticmethod
    def _unpack_pointer(raw: bytes) -> int:
        if len(raw) != 8:
            raise TrainerError("读取对象指针失败")
        return struct.unpack("<Q", raw)[0]

    def _production_address(self, name: str) -> int:
        assert self.candidate is not None
        value = self.candidate["productions"][name].get("total_address")
        if not value:
            raise TrainerError(f"资源 {name} 没有可写库存字段")
        return int(value, 0)

    def _settlement_address(self) -> int:
        assert self.candidate is not None
        return int(self.candidate["settlement"], 0)

    def _read_float(self, handle: int, address: int) -> float:
        return self._unpack_float(memory_scan.read_memory(handle, address, 4))

    def _read_int(self, handle: int, address: int) -> int:
        return self._unpack_int(memory_scan.read_memory(handle, address, 4))

    def _read_authority(self, handle: int) -> float:
        settlement = self._settlement_address()
        maximum = self._read_float(handle, settlement + 0x2F8)
        base = self._read_float(handle, settlement + 0x2FC)
        source_total = 0.0
        for offset in AUTHORITY_SOURCE_OFFSETS:
            pointer = self._unpack_pointer(memory_scan.read_memory(handle, settlement + offset, 8))
            source_total += self._read_float(handle, pointer + 0x10)
        return max(0.0, min(maximum, base + source_total)) * 100.0

    def _read_current_values(self) -> dict:
        with self.memory_lock:
            self._ensure_attached()
            return self._read_current_values_locked()

    def _read_current_values_locked(self) -> dict:
        assert self.pid is not None
        handle = memory_scan.open_read_only(self.pid)
        try:
            food = sum(self._read_float(handle, self._production_address(name)) for name in FOOD_PARTS)
            fuel = sum(self._read_float(handle, self._production_address(name)) for name in FUEL_PARTS)
            settlement = self._settlement_address()
            patience = self._read_int(handle, settlement + 0x340)
            patience_max = self._read_int(handle, settlement + 0x34C)
            return {
                "manpower": self._read_float(handle, self._production_address("manpower")),
                "food": food,
                "water": self._read_float(handle, self._production_address("water")),
                "wood": self._read_float(handle, self._production_address("wood")),
                "fuel": fuel,
                "authority": self._read_authority(handle),
                "patience": (patience, patience_max),
            }
        finally:
            memory_scan.kernel32.CloseHandle(handle)

    def _apply_current_values(self, values: dict) -> None:
        for key in ("manpower", "food", "water", "wood", "fuel"):
            if key in values:
                raw = float(values[key])
                visible = math.floor(max(0.0, raw) + 1e-6)
                self.current_vars[key].set(f"{visible} ({raw:.2f})")
        if "authority" in values:
            self.current_vars["authority"].set(f"{float(values['authority']):.0f}")
        if "patience" in values:
            current, maximum = values["patience"]
            self.current_vars["patience"].set(f"{current} / {maximum}")

    def start_refresh(self) -> None:
        self._set_status("正在读取当前值……")
        self._run_background(self._read_current_values, "当前值已刷新")

    def _parse_target(self, key: str) -> float:
        raw = self.target_vars[key].get().strip()
        try:
            value = float(raw)
        except ValueError as exc:
            raise TrainerError(f"{dict((k, n) for k, n, _ in RESOURCE_ROWS)[key]}目标值无效") from exc
        if not math.isfinite(value) or value < 0:
            raise TrainerError("目标值必须是大于等于0的有限数字")
        limits = {
            "manpower": 999,
            "food": 999,
            "water": 999,
            "wood": 999,
            "fuel": 999,
            "authority": 100,
            "patience": 100000,
        }
        if value > limits[key]:
            raise TrainerError(f"目标值过大；{key} 当前安全上限为 {limits[key]}")
        return value

    def _add_float_change(self, changes: list[dict], handle: int, name: str, address: int, value: float):
        before = memory_scan.read_memory(handle, address, 4)
        after = struct.pack("<f", float(value))
        if before != after:
            changes.append({"name": name, "address": address, "before": before, "after": after})

    def _build_group_changes(
        self, changes: list[dict], handle: int, names: tuple[str, ...], target: float
    ) -> None:
        current = [(name, self._read_float(handle, self._production_address(name))) for name in names]
        delta = target - sum(value for _, value in current)
        if abs(delta) < 0.0001:
            return
        updated = dict(current)
        if delta > 0:
            updated[names[0]] += delta
        else:
            remaining = -delta
            for name, value in current:
                reduction = min(value, remaining)
                updated[name] = value - reduction
                remaining -= reduction
                if remaining <= 0.0001:
                    break
            if remaining > 0.0001:
                raise TrainerError("目标值低于可安全调整的资源总量")
        for name, old_value in current:
            new_value = updated[name]
            if abs(new_value - old_value) >= 0.0001:
                self._add_float_change(
                    changes, handle, name, self._production_address(name), new_value
                )

    def _build_changes(self, handle: int, key: str, target: float) -> list[dict]:
        changes: list[dict] = []
        if key in ("manpower", "water", "wood"):
            self._add_float_change(changes, handle, key, self._production_address(key), target)
        elif key == "food":
            self._build_group_changes(changes, handle, FOOD_PARTS, target)
        elif key == "fuel":
            self._build_group_changes(changes, handle, FUEL_PARTS, target)
        elif key == "authority":
            ratio = target / 100.0
            settlement = self._settlement_address()
            self._add_float_change(changes, handle, "authority_max", settlement + 0x2F8, ratio)
            self._add_float_change(changes, handle, "authority_base", settlement + 0x2FC, ratio)
        elif key == "patience":
            address = self._settlement_address() + 0x340
            before = memory_scan.read_memory(handle, address, 4)
            after = struct.pack("<i", int(round(target)))
            if before != after:
                changes.append(
                    {"name": "objective_patience", "address": address, "before": before, "after": after}
                )
        else:
            raise TrainerError(f"未知项目：{key}")
        return changes

    @session_log.audit
    def _write_key(self, key: str, target: float, log_change: bool = True) -> None:
        with self.memory_lock:
            self._ensure_attached()
            assert self.pid is not None
            handle = memory_scan.open_read_write(self.pid)
            written: list[dict] = []
            try:
                changes = self._build_changes(handle, key, target)
                for change in changes:
                    current = memory_scan.read_memory(handle, change["address"], 4)
                    if current != change["before"]:
                        raise TrainerError(f"{change['name']}在写入前发生变化，已取消本次操作")
                try:
                    for change in changes:
                        memory_scan.write_memory(handle, change["address"], change["after"])
                        if memory_scan.read_memory(handle, change["address"], 4) != change["after"]:
                            raise TrainerError(f"{change['name']}写入后验证失败")
                        written.append(change)
                except Exception:
                    for change in reversed(written):
                        memory_scan.write_memory(handle, change["address"], change["before"])
                    raise
            finally:
                memory_scan.kernel32.CloseHandle(handle)

        session_log.emit('resource_write_verified', pid=self.pid, key=key, target=target,
                         continuous=not log_change, changes=changes)
        if log_change and changes:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            record = {
                "created_local": time.strftime("%Y-%m-%d %H:%M:%S"),
                "process": PROCESS_NAME,
                "pid": self.pid,
                "key": key,
                "target": target,
                "changes": [
                    {
                        "name": item["name"],
                        "address": f"0x{item['address']:016X}",
                        "before_hex": item["before"].hex(),
                        "after_hex": item["after"].hex(),
                    }
                    for item in changes
                ],
            }
            path = LOG_DIR / f"{time.strftime('%Y%m%d_%H%M%S')}_{key}.json"
            path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_player_soldiers(self, handle: int) -> list[dict]:
        assert self.candidate is not None
        regions = list(memory_scan.readable_private_regions(handle))
        if not regions:
            raise TrainerError("没有找到可读取的游戏对象内存")
        contains = memory_scan.private_region_lookup(regions)
        reader = memory_scan.cached_reader(handle, contains)
        try:
            return memory_scan.read_player_soldiers(reader, self.candidate)
        except RuntimeError as exc:
            raise TrainerError(f"玩家战士结构验证失败：{exc}") from exc

    @session_log.audit
    def _accelerate_moving_soldiers(self, log_change: bool = True) -> int:
        """Reduce active player journeys to one turn with checked batch writes."""
        with self.memory_lock:
            self._ensure_attached()
            assert self.pid is not None
            pid = self.pid
            handle = memory_scan.open_read_write(pid)
            changes: list[dict] = []
            written: list[dict] = []
            try:
                for soldier in self._read_player_soldiers(handle):
                    if not soldier["can_accelerate"]:
                        continue
                    changes.append(
                        {
                            **soldier,
                            "before": struct.pack("<f", soldier["turns"]),
                            "after": struct.pack("<f", 1.0),
                        }
                    )

                # The game may advance between the validated snapshot and this
                # write.  Recheck every mutable field before changing anything.
                for change in changes:
                    if memory_scan.read_memory(handle, change["turns_address"], 4) != change["before"]:
                        raise TrainerTransientError("战士移动回合刚刚发生变化，将自动重试")
                    if memory_scan.read_memory(handle, change["object"] + 0x8C, 1) != b"\x00":
                        raise TrainerTransientError("战士状态刚刚发生变化，将自动重试")
                    current_zone = self._unpack_pointer(
                        memory_scan.read_memory(handle, change["object"] + 0x30, 8)
                    )
                    from_zone = self._unpack_pointer(
                        memory_scan.read_memory(handle, change["object"] + 0x38, 8)
                    )
                    raw_design = memory_scan.read_memory(
                        handle, change["object"] + 0xB8, 8
                    )
                    if len(raw_design) != 8:
                        raise TrainerTransientError(
                            "战士移动状态刚刚发生变化，将自动重试"
                        )
                    design = self._unpack_pointer(raw_design)
                    if not design:
                        raise TrainerTransientError(
                            "战士移动状态刚刚发生变化，将自动重试"
                        )
                    design_owner = self._unpack_pointer(
                        memory_scan.read_memory(handle, design + 0x10, 8)
                    )
                    if (
                        current_zone != change["current_zone"]
                        or from_zone != change["from_zone"]
                        or current_zone == from_zone
                        or design != change["design"]
                        or design_owner != change["object"]
                    ):
                        raise TrainerTransientError("战士移动状态刚刚发生变化，将自动重试")

                try:
                    for change in changes:
                        memory_scan.write_memory(
                            handle, change["turns_address"], change["after"]
                        )
                        if (
                            memory_scan.read_memory(handle, change["turns_address"], 4)
                            != change["after"]
                        ):
                            raise TrainerError(
                                f"战士 {change['index']} 的移动回合写入后验证失败"
                            )
                        written.append(change)
                except Exception:
                    for change in reversed(written):
                        memory_scan.write_memory(
                            handle, change["turns_address"], change["before"]
                        )
                    raise
            finally:
                memory_scan.kernel32.CloseHandle(handle)

        if log_change and changes:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            record = {
                "created_local": time.strftime("%Y-%m-%d %H:%M:%S"),
                "process": PROCESS_NAME,
                "pid": pid,
                "key": "soldier_fast_move",
                "target_turns": 1.0,
                "changes": [
                    {
                        "index": item["index"],
                        "soldier": f"0x{item['object']:016X}",
                        "address": f"0x{item['turns_address']:016X}",
                        "before": item["turns"],
                        "after": 1.0,
                    }
                    for item in changes
                ],
            }
            milliseconds = int(time.time() * 1000) % 1000
            path = LOG_DIR / (
                f"{time.strftime('%Y%m%d_%H%M%S')}_{milliseconds:03d}_soldier_fast_move.json"
            )
            path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return len(changes)

    def start_set_one(self, key: str) -> None:
        try:
            target = self._parse_target(key)
        except Exception as exc:
            self._background_error(exc)
            return
        self._set_status("正在设置并验证……")

        def task():
            self._write_key(key, target)
            return self._read_current_values()

        self._run_background(task, "设置完成；暂停状态下可能需要短暂推进才刷新界面")

    def start_set_all(self) -> None:
        try:
            targets = {key: self._parse_target(key) for key, _, _ in RESOURCE_ROWS}
        except Exception as exc:
            self._background_error(exc)
            return
        self._set_status("正在设置全部项目……")

        def task():
            for key, target in targets.items():
                self._write_key(key, target)
            return self._read_current_values()

        self._run_background(task, "全部设置完成")

    def stop_all_locks(self) -> None:
        for variable in self.freeze_vars.values():
            variable.set(False)
        self.team_keep_var.set(False)
        self._set_status("已停止所有持续锁定")

    def _fast_move_toggled(self) -> None:
        if self.fast_move_var.get():
            self.fast_move_status_var.set("已启用，等待移动")
            self._set_status("战士快速移动已启用；到达仍由下一次游戏推进正常触发")
        else:
            self.fast_move_status_var.set("未启用")
            self._set_status("战士快速移动已关闭")

    def _lock_tick(self) -> None:
        if getattr(self, '_closing', False):
            return
        if not self.lock_worker_running and self.pid is not None:
            selected = [key for key, variable in self.freeze_vars.items() if variable.get()]
            fast_move = self.fast_move_var.get()
            if selected or fast_move:
                try:
                    targets = {key: self._parse_target(key) for key in selected}
                except Exception as exc:
                    self._background_error(exc)
                    self.stop_all_locks()
                else:
                    self.lock_worker_running = True

                    def worker():
                        try:
                            accelerated = 0
                            if fast_move:
                                accelerated = self._accelerate_moving_soldiers()
                            for key, target in targets.items():
                                self._write_key(key, target, log_change=False)
                            if fast_move:
                                self.root.after(
                                    0,
                                    lambda count=accelerated: self._fast_move_tick_succeeded(
                                        count
                                    ),
                                )
                        except Exception as exc:
                            if isinstance(exc, TrainerTransientError):
                                self.root.after(0, lambda error=exc: self._lock_retry_later(error))
                            else:
                                self.root.after(0, lambda error=exc: self._lock_failed(error))
                        finally:
                            self.lock_worker_running = False

                    self._start_worker(worker)
        self.root.after(800, self._lock_tick)

    def _lock_failed(self, error: Exception) -> None:
        self.stop_all_locks()
        self.fast_move_var.set(False)
        self.fast_move_status_var.set("已停用")
        self._background_error(error)

    def _lock_retry_later(self, error: Exception) -> None:
        if self.fast_move_var.get():
            self.fast_move_status_var.set("等待自动重试")
        self._set_status(f"持续锁定已暂停，自动重连后继续：{error}")

    def _fast_move_tick_succeeded(self, count: int) -> None:
        if not self.fast_move_var.get():
            return
        if count:
            self.fast_move_status_var.set(f"已加速 {count} 名")
            self._set_status(f"已将 {count} 名玩家战士的剩余路程缩短到 1 回合")
        else:
            self.fast_move_status_var.set("已启用，等待移动")

    def start_expedition(self, action: str) -> None:
        if self.expedition_busy:
            return
        self.expedition_busy = True
        self.expedition_status_var.set("正在连接远征系统……")
        for button in self.expedition_buttons:
            button.configure(state="disabled")

        def worker():
            try:
                with self.memory_lock:
                    result = expedition.operate(action)
                status = f"日期偏移：{result['days']} 天"
                if action != "read":
                    status += "；重进选关刷新任务"
                    try:
                        LOG_DIR.mkdir(parents=True, exist_ok=True)
                        record = dict(result, created_local=time.strftime("%Y-%m-%d %H:%M:%S"))
                        (LOG_DIR / f"expedition_{time.time_ns()}.json").write_text(
                            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
                        )
                    except OSError:
                        status += "（操作成功，但日志保存失败）"
                self.root.after(0, lambda text=status: self._expedition_finished(text))
            except Exception as exc:
                self.root.after(0, lambda text=str(exc): self._expedition_finished(f"远征操作失败：{text}"))

        self._start_worker(worker)

    def _expedition_finished(self, status: str) -> None:
        self.expedition_busy = False
        self.expedition_status_var.set(status)
        for button in self.expedition_buttons:
            button.configure(state="normal")

    def start_teams(self, kind=None) -> None:
        if self.teams_busy:
            return
        self.teams_busy = True
        remember = self.team_keep_var.get()
        self.teams_status_var.set("正在读取队伍……" if kind is None else "正在校验并增加队伍……")
        for button in self.teams_buttons:
            button.configure(state="disabled")
        def worker():
            try:
                with self.memory_lock:
                    result = teams.operate(kind)
                    if kind is not None:
                        self.team_targets[kind] = result['teams'][kind]['count']
                    elif remember:
                        for queue, entry in result['teams'].items():
                            if entry['count'] > 0:
                                self.team_targets[queue] = max(self.team_targets.get(queue, 0), entry['count'])
                counts = result['teams']
                status = f"探索：{counts['explore']['count']} 队　建设：{counts['build']['count']} 队"
                if kind is not None:
                    status += "；已 +1"
                if result.get('log_warning'):
                    status += result['log_warning']
            except Exception as exc:
                status = f"队伍操作失败：{exc}"
            self.root.after(0, lambda text=status: self._teams_finished(text))
        self._start_worker(worker)

    def _teams_finished(self, status):
        self.teams_busy = False
        self.teams_status_var.set(status)
        for button in self.teams_buttons:
            button.configure(state="normal")

    def _team_restore_tick(self):
        if getattr(self, '_closing', False):
            return
        if self.team_keep_var.get() and self.team_targets and not self.team_restore_busy and not self.teams_busy:
            self.team_restore_busy=True
            def worker():
                try:
                    with self.memory_lock:
                        result=None
                        for kind,target in tuple(self.team_targets.items()):
                            result=teams.operate(kind,target=target)
                        if result:
                            counts=result['teams']
                            text=f"保持中：探索 {counts['explore']['count']}，建设 {counts['build']['count']}"
                            self.root.after(0,lambda:self.teams_status_var.set(text))
                except Exception as exc:
                    self.root.after(0,lambda text=str(exc):self.teams_status_var.set(f'队伍保持暂停，稍后重试：{text}'))
                finally:
                    self.team_restore_busy=False
            self._start_worker(worker)
        self.root.after(1500,self._team_restore_tick)

    def start_soldier(self, action):
        if self.soldier_busy:
            return
        selected=None
        if action in soldier_upgrade.ACTIONS:
            index=self.soldier_picker.current()
            if not 0 <= index < len(self.soldier_options):
                self.soldier_status_var.set('请先读取并选择一名战士')
                return
            selected=self.soldier_options[index]
        self.soldier_busy=True
        for button in self.soldier_buttons:
            button.configure(state='disabled')
        def worker():
            try:
                with self.memory_lock:
                    result=soldier_upgrade.operate(action,selected)
                self.root.after(0,lambda:self._soldier_finished(result,None))
            except Exception as exc:
                self.root.after(0,lambda error=str(exc):self._soldier_finished(None,error))
        self._start_worker(worker)

    def _soldier_finished(self, result, error):
        self.soldier_busy=False
        for button in self.soldier_buttons:
            button.configure(state='normal')
        if error:
            self.soldier_status_var.set(error)
            return
        previous=self.soldier_picker.current()
        self.soldier_options=[dict(s,pid=result['pid'],game=result['game'],manager=result['manager'])
                              for s in result['soldiers']]
        self.soldier_picker['values']=[f"{s['ident']} | 经验 {s['exp']:.2f} | 武器 {s['strength']:.2f} | 小队 {s['size']:.2f}"
                                       for s in self.soldier_options]
        if self.soldier_options:
            self.soldier_picker.current(min(max(previous,0),len(self.soldier_options)-1))
        else:
            self.soldier_picker.set('')
        request=result.get('request')
        status=request['status'] if request else 0
        text={0:'已读取；请选择战士和独立升级项目',1:'请求还在等待游戏执行：请切到游戏窗口让时间前进一下（失焦会暂停）',
              2:'游戏正在执行升级，请稍后读取',3:'升级完成',-1:'关卡已变化，升级未执行',
              -2:'战士列表异常，升级未执行',-3:'战士已离场，升级未执行',-4:'已达本工具上限或战士尚未就绪',
              -5:'游戏已没有可选的战士升级奖励',-6:'已有待处理升级，请先点击游戏里的升级图标',
              -7:'升级事件未就绪或校验失败，未触发',-8:'游戏未确认生成一个升级事件，请检查地图后再试',
              -9:'升级事件执行异常；请检查游戏状态，勿连续重试'}[status]
        if status==3 and request['action']==1:
            text='已生成升级事件；请在所选战士所在区域点击升级图标，选择加成'
        elif status==3:
            text+=f"：{request['before']:g} → {request['after']:g}"
        elif status<0 and result.get('diag'):
            stage=soldier_upgrade.STAGE_TEXT.get(result['diag'].get('stage'))
            if stage:
                text+=f"（原生阶段：{stage}；挂钩调用 {result['diag'].get('hook_calls',0)} 次）"
        self.soldier_status_var.set(text if self.soldier_options else '当前关卡没有可升级战士')

    def start_tasks(self, action: str) -> None:
        if self.tasks_busy:
            return
        try:
            count = task_extension.parse_count(self.tasks_count_var.get()) if action == 'add' else 1
        except ValueError as exc:
            self.tasks_status_var.set(str(exc))
            return
        self.tasks_busy = True
        for button in self.tasks_buttons:
            button.configure(state='disabled')
        self.tasks_status_var.set('正在处理任务，请稍候……')
        def worker():
            try:
                with self.memory_lock:
                    result = task_extension.operate(action, count)
                if action == 'add':
                    status = f"已添加 {result['count']} 个；切换赛季/重进地图后读取确认"
                elif action == 'clear':
                    status = '已清除；切换赛季或重进地图刷新'
                elif result['error']:
                    status = f"生成未完成（错误 {result['error']}），请清除本次添加。"
                elif result['count']:
                    status = f"已配置 {result['count']} 个；最近生成 {result['generated']} 个；地图列表构建 {result['calls']} 次。"
                else:
                    status = '当前没有添加任务。'
            except Exception as exc:
                status = f'任务操作失败：{exc}'
            self.root.after(0, lambda: self._tasks_finished(status))
        self._start_worker(worker)

    def _tasks_finished(self, status: str) -> None:
        self.tasks_busy = False
        self.tasks_status_var.set(status)
        for button in self.tasks_buttons:
            button.configure(state='normal')

    def open_log_directory(self) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(session_log.CURRENT.folder if session_log.CURRENT else LOG_DIR)  # type: ignore[attr-defined]
        except OSError as exc:
            self._background_error(exc)


def main() -> None:
    global LOG_DIR
    APP_DATA.mkdir(parents=True, exist_ok=True)
    base = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
    root = tk.Tk()
    root.withdraw()
    try:
        session = session_log.Session(base / 'logs', TRAINER_VERSION)
    except OSError as exc:
        messagebox.showerror('无法创建日志', f'请将修改器放在可写目录后重试：{exc}', parent=root)
        root.destroy()
        return
    session_log.CURRENT = session
    LOG_DIR = session.folder / 'operations'
    session.start()
    try:
        app = TrainerApp(root)
        def callback_error(kind, value, tb):
            import traceback
            session_log.emit('ui_exception', error=str(value), traceback=''.join(traceback.format_exception(kind, value, tb)))
            app._set_status(f'界面错误：{value}')
        root.report_callback_exception = callback_error
        root.deiconify()
        root.mainloop()
    finally:
        session.finish()
        session_log.CURRENT = None


if __name__ == "__main__":
    main()
