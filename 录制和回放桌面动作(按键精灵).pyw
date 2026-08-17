#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import json
import threading
from queue import Queue, Empty

# ============================================================
# Windows DPI 设置
# ============================================================

IS_WIN = sys.platform == "win32"

if IS_WIN:
    import ctypes
    from ctypes import wintypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox

from pynput import keyboard, mouse
from pynput.keyboard import Key, Controller as KBController
from pynput.mouse import Button, Controller as MSController

# ============================================================
# Windows 原生鼠标 API
# ============================================================

if IS_WIN:
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    user32 = ctypes.windll.user32
    user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
    user32.GetCursorPos.restype = wintypes.BOOL
    user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    user32.SetCursorPos.restype = wintypes.BOOL
    user32.WindowFromPoint.argtypes = [POINT]
    user32.WindowFromPoint.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD)
    ]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD

# ============================================================
# 全局输入控制器
# ============================================================

kb = KBController()
ms = MSController()

# ============================================================
# 全局变量
# ============================================================

CURRENT_PID = os.getpid()
LISTENER_QUEUE_MAX = 50000

events = []
events_lock = threading.RLock()

listener_queue = Queue(maxsize=LISTENER_QUEUE_MAX)
gui_queue = Queue()

recorder_thread_stop = threading.Event()
reset_recorder_signal = threading.Event()

playback_thread = None
playback_thread_stop = threading.Event()

kb_listener = None
ms_listener = None

record_mouse_moves = threading.Event()
record_mouse_moves.set()

ignore_clicks_since = 0.0
ignore_clicks_lock = threading.Lock()

# ---------- 新增全局状态 ----------
is_recording = False          # 是否正在录制
is_playback_active = False    # 是否正在回放
simulating = False            # 是否正在模拟操作（屏蔽监听回调）
ctrl_pressed = False          # Ctrl 键是否按下（用于热键检测）
# ---------------------------------

# ============================================================
# 鼠标坐标：Windows 原生真实屏幕坐标
# ============================================================

def get_native_mouse_position():
    if IS_WIN:
        try:
            pt = POINT()
            if user32.GetCursorPos(ctypes.byref(pt)):
                return int(pt.x), int(pt.y)
        except Exception:
            pass
    try:
        x, y = ms.position
        return int(x), int(y)
    except Exception:
        return 0, 0

def set_native_mouse_position(x, y):
    x = int(round(x))
    y = int(round(y))
    if IS_WIN:
        try:
            ok = user32.SetCursorPos(x, y)
            if ok:
                return True
        except Exception:
            pass
    try:
        ms.position = (x, y)
        return True
    except Exception:
        return False

# ============================================================
# 判断鼠标是否位于本程序窗口
# ============================================================

def is_cursor_over_self_window(x=None, y=None):
    if not IS_WIN:
        return False
    try:
        if x is None or y is None:
            x, y = get_native_mouse_position()
        pt = POINT()
        pt.x = int(x)
        pt.y = int(y)
        hwnd_under_cursor = user32.WindowFromPoint(pt)
        if not hwnd_under_cursor:
            return False
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd_under_cursor, ctypes.byref(pid))
        return pid.value == CURRENT_PID
    except Exception:
        return False

# ============================================================
# 特殊键中文名称
# ============================================================

SPECIAL_KEY_CN = {
    "space": "空格",
    "enter": "回车",
    "tab": "Tab",
    "shift": "Shift",
    "shift_r": "Shift(右)",
    "ctrl": "Ctrl",
    "ctrl_r": "Ctrl(右)",
    "alt": "Alt",
    "alt_r": "Alt(右)",
    "caps_lock": "大写锁定",
    "esc": "Esc",
    "backspace": "退格",
    "delete": "Delete",
    "home": "Home",
    "end": "End",
    "page_up": "PageUp",
    "page_down": "PageDown",
    "left": "←",
    "right": "→",
    "up": "↑",
    "down": "↓",
}
for i in range(1, 13):
    SPECIAL_KEY_CN[f"f{i}"] = f"F{i}"

# ============================================================
# 序列化
# ============================================================

def serialize_key(key):
    try:
        return {"is_special": False, "value": key.char}
    except AttributeError:
        name = str(key)
        if name.startswith("Key."):
            name = name.split(".", 1)[1]
        return {"is_special": True, "value": name}

def deserialize_key(obj):
    if obj is None:
        return None
    if obj.get("is_special"):
        name = obj.get("value")
        try:
            return getattr(Key, name) if name else None
        except Exception:
            return None
    return obj.get("value")

def serialize_button(btn):
    try:
        return str(btn).split(".")[1]
    except Exception:
        return str(btn)

def deserialize_button(name):
    try:
        if "." in str(name):
            name = str(name).split(".")[1]
        return getattr(Button, name)
    except Exception:
        return Button.left

# ============================================================
# 事件描述
# ============================================================

def describe_event_cn(e):
    t = e.get("type")
    if t in ("key_down", "key_up"):
        k = e.get("key", {})
        if k.get("is_special"):
            label = SPECIAL_KEY_CN.get(k.get("value"), k.get("value"))
        else:
            label = repr(k.get("value"))
        return f"{'按下' if t == 'key_down' else '松开'} 键 {label}"
    elif t == "mouse_move":
        pos = e.get("pos", [0, 0])
        return f"移动鼠标 到 ({pos[0]},{pos[1]})"
    elif t == "mouse_click":
        btn = {
            "left": "左键",
            "right": "右键",
            "middle": "中键"
        }.get(e.get("button", "left"), e.get("button"))
        pos = e.get("pos", [0, 0])
        return f"鼠标{btn} {'按下' if e.get('pressed') else '松开'} 于 ({pos[0]},{pos[1]})"
    elif t == "mouse_scroll":
        return f"滚动 ({e.get('dx', 0)}, {e.get('dy', 0)})"
    return "未知事件"

# ============================================================
# 事件加入队列
# ============================================================

def enqueue_event(ev):
    try:
        listener_queue.put_nowait(ev)
    except Exception:
        pass

# ============================================================
# 键盘监听（修改：支持热键 + 屏蔽模拟操作）
# ============================================================

def on_keyboard_press(k):
    global ctrl_pressed, simulating, is_playback_active, is_recording

    # 模拟操作期间完全忽略
    if simulating:
        return

    # 更新 Ctrl 状态
    if k == Key.ctrl:
        ctrl_pressed = True

    # 检测热键 Ctrl+F12（回放进行中才生效）
    if is_playback_active and k == Key.f12 and ctrl_pressed:
        playback_thread_stop.set()
        return  # 不记录此事件

    # 回放进行中，忽略所有其他键盘事件
    if is_playback_active:
        return

    # 录制进行中，正常记录
    if is_recording:
        enqueue_event({
            "timestamp": time.time(),
            "type": "key_down",
            "key": serialize_key(k)
        })

def on_keyboard_release(k):
    global ctrl_pressed, simulating, is_playback_active, is_recording

    if simulating:
        return

    if k == Key.ctrl:
        ctrl_pressed = False

    if is_playback_active:
        return

    if is_recording:
        enqueue_event({
            "timestamp": time.time(),
            "type": "key_up",
            "key": serialize_key(k)
        })

# ============================================================
# 鼠标监听（修改：回放中忽略）
# ============================================================

def on_mouse_move(x, y):
    if simulating or is_playback_active:
        return
    if is_recording:
        real_x, real_y = get_native_mouse_position()
        enqueue_event({
            "timestamp": time.time(),
            "type": "mouse_move",
            "pos": [real_x, real_y]
        })

def on_mouse_click(x, y, button, pressed):
    if simulating or is_playback_active:
        return
    if is_recording:
        real_x, real_y = get_native_mouse_position()
        enqueue_event({
            "timestamp": time.time(),
            "type": "mouse_click",
            "button": serialize_button(button),
            "pressed": bool(pressed),
            "pos": [real_x, real_y]
        })

def on_mouse_scroll(x, y, dx, dy):
    if simulating or is_playback_active:
        return
    if is_recording:
        real_x, real_y = get_native_mouse_position()
        enqueue_event({
            "timestamp": time.time(),
            "type": "mouse_scroll",
            "dx": float(dx),
            "dy": float(dy),
            "pos": [real_x, real_y]
        })

# ============================================================
# 启动 / 停止监听（启动由主程序调用，停止保留但不使用）
# ============================================================

def start_listeners():
    global kb_listener, ms_listener
    if not kb_listener:
        kb_listener = keyboard.Listener(
            on_press=on_keyboard_press,
            on_release=on_keyboard_release
        )
        kb_listener.start()
    if not ms_listener:
        ms_listener = mouse.Listener(
            on_move=on_mouse_move,
            on_click=on_mouse_click,
            on_scroll=on_mouse_scroll
        )
        ms_listener.start()

def stop_listeners():
    global kb_listener, ms_listener
    if kb_listener:
        try:
            kb_listener.stop()
        except Exception:
            pass
        kb_listener = None
    if ms_listener:
        try:
            ms_listener.stop()
        except Exception:
            pass
        ms_listener = None

# ============================================================
# 录制线程（修改：检查 is_recording 标志）
# ============================================================

def recorder_loop():
    last_kept_ts = None

    def emit_event(ev, refresh_ui=True):
        nonlocal last_kept_ts
        ts = ev.get("timestamp", time.time())
        if last_kept_ts is None:
            dt = 0.0
        else:
            dt = max(0.0, ts - last_kept_ts)
        last_kept_ts = ts
        ev_out = dict(ev)
        ev_out["dt"] = dt
        ev_out["ts"] = ts
        with events_lock:
            events.append(ev_out)
        if refresh_ui:
            gui_queue.put(("_REFRESH_TABLE_", None))

    while not recorder_thread_stop.is_set():
        if reset_recorder_signal.is_set():
            last_kept_ts = None
            reset_recorder_signal.clear()

        try:
            ev = listener_queue.get(timeout=0.01)
        except Empty:
            continue

        # ---------- 新增：非录制状态直接丢弃 ----------
        if not is_recording:
            continue
        # ---------------------------------------------

        try:
            ts = ev.get("timestamp", time.time())
            etype = ev.get("type")
            pos = ev.get("pos")
            if pos:
                px, py = pos[0], pos[1]
            else:
                px = py = None

            # 忽略自己窗口上的操作
            if px is not None and py is not None:
                if is_cursor_over_self_window(px, py):
                    continue

            # 停止录制后的一小段时间忽略点击
            if etype == "mouse_click":
                with ignore_clicks_lock:
                    ics = ignore_clicks_since
                if ics and ts >= ics:
                    continue

            # 鼠标移动
            if etype == "mouse_move":
                if record_mouse_moves.is_set():
                    emit_event(ev, refresh_ui=False)
                continue

            # 其它事件
            emit_event(ev, refresh_ui=True)

        except Exception as ex:
            gui_queue.put(("_LOG_", f"录制异常: {ex}"))

# ============================================================
# 回放鼠标移动
# ============================================================

def playback_mouse_move(x, y):
    x = int(round(x))
    y = int(round(y))
    set_native_mouse_position(x, y)

# ============================================================
# 回放鼠标点击（修改：添加模拟标志）
# ============================================================

def playback_mouse_click(e):
    pos = e.get("pos")
    if pos and len(pos) >= 2:
        x = int(round(pos[0]))
        y = int(round(pos[1]))
        set_native_mouse_position(x, y)
        time.sleep(0.015)

    btn = deserialize_button(e.get("button"))

    global simulating
    if e.get("pressed"):
        simulating = True
        try:
            ms.press(btn)
        finally:
            simulating = False
    else:
        simulating = True
        try:
            ms.release(btn)
        finally:
            simulating = False

# ============================================================
# 回放线程（修改：保持监听器，增加模拟标志，管理回放状态）
# ============================================================

def playback_worker(evts, speed_multiplier, repeat_count=1):
    global is_playback_active, simulating

    try:
        # ---------- 设置回放进行中 ----------
        is_playback_active = True
        # 不再停止监听器，保持热键可用

        if not evts:
            gui_queue.put(("_PLAY_FINISH_", None))
            return

        current_loop = 0
        while not playback_thread_stop.is_set():
            current_loop += 1
            if repeat_count > 0:
                loop_str = f"（第 {current_loop}/{repeat_count} 次）"
            else:
                loop_str = f"（第 {current_loop} 次循环）"

            gui_queue.put(("_STATUS_", f"▶️ 精确回放中...{loop_str}"))

            for idx, e in enumerate(evts):
                if playback_thread_stop.is_set():
                    break

                gui_queue.put(("_PLAY_START_", idx))
                success = True
                err_msg = ""

                try:
                    dt = float(e.get("dt", 0.0))
                    if dt > 0:
                        time.sleep(dt / speed_multiplier)

                    t = e.get("type")

                    # ---------- 键盘操作（带模拟标志） ----------
                    if t in ("key_down", "key_up"):
                        k = deserialize_key(e.get("key"))
                        if k is not None:
                            simulating = True
                            try:
                                if t == "key_down":
                                    kb.press(k)
                                else:
                                    kb.release(k)
                            finally:
                                simulating = False

                    # ---------- 鼠标移动（原生API，无需模拟标志） ----------
                    elif t == "mouse_move":
                        pos = e.get("pos")
                        if pos and len(pos) >= 2 and pos[0] is not None and pos[1] is not None:
                            playback_mouse_move(pos[0], pos[1])

                    # ---------- 鼠标点击（内部已处理模拟标志） ----------
                    elif t == "mouse_click":
                        playback_mouse_click(e)

                    # ---------- 鼠标滚轮（带模拟标志） ----------
                    elif t == "mouse_scroll":
                        simulating = True
                        try:
                            ms.scroll(e.get("dx", 0), e.get("dy", 0))
                        finally:
                            simulating = False

                except Exception as ex:
                    success = False
                    err_msg = str(ex)

                gui_queue.put(("_PLAY_DONE_", (idx, success, err_msg)))

            if repeat_count > 0 and current_loop >= repeat_count:
                break

        gui_queue.put(("_PLAY_FINISH_", None))

    finally:
        # ---------- 无论何种方式退出，重置回放状态 ----------
        is_playback_active = False
        # 确保模拟标志恢复
        simulating = False

# ============================================================
# 获取桌面路径
# ============================================================

def get_desktop_path():
    if IS_WIN:
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
            )
            path, _ = winreg.QueryValueEx(key, "Desktop")
            winreg.CloseKey(key)
            path = os.path.expandvars(path)
            if os.path.isdir(path):
                return path
        except Exception:
            pass
    user_home = os.path.expanduser("~")
    for p in [
        os.path.join(user_home, "OneDrive", "桌面"),
        os.path.join(user_home, "Desktop"),
        os.path.join(user_home, "桌面")
    ]:
        if os.path.isdir(p):
            return p
    return os.getcwd()

# ============================================================
# 自定义窗口
# ============================================================

class BaseCustomWindow:
    # （该类无修改，保持原样）
    def __init__(self, root, title="自定义窗口", width=800, height=650):
        self.root = root
        self.window_title = title
        self.width = width
        self.height = height
        self.bg_color = "#EBF7DF"
        self.title_bg = "#d9eec9"
        self.btn_hover_bg = "#c5e3b2"
        self.shadow_color = "#c2d2b3"
        self.x_offset = None
        self.y_offset = None
        self._init_window_structure()
        self._setup_style()
        self._build_layout()
        self.setup_content(self.main_container)
        self._center_and_show()

    def _init_window_structure(self):
        self.root.title(self.window_title)
        self.root.geometry("0x0+0+0")
        self.root.attributes("-alpha", 0.0)
        self.top = tk.Toplevel(self.root)
        self.top.overrideredirect(True)
        self.top.geometry(f"{self.width}x{self.height}")
        self.top.withdraw()
        self.root.bind("<Map>", self._on_restore)

    def _setup_style(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("WinBg.TFrame", background=self.bg_color)
        self.style.configure("WinBg.TCheckbutton", background=self.bg_color)
        self.style.map("WinBg.TCheckbutton", background=[("active", self.bg_color)])

    def _build_layout(self):
        self.shadow_frame = tk.Frame(self.top, bg=self.shadow_color)
        self.shadow_frame.pack(fill=tk.BOTH, expand=True)
        self.main_container = tk.Frame(self.shadow_frame, bg=self.bg_color)
        self.main_container.place(x=0, y=0, relwidth=1, relheight=1, width=-3, height=-3)

        self.title_bar = tk.Frame(self.main_container, bg=self.title_bg, height=36)
        self.title_bar.pack(fill=tk.X)
        self.title_bar.pack_propagate(False)

        tk.Label(self.title_bar, text=self.window_title, bg=self.title_bg,
                 font=("微软雅黑", 11, "bold")).pack(side=tk.LEFT, padx=12)

        btn_close = tk.Button(self.title_bar, text="×", bg=self.title_bg,
                              activebackground=self.btn_hover_bg, relief="flat",
                              font=("", 12), width=3, command=self.root.destroy)
        btn_close.pack(side=tk.RIGHT)
        btn_close.bind("<Enter>", lambda e: btn_close.config(bg=self.btn_hover_bg))
        btn_close.bind("<Leave>", lambda e: btn_close.config(bg=self.title_bg))

        btn_min = tk.Button(self.title_bar, text="−", bg=self.title_bg,
                            activebackground=self.btn_hover_bg, relief="flat",
                            font=("", 12), width=3, command=self._min_win)
        btn_min.pack(side=tk.RIGHT)
        btn_min.bind("<Enter>", lambda e: btn_min.config(bg=self.btn_hover_bg))
        btn_min.bind("<Leave>", lambda e: btn_min.config(bg=self.title_bg))

        self.title_bar.bind("<ButtonPress-1>", self._start_move)
        self.title_bar.bind("<ButtonRelease-1>", self._stop_move)
        self.title_bar.bind("<B1-Motion>", self._do_move)

    def _center_and_show(self):
        self.top.update()
        sw = self.top.winfo_screenwidth()
        sh = self.top.winfo_screenheight()
        x = (sw - self.width) // 2
        y = (sh - self.height) // 2
        self.top.geometry(f"{self.width}x{self.height}+{x}+{y}")
        self.top.deiconify()

    def _min_win(self):
        self.top.withdraw()
        self.root.iconify()

    def _on_restore(self, event):
        if self.root.state() == "normal":
            self.top.deiconify()

    def _start_move(self, event):
        self.x_offset = event.x
        self.y_offset = event.y

    def _stop_move(self, event):
        self.x_offset = None
        self.y_offset = None

    def _do_move(self, event):
        if self.x_offset is None or self.y_offset is None:
            return
        self.top.geometry(
            f"+{self.top.winfo_x() + event.x - self.x_offset}"
            f"+{self.top.winfo_y() + event.y - self.y_offset}"
        )

    def setup_content(self, parent):
        pass

# ============================================================
# 主程序
# ============================================================

class AutoRecorderApp(BaseCustomWindow):
    def setup_content(self, parent):
        self.is_playing = False

        self.content_frame = ttk.Frame(parent, style="WinBg.TFrame", padding=15)
        self.content_frame.pack(fill=tk.BOTH, expand=True)

        # 状态
        status_frame = tk.Frame(self.content_frame, bg=self.bg_color)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(status_frame, text="状态: ", bg=self.bg_color,
                 font=("微软雅黑", 10, "bold")).pack(side=tk.LEFT)
        self.lbl_status = tk.Label(status_frame, text="空闲", bg=self.bg_color,
                                   font=("微软雅黑", 10), fg="#333333")
        self.lbl_status.pack(side=tk.LEFT)

        # 按钮
        btn_frame = tk.Frame(self.content_frame, bg=self.bg_color)
        btn_frame.pack(fill=tk.X, pady=5)
        btn_style = {"font": ("微软雅黑", 10, "bold"), "relief": tk.RAISED,
                     "bd": 2, "width": 10}

        self.btn_rec = tk.Button(btn_frame, text="🔴 录制", fg="red",
                                 command=self.on_record, **btn_style)
        self.btn_rec.grid(row=0, column=0, padx=5)

        self.btn_stop_rec = tk.Button(btn_frame, text="⏹️ 停止录制", fg="#8B0000",
                                      command=self.on_stop_record, **btn_style)
        self.btn_stop_rec.grid(row=0, column=1, padx=5)

        self.btn_play = tk.Button(btn_frame, text="▶️ 回放", fg="green",
                                  command=self.on_play, **btn_style)
        self.btn_play.grid(row=0, column=2, padx=5)

        self.btn_stop_play = tk.Button(btn_frame, text="⏸️ 停止回放", fg="#006400",
                                       command=self.on_stop_play, **btn_style)
        self.btn_stop_play.grid(row=0, column=3, padx=5)

        tk.Button(btn_frame, text="💾 保存", fg="#0000CD",
                  command=self.on_save, **btn_style).grid(row=0, column=4, padx=5)
        tk.Button(btn_frame, text="📂 读取", fg="#800080",
                  command=self.on_load, **btn_style).grid(row=0, column=5, padx=5)
        tk.Button(btn_frame, text="🗑️ 清空", fg="#D2691E",
                  command=self.on_clear, **btn_style).grid(row=0, column=6, padx=5)

        # 选项
        opt_frame = ttk.Frame(self.content_frame, style="WinBg.TFrame")
        opt_frame.pack(fill=tk.X, pady=10)

        self.var_mouse_move = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="记录鼠标轨迹", variable=self.var_mouse_move,
                        style="WinBg.TCheckbutton", command=self.toggle_mouse).pack(side=tk.LEFT, padx=5)

        tk.Label(opt_frame, text="倍率:", bg=self.bg_color).pack(side=tk.LEFT, padx=(10, 2))
        self.entry_speed = tk.Entry(opt_frame, width=5)
        self.entry_speed.insert(0, "1.0")
        self.entry_speed.pack(side=tk.LEFT)

        tk.Label(opt_frame, text="回放次数:", bg=self.bg_color).pack(side=tk.LEFT, padx=(10, 2))
        self.entry_repeat = tk.Entry(opt_frame, width=5)
        self.entry_repeat.insert(0, "1")
        self.entry_repeat.pack(side=tk.LEFT)

        tk.Label(opt_frame, text="(0为无限)", bg=self.bg_color,
                 fg="#666666", font=("微软雅黑", 8)).pack(side=tk.LEFT, padx=(2, 5))
        tk.Label(opt_frame, text="俏狐出品 QQ:86074731", bg=self.bg_color,
                 fg="#006400", font=("微软雅黑", 8)).pack(side=tk.RIGHT, padx=5)

        # 事件表
        table_frame = tk.Frame(self.content_frame)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        cols = ("#", "间隔(s)", "操作", "状态")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=15)
        self.tree.heading("#1", text="#")
        self.tree.column("#1", width=50, anchor=tk.CENTER)
        self.tree.heading("#2", text="间隔(s)")
        self.tree.column("#2", width=80, anchor=tk.CENTER)
        self.tree.heading("#3", text="操作")
        self.tree.column("#3", width=450, anchor=tk.W)
        self.tree.heading("#4", text="状态")
        self.tree.column("#4", width=120, anchor=tk.CENTER)

        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.tag_configure("playing", background="#ADD8E6")
        self.tree.tag_configure("error", background="#FFB6C1")

        # 日志
        self.txt_log = tk.Text(self.content_frame, height=6, bg="#F0F8FF", font=("Consolas", 9))
        self.txt_log.pack(fill=tk.X, pady=(10, 0))

        self.bind_right_click()
        self.root.after(100, self.process_gui_queue)

    # 日志
    def log(self, msg):
        self.txt_log.insert(tk.END, msg + "\n")
        self.txt_log.see(tk.END)

    # 鼠标轨迹
    def toggle_mouse(self):
        if self.var_mouse_move.get():
            record_mouse_moves.set()
        else:
            record_mouse_moves.clear()

    # GUI 消息处理
    def process_gui_queue(self):
        while not gui_queue.empty():
            try:
                msg_type, data = gui_queue.get_nowait()
            except Empty:
                break

            if msg_type == "_LOG_":
                self.log(data)
            elif msg_type == "_STATUS_":
                self.lbl_status.config(text=data, fg="green")
            elif msg_type == "_REFRESH_TABLE_":
                self.refresh_table()
            elif msg_type == "_PLAY_START_":
                for item in self.tree.get_children():
                    self.tree.item(item, tags=())
                children = self.tree.get_children()
                if data < len(children):
                    item = children[data]
                    self.tree.item(item, tags=("playing",))
                    self.tree.set(item, 3, "进行中")
                    self.tree.see(item)
            elif msg_type == "_PLAY_DONE_":
                idx, success, err = data
                children = self.tree.get_children()
                if idx < len(children):
                    item = children[idx]
                    if success:
                        self.tree.item(item, tags=())
                        self.tree.set(item, 3, "成功")
                    else:
                        self.tree.item(item, tags=("error",))
                        self.tree.set(item, 3, f"失败: {err}")
            elif msg_type == "_PLAY_FINISH_":
                self.is_playing = False
                self.btn_play.config(state=tk.NORMAL)
                self.lbl_status.config(text="回放已完成", fg="black")
                for item in self.tree.get_children():
                    if "playing" in self.tree.item(item, "tags"):
                        self.tree.item(item, tags=())

        self.root.after(100, self.process_gui_queue)

    # 刷新表格
    def refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        with events_lock:
            for i, ev in enumerate(events):
                self.tree.insert("", tk.END, values=(
                    i,
                    round(ev.get("dt", 0.0), 3),
                    describe_event_cn(ev),
                    ""
                ))

    # ---------- 开始录制（修改：设置录制标志） ----------
    def on_record(self):
        global is_recording, ignore_clicks_since

        if self.is_playing:
            return

        playback_thread_stop.set()

        with ignore_clicks_lock:
            ignore_clicks_since = 0.0

        reset_recorder_signal.set()

        while not listener_queue.empty():
            try:
                listener_queue.get_nowait()
            except Empty:
                break

        with events_lock:
            events.clear()

        # ---------- 设置录制状态 ----------
        is_recording = True
        start_listeners()  # 确保监听器运行

        self.lbl_status.config(text="🔴 录制中...", fg="red")
        self.log("开始录制。")
        self.log("坐标模式：Windows GetCursorPos 原生屏幕坐标")
        self.refresh_table()

    # ---------- 停止录制（修改：关闭录制标志，但不停监听器） ----------
    def on_stop_record(self):
        global ignore_clicks_since, is_recording

        cutoff = time.time() - 0.15
        with ignore_clicks_lock:
            ignore_clicks_since = cutoff

        # 不再停止监听器，保证热键始终可用
        # stop_listeners()   # 已移除

        is_recording = False

        self.lbl_status.config(text="⏹️ 已停止录制", fg="black")
        self.log("停止录制。")

        try:
            x, y = get_native_mouse_position()
            self.log(f"当前 Windows 原生鼠标坐标: ({x}, {y})")
        except Exception:
            pass

        self.refresh_table()

    # 开始回放
    def on_play(self):
        global playback_thread

        if self.is_playing:
            return

        with events_lock:
            if not events:
                self.lbl_status.config(text="⚠️ 没有可回放的事件", fg="orange")
                return
            evs_copy = json.loads(json.dumps(events))

        try:
            speed = float(self.entry_speed.get().strip() or 1.0)
            if speed <= 0:
                speed = 1.0
        except ValueError:
            speed = 1.0

        try:
            repeat = int(self.entry_repeat.get().strip() or 1)
        except ValueError:
            repeat = 1

        self.is_playing = True
        self.btn_play.config(state=tk.DISABLED)
        playback_thread_stop.clear()

        playback_thread = threading.Thread(
            target=playback_worker,
            args=(evs_copy, speed, repeat),
            daemon=True
        )
        playback_thread.start()

        if repeat == 0:
            loop_tip = "无限循环"
        else:
            loop_tip = f"{repeat} 次"
        self.log(f"开始回放 （倍率: {speed}x, 次数: {loop_tip}）...")

    # 停止回放
    def on_stop_play(self):
        playback_thread_stop.set()
        self.lbl_status.config(text="⏸️ 已请求停止回放", fg="orange")

    # 保存 / 读取 / 清空（保持不变）
    def on_save(self):
        fname = filedialog.asksaveasfilename(
            title="保存 JSON 文件",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")]
        )
        if fname:
            with events_lock:
                with open(fname, "w", encoding="utf-8") as f:
                    json.dump(events, f, ensure_ascii=False, indent=2)
            self.lbl_status.config(text="💾 已保存")

    def on_load(self):
        playback_thread_stop.set()
        self.is_playing = False
        self.btn_play.config(state=tk.NORMAL)

        fname = filedialog.askopenfilename(
            title="加载 JSON 文件",
            filetypes=[("JSON", "*.json")]
        )
        if not fname:
            return
        try:
            with open(fname, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("JSON 文件格式错误")
            with events_lock:
                events.clear()
                events.extend(data)
            self.refresh_table()
            self.entry_repeat.delete(0, tk.END)
            self.entry_repeat.insert(0, "1")
            self.lbl_status.config(text="📂 已加载（默认回放 1 次）")
            self.log(f"成功载入脚本: {os.path.basename(fname)}")
        except Exception as ex:
            messagebox.showerror("读取失败", str(ex))

    def on_clear(self):
        playback_thread_stop.set()
        self.is_playing = False
        self.btn_play.config(state=tk.NORMAL)
        with events_lock:
            events.clear()
        self.refresh_table()
        self.lbl_status.config(text="🗑️ 已清空")

    # 右键菜单（保持不变）
    def bind_right_click(self):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="📋 复制到剪贴板", command=self.cmd_copy)
        menu.add_command(label="⬆️ 上移选区", command=self.cmd_up)
        menu.add_command(label="⬇️ 下移选区", command=self.cmd_down)
        menu.add_command(label="📝 导出全部为 TXT", command=self.cmd_export)

        def on_rclick(event):
            item = self.tree.identify_row(event.y)
            if item and item not in self.tree.selection():
                self.tree.selection_set(item)
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        self.tree.bind("<Button-3>", on_rclick)

    def _get_selected_indices(self):
        return sorted([self.tree.index(i) for i in self.tree.selection()])

    def cmd_copy(self):
        idxs = self._get_selected_indices()
        if not idxs:
            return
        with events_lock:
            texts = [
                f"{i} | {round(events[i].get('dt', 0.0), 3)}s | {describe_event_cn(events[i])}"
                for i in idxs if 0 <= i < len(events)
            ]
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(texts))
        self.log("已复制选中行。")

    def cmd_up(self):
        idxs = self._get_selected_indices()
        if not idxs:
            return
        if min(idxs) == 0:
            return
        start, end = min(idxs), max(idxs)
        with events_lock:
            block = events[start:end+1]
            del events[start:end+1]
            for i, item in enumerate(block):
                events.insert(start - 1 + i, item)
        self.refresh_table()

    def cmd_down(self):
        idxs = self._get_selected_indices()
        if not idxs:
            return
        start, end = min(idxs), max(idxs)
        with events_lock:
            if end >= len(events) - 1:
                return
            block = events[start:end+1]
            del events[start:end+1]
            for i, item in enumerate(block):
                events.insert(start + 1 + i, item)
        self.refresh_table()

    def cmd_export(self):
        with events_lock:
            all_lines = [
                f"{i} | {round(ev.get('dt', 0.0), 3)}s | {describe_event_cn(ev)}"
                for i, ev in enumerate(events)
            ]
        fname = os.path.join(
            get_desktop_path(),
            f"auto_recorder_export_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        )
        with open(fname, "w", encoding="utf-8") as f:
            f.write("\n".join(all_lines))
        self.log(f"已导出 TXT 到桌面: {os.path.basename(fname)}")

# ============================================================
# 程序入口
# ============================================================

if __name__ == "__main__":
    recorder_thread_stop.clear()
    threading.Thread(target=recorder_loop, daemon=True).start()

    # ---------- 启动监听器，使热键始终有效 ----------
    start_listeners()

    root = tk.Tk()
    app = AutoRecorderApp(
        root,
        title="按键精灵 — 俏狐出品 QQ:86074731",
        width=820,
        height=680
    )
    root.mainloop()