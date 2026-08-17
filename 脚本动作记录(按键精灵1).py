import pyautogui
import keyboard
import time
import json
import threading
import os
from datetime import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import ctypes
import sys
import win32api
import win32con
import pystray
from PIL import Image, ImageDraw
import win32gui

class SimpleRecorder:
    """简单坐标录制器"""
    
    def __init__(self):
        self.recording = False
        self.playing = False
        self.paused = False
        self.actions = []
        self.start_time = None
        
    def record_action(self, action_type, data):
        current_time = time.time() - self.start_time
        action = {
            'type': action_type,
            'time': round(current_time, 3)
        }
        
        if 'x' in data and 'y' in data:
            action['x'] = data['x']
            action['y'] = data['y']
        if 'key' in data:
            action['key'] = data['key']
        if 'button' in data:
            action['button'] = data['button']
            
        self.actions.append(action)
        return action
        
    def execute_action(self, action):
        try:
            action_type = action.get('type')
            
            if action_type == 'mouse_down':
                x = action.get('x', 0)
                y = action.get('y', 0)
                button = action.get('button', 'left')
                pyautogui.mouseDown(x=x, y=y, button=button)
                return True
                
            elif action_type == 'mouse_up':
                x = action.get('x', 0)
                y = action.get('y', 0)
                button = action.get('button', 'left')
                pyautogui.mouseUp(x=x, y=y, button=button)
                return True
                
            elif action_type == 'key_down':
                key = action.get('key', '')
                if key:
                    pyautogui.keyDown(key)
                    return True
                    
            elif action_type == 'key_up':
                key = action.get('key', '')
                if key:
                    pyautogui.keyUp(key)
                    return True
                    
            return False
            
        except Exception as e:
            print(f"执行失败: {e}")
            return False

class SystemTray:
    """系统托盘图标"""
    
    def __init__(self, app):
        self.app = app
        self.icon = None
        self.running = False
        self.progress = 0
        self.status_text = "就绪"
        self.tray_thread = None
        self._stop_event = threading.Event()
        
    def create_image(self, progress=0, status="就绪"):
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), '#f5f0e8')
        draw = ImageDraw.Draw(image)
        
        draw.rectangle([2, 2, width-2, height-2], fill='#4a7c59', outline='#3d6b4a', width=2)
        
        if progress > 0:
            start_angle = -90
            end_angle = start_angle + (progress / 100) * 360
            draw.arc([8, 8, 56, 56], start=start_angle, end=end_angle, fill='#ffffff', width=4)
        
        if progress > 0:
            text = f"{int(progress)}%"
        else:
            text = "▶"
        
        from PIL import ImageFont
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except:
            font = ImageFont.load_default()
            
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (width - text_width) // 2
        y = (height - text_height) // 2 - 2
        
        draw.text((x, y), text, fill='#ffffff', font=font)
        
        return image
        
    def run(self):
        if self.running:
            return
            
        self.running = True
        self._stop_event.clear()
        
        menu = pystray.Menu(
            pystray.MenuItem("📊 显示主窗口", self.show_window),
            pystray.MenuItem("⏹️ 停止回放", self.stop_playback),
            pystray.MenuItem("📋 查看日志", self.show_log),
            pystray.MenuItem("🚪 退出", self.quit_app)
        )
        
        image = self.create_image(0, "就绪")
        self.icon = pystray.Icon("录制回放工具", image, "🎬 录制回放工具", menu)
        
        # 在独立线程中运行
        self.tray_thread = threading.Thread(target=self._run_icon, daemon=True)
        self.tray_thread.start()
        
    def _run_icon(self):
        try:
            # 运行托盘图标
            self.icon.run()
        except Exception as e:
            pass
        finally:
            self.running = False
            
    def stop(self):
        """停止托盘图标 - 彻底移除"""
        self.running = False
        self._stop_event.set()
        
        if self.icon:
            try:
                # 先隐藏图标
                self.icon.visible = False
                # 然后停止
                self.icon.stop()
            except:
                pass
            self.icon = None
            
        # 等待线程结束
        if self.tray_thread and self.tray_thread.is_alive():
            try:
                self.tray_thread.join(timeout=0.5)
            except:
                pass
                
    def update_progress(self, progress, status="回放中"):
        self.progress = progress
        self.status_text = status
        if self.icon and self.running:
            try:
                image = self.create_image(progress, status)
                self.icon.icon = image
                self.icon.title = f"🎬 {status} {int(progress)}%"
            except:
                pass
            
    def show_window(self):
        if self.app and self.app.root:
            try:
                self.app.root.deiconify()
                self.app.root.lift()
                win32gui.SetForegroundWindow(self.app.root.winfo_id())
            except:
                pass
            
    def stop_playback(self):
        if self.app and self.app.recorder.playing:
            self.app.stop_playback()
            
    def show_log(self):
        if self.app and self.app.root:
            try:
                self.app.root.deiconify()
                self.app.root.lift()
                win32gui.SetForegroundWindow(self.app.root.winfo_id())
                self.app.log_text.see(tk.END)
            except:
                pass
            
    def quit_app(self):
        if self.app:
            self.app.quit_app()

class SimpleRecorderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🎬 操作录制回放工具")
        self.root.geometry("950x700")
        self.root.resizable(True, True)
        
        self.window_position = "center"
        self._set_window_position()
        
        self.recorder = SimpleRecorder()
        self.recording_thread = None
        self.play_thread = None
        self.was_minimized = False
        self.loop_count = 1
        self.current_loop = 0
        self.current_theme = "light"
        self._closing = False
        
        self.tray = SystemTray(self)
        
        self.themes = {
            "dark": {
                "bg": "#2b2b2b",
                "fg": "#ffffff",
                "frame_bg": "#2b2b2b",
                "frame_fg": "#ffffff",
                "text_bg": "#1e1e1e",
                "text_fg": "#d4d4d4",
                "button_bg": "#424242",
                "button_fg": "#ffffff",
                "entry_bg": "#424242",
                "entry_fg": "#ffffff",
                "label_fg": "#ffffff",
                "status_bg": "#1e1e1e",
                "progress_bg": "#3c3c3c",
                "progress_fg": "#4caf50",
                "log_bg": "#1e1e1e",
                "log_fg": "#d4d4d4",
                "title_fg": "#007acc",
                "border_color": "#3c3c3c",
                "toolbar_bg": "#2b2b2b",
                "toolbar_fg": "#888",
                "menu_bg": "#2b2b2b",
                "menu_fg": "#ffffff",
                "spinbox_bg": "#424242",
                "spinbox_fg": "#ffffff",
                "radiobutton_fg": "#ffffff",
                "checkbutton_fg": "#ffffff",
                "status_fg": "#ffffff"
            },
            "light": {
                "bg": "#f5f0e8",
                "fg": "#3c3c3c",
                "frame_bg": "#f5f0e8",
                "frame_fg": "#3c3c3c",
                "text_bg": "#ffffff",
                "text_fg": "#2c2c2c",
                "button_bg": "#d4c9b8",
                "button_fg": "#2c2c2c",
                "entry_bg": "#ffffff",
                "entry_fg": "#2c2c2c",
                "label_fg": "#3c3c3c",
                "status_bg": "#e8e0d5",
                "progress_bg": "#d4c9b8",
                "progress_fg": "#5d8a5e",
                "log_bg": "#faf8f5",
                "log_fg": "#2c2c2c",
                "title_fg": "#4a7c59",
                "border_color": "#d4c9b8",
                "toolbar_bg": "#f5f0e8",
                "toolbar_fg": "#888",
                "menu_bg": "#f5f0e8",
                "menu_fg": "#2c2c2c",
                "spinbox_bg": "#ffffff",
                "spinbox_fg": "#2c2c2c",
                "radiobutton_fg": "#3c3c3c",
                "checkbutton_fg": "#3c3c3c",
                "status_fg": "#3c3c3c"
            }
        }
        
        self.create_widgets()
        self.setup_hotkeys()
        
        self.update_status("就绪 ✅", "green")
        
        if not self.is_admin():
            self.log_message("⚠️ 建议以管理员身份运行", 'warning')
            
        self.update_timer()
        
        self.root.bind_all('<Control-l>', self.clear_log_event)
        self.root.bind_all('<Control-L>', self.clear_log_event)
        self.log_text.bind('<Control-l>', self.clear_log_event)
        self.log_text.bind('<Control-L>', self.clear_log_event)
        
        # 先创建托盘图标，但不显示
        self.tray.run()
        
        # 点击X直接退出，带确认对话框
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.apply_theme()
        
    def _set_window_position(self):
        width = 950
        height = 700
        if self.window_position == "center":
            x = (self.root.winfo_screenwidth() // 2) - (width // 2)
            y = (self.root.winfo_screenheight() // 2) - (height // 2)
        else:
            x = self.root.winfo_screenwidth() - width - 10
            y = self.root.winfo_screenheight() - height - 40
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
    def center_window(self):
        self.window_position = "center"
        width = 950
        height = 700
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
    def move_to_corner(self):
        self.window_position = "corner"
        width = 950
        height = 700
        x = self.root.winfo_screenwidth() - width - 10
        y = self.root.winfo_screenheight() - height - 40
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
    def toggle_window_position(self):
        if self.window_position == "center":
            self.move_to_corner()
            self.log_message("📍 窗口已移到右下角", 'info')
        else:
            self.center_window()
            self.log_message("📍 窗口已居中", 'info')
        
    def is_admin(self):
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False
            
    def setup_hotkeys(self):
        try:
            keyboard.unhook_all()
            keyboard.add_hotkey('f9', self.start_recording)
            keyboard.add_hotkey('f10', self.stop_recording)
            keyboard.add_hotkey('f11', self.toggle_pause)
            keyboard.add_hotkey('ctrl+l', self.clear_log)
            self.log_message("⌨️ 快捷键: F9-开始 F10-停止 F11-暂停 Ctrl+L-清空日志", 'info')
        except Exception as e:
            self.log_message(f"❌ 快捷键注册失败: {e}", 'error')
            
    def apply_theme(self):
        theme = self.themes[self.current_theme]
        
        self.root.configure(bg=theme['bg'])
        self._apply_theme_to_widgets(self.root, theme)
        
        self.log_text.configure(bg=theme['log_bg'], fg=theme['log_fg'])
        self.status_label.configure(bg=theme['status_bg'], fg=theme['fg'])
        self.info_label.configure(bg=theme['status_bg'], fg=theme['fg'] if theme['fg'] != '#ffffff' else '#888')
        self.title_label.configure(fg=theme['title_fg'])
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TProgressbar",
                       background=theme['progress_fg'],
                       troughcolor=theme['progress_bg'],
                       thickness=10)
        
        if self.current_theme == 'light':
            self.log_text.tag_config('info', foreground='#4a7c59')
            self.log_text.tag_config('success', foreground='#2e7d32')
            self.log_text.tag_config('error', foreground='#c62828')
            self.log_text.tag_config('warning', foreground='#e65100')
            self.log_text.tag_config('recording', foreground='#c62828')
            self.log_text.tag_config('mouse', foreground='#6a1b9a')
            self.log_text.tag_config('keyboard', foreground='#0d47a1')
        else:
            self.log_text.tag_config('info', foreground='#4fc3f7')
            self.log_text.tag_config('success', foreground='#81c784')
            self.log_text.tag_config('error', foreground='#ef5350')
            self.log_text.tag_config('warning', foreground='#ffb74d')
            self.log_text.tag_config('recording', foreground='#ff6b6b')
            self.log_text.tag_config('mouse', foreground='#ce93d8')
            self.log_text.tag_config('keyboard', foreground='#81d4fa')
        
        self.log_menu.configure(bg=theme['menu_bg'], fg=theme['menu_fg'])
        
        self.log_message(f"🎨 切换到{ '深色' if self.current_theme == 'dark' else '护眼浅色' }主题", 'info')
        
    def _apply_theme_to_widgets(self, widget, theme):
        try:
            if isinstance(widget, tk.Frame):
                widget.configure(bg=theme['bg'])
            elif isinstance(widget, tk.LabelFrame):
                widget.configure(bg=theme['frame_bg'], fg=theme['frame_fg'])
            elif isinstance(widget, tk.Label):
                if widget == self.title_label:
                    widget.configure(fg=theme['title_fg'])
                else:
                    widget.configure(bg=theme['bg'], fg=theme['label_fg'])
            elif isinstance(widget, tk.Button):
                current_bg = widget.cget('bg')
                if current_bg in ['#d32f2f', '#b71c1c', '#c62828', '#f57c00', 
                                  '#2e7d32', '#1b5e20', '#9e9e9e', '#1565c0', 
                                  '#4a7c59', '#2e7d32']:
                    pass
                else:
                    widget.configure(bg=theme['button_bg'], fg=theme['button_fg'])
            elif isinstance(widget, tk.Checkbutton):
                widget.configure(bg=theme['bg'], fg=theme['checkbutton_fg'],
                               selectcolor=theme['bg'])
            elif isinstance(widget, tk.Radiobutton):
                widget.configure(bg=theme['bg'], fg=theme['radiobutton_fg'],
                               selectcolor=theme['bg'])
            elif isinstance(widget, tk.Spinbox):
                widget.configure(bg=theme['spinbox_bg'], fg=theme['spinbox_fg'],
                               readonlybackground=theme['spinbox_bg'])
            elif isinstance(widget, ttk.Combobox):
                style = ttk.Style()
                style.theme_use('clam')
                style.configure("TCombobox",
                              fieldbackground=theme['entry_bg'],
                              background=theme['entry_bg'],
                              foreground=theme['entry_fg'])
                widget.configure(background=theme['entry_bg'], foreground=theme['entry_fg'])
            elif isinstance(widget, tk.Text):
                widget.configure(bg=theme['log_bg'], fg=theme['log_fg'])
            elif isinstance(widget, tk.Listbox):
                widget.configure(bg=theme['entry_bg'], fg=theme['entry_fg'])
            elif isinstance(widget, tk.Entry):
                widget.configure(bg=theme['entry_bg'], fg=theme['entry_fg'])
                
            for child in widget.winfo_children():
                self._apply_theme_to_widgets(child, theme)
                
        except Exception as e:
            pass
            
    def toggle_theme(self, theme_value):
        if theme_value != self.current_theme:
            self.current_theme = theme_value
            self.apply_theme()
            
    def clear_log_event(self, event=None):
        self.clear_log()
        return "break"
        
    def create_widgets(self):
        main_frame = tk.Frame(self.root, bg='#f5f0e8')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        title_frame = tk.Frame(main_frame, bg='#f5f0e8')
        title_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.title_label = tk.Label(title_frame, text="🎬 操作录制回放工具", 
                                    font=('Arial', 20, 'bold'), 
                                    fg='#4a7c59', bg='#f5f0e8')
        self.title_label.pack(side=tk.LEFT)
        
        right_frame = tk.Frame(title_frame, bg='#f5f0e8')
        right_frame.pack(side=tk.RIGHT)
        
        tk.Label(right_frame, text="位置:", fg='#3c3c3c', bg='#f5f0e8',
                font=('Arial', 9)).pack(side=tk.LEFT, padx=5)
        
        self.pos_var = tk.StringVar(value="center")
        center_rb = tk.Radiobutton(right_frame, text="📍 居中", 
                                  variable=self.pos_var, value="center",
                                  command=self.toggle_window_position,
                                  fg='#3c3c3c', bg='#f5f0e8',
                                  selectcolor='#d4c9b8', activebackground='#f5f0e8')
        center_rb.pack(side=tk.LEFT, padx=2)
        
        corner_rb = tk.Radiobutton(right_frame, text="📌 右下", 
                                  variable=self.pos_var, value="corner",
                                  command=self.toggle_window_position,
                                  fg='#3c3c3c', bg='#f5f0e8',
                                  selectcolor='#d4c9b8', activebackground='#f5f0e8')
        corner_rb.pack(side=tk.LEFT, padx=2)
        
        tk.Frame(right_frame, width=1, bg='#d4c9b8').pack(side=tk.LEFT, padx=5, fill=tk.Y, pady=2)
        
        tk.Label(right_frame, text="主题:", fg='#3c3c3c', bg='#f5f0e8',
                font=('Arial', 9)).pack(side=tk.LEFT, padx=5)
        
        self.theme_var = tk.StringVar(value="light")
        dark_rb = tk.Radiobutton(right_frame, text="🌙 深色", 
                                variable=self.theme_var, value="dark",
                                command=lambda: self.toggle_theme("dark"),
                                fg='#3c3c3c', bg='#f5f0e8',
                                selectcolor='#d4c9b8', activebackground='#f5f0e8')
        dark_rb.pack(side=tk.LEFT, padx=2)
        
        light_rb = tk.Radiobutton(right_frame, text="☀️ 护眼", 
                                 variable=self.theme_var, value="light",
                                 command=lambda: self.toggle_theme("light"),
                                 fg='#3c3c3c', bg='#f5f0e8',
                                 selectcolor='#d4c9b8', activebackground='#f5f0e8')
        light_rb.pack(side=tk.LEFT, padx=2)
        
        control_frame = tk.Frame(main_frame, bg='#f5f0e8')
        control_frame.pack(fill=tk.X, pady=5)
        
        record_group = tk.LabelFrame(control_frame, text="📹 录制控制", 
                                     fg='#3c3c3c', bg='#f5f0e8')
        record_group.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        btn_frame = tk.Frame(record_group, bg='#f5f0e8')
        btn_frame.pack(pady=5)
        
        self.btn_record = tk.Button(btn_frame, text="🔴 开始录制 (F9)", 
                                   command=self.start_recording,
                                   bg='#d32f2f', fg='white',
                                   font=('Arial', 10, 'bold'), padx=12, pady=5,
                                   width=13)
        self.btn_record.pack(side=tk.LEFT, padx=2)
        
        self.btn_stop = tk.Button(btn_frame, text="⏹️ 停止 (F10)", 
                                  command=self.stop_recording,
                                  bg='#9e9e9e', fg='white',
                                  font=('Arial', 10, 'bold'), padx=12, pady=5,
                                  state=tk.DISABLED, width=11)
        self.btn_stop.pack(side=tk.LEFT, padx=2)
        
        self.btn_pause = tk.Button(btn_frame, text="⏸️ 暂停 (F11)", 
                                   command=self.toggle_pause,
                                   bg='#f57c00', fg='white',
                                   font=('Arial', 10, 'bold'), padx=12, pady=5,
                                   state=tk.DISABLED, width=11)
        self.btn_pause.pack(side=tk.LEFT, padx=2)
        
        self.timer_label = tk.Label(btn_frame, text="⏱️ 00:00:00", 
                                   fg='#4a7c59', bg='#f5f0e8',
                                   font=('Arial', 12, 'bold'))
        self.timer_label.pack(side=tk.LEFT, padx=8)
        
        play_group = tk.LabelFrame(control_frame, text="▶️ 回放控制", 
                                   fg='#3c3c3c', bg='#f5f0e8')
        play_group.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        play_btn_frame = tk.Frame(play_group, bg='#f5f0e8')
        play_btn_frame.pack(pady=5)
        
        self.btn_play = tk.Button(play_btn_frame, text="▶️ 回放", 
                                 command=self.start_playback,
                                 bg='#2e7d32', fg='white',
                                 font=('Arial', 10, 'bold'), padx=12, pady=5,
                                 state=tk.DISABLED, width=13)
        self.btn_play.pack(side=tk.LEFT, padx=2)
        
        self.btn_stop_play = tk.Button(play_btn_frame, text="⏹️ 停止", 
                                       command=self.stop_playback,
                                       bg='#9e9e9e', fg='white',
                                       font=('Arial', 10, 'bold'), padx=12, pady=5,
                                       state=tk.DISABLED, width=11)
        self.btn_stop_play.pack(side=tk.LEFT, padx=2)
        
        self.progress_var = tk.DoubleVar()
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TProgressbar", 
                       background='#5d8a5e',
                       troughcolor='#d4c9b8',
                       thickness=10)
        self.progress_bar = ttk.Progressbar(play_group, variable=self.progress_var,
                                           maximum=100, length=160)
        self.progress_bar.pack(side=tk.RIGHT, padx=10, pady=5)
        
        settings_frame = tk.Frame(main_frame, bg='#f5f0e8')
        settings_frame.pack(fill=tk.X, pady=3)
        
        row1 = tk.Frame(settings_frame, bg='#f5f0e8')
        row1.pack(fill=tk.X, pady=2)
        
        tk.Label(row1, text="速度:", fg='#3c3c3c', bg='#f5f0e8',
                font=('Arial', 9)).pack(side=tk.LEFT, padx=(10, 3))
        
        self.speed_var = tk.StringVar(value="1.0")
        speed_spin = tk.Spinbox(row1, from_=0.1, to=5.0, increment=0.1,
                                textvariable=self.speed_var, width=4,
                                bg='#ffffff', fg='#2c2c2c', relief=tk.FLAT,
                                font=('Arial', 9))
        speed_spin.pack(side=tk.LEFT, padx=2)
        
        tk.Label(row1, text="循环:", fg='#3c3c3c', bg='#f5f0e8',
                font=('Arial', 9)).pack(side=tk.LEFT, padx=(15, 3))
        
        self.loop_count_var = tk.StringVar(value="1")
        loop_spin = tk.Spinbox(row1, from_=0, to=999, increment=1,
                               textvariable=self.loop_count_var, width=4,
                               bg='#ffffff', fg='#2c2c2c', relief=tk.FLAT,
                               font=('Arial', 9))
        loop_spin.pack(side=tk.LEFT, padx=2)
        
        tk.Label(row1, text="(0=无限)", fg='#888', bg='#f5f0e8',
                font=('Arial', 8)).pack(side=tk.LEFT, padx=2)
        
        self.minimize_var = tk.BooleanVar(value=False)
        tk.Checkbutton(row1, text="⬇️ 回放时最小化", 
                      variable=self.minimize_var,
                      fg='#3c3c3c', bg='#f5f0e8',
                      selectcolor='#d4c9b8').pack(side=tk.LEFT, padx=15)
        
        self.record_mouse_var = tk.BooleanVar(value=True)
        tk.Checkbutton(row1, text="🖱️ 鼠标", 
                      variable=self.record_mouse_var,
                      fg='#3c3c3c', bg='#f5f0e8',
                      selectcolor='#d4c9b8').pack(side=tk.LEFT, padx=10)
        
        self.record_keyboard_var = tk.BooleanVar(value=True)
        tk.Checkbutton(row1, text="⌨️ 键盘", 
                      variable=self.record_keyboard_var,
                      fg='#3c3c3c', bg='#f5f0e8',
                      selectcolor='#d4c9b8').pack(side=tk.LEFT, padx=10)
        
        info_frame = tk.LabelFrame(main_frame, text="📊 实时信息", 
                                   fg='#3c3c3c', bg='#f5f0e8')
        info_frame.pack(fill=tk.X, pady=5)
        
        info_grid = tk.Frame(info_frame, bg='#f5f0e8')
        info_grid.pack(fill=tk.X, padx=5, pady=5)
        
        self.mouse_pos_label = tk.Label(info_grid, text="🖱️ 位置: (0, 0)", 
                                       fg='#5d8a5e', bg='#f5f0e8',
                                       font=('Consolas', 10))
        self.mouse_pos_label.grid(row=0, column=0, padx=10, sticky='w')
        
        self.stats_label = tk.Label(info_grid, text="📝 操作: 0", 
                                   fg='#5d8a5e', bg='#f5f0e8',
                                   font=('Consolas', 10))
        self.stats_label.grid(row=0, column=1, padx=10, sticky='w')
        
        self.duration_label = tk.Label(info_grid, text="⏱️ 时长: 00:00:00", 
                                      fg='#5d8a5e', bg='#f5f0e8',
                                      font=('Consolas', 10))
        self.duration_label.grid(row=0, column=2, padx=10, sticky='w')
        
        self.loop_info_label = tk.Label(info_grid, text="🔄 循环: 0/1", 
                                       fg='#f57c00', bg='#f5f0e8',
                                       font=('Consolas', 10))
        self.loop_info_label.grid(row=0, column=3, padx=10, sticky='w')
        
        log_frame = tk.LabelFrame(main_frame, text="📋 日志信息 (右键菜单 / Ctrl+L清空)", 
                                  fg='#3c3c3c', bg='#f5f0e8')
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        log_toolbar = tk.Frame(log_frame, bg='#f5f0e8')
        log_toolbar.pack(fill=tk.X, padx=5, pady=2)
        
        tk.Label(log_toolbar, text="💡 Ctrl+L 清空日志", 
                fg='#888', bg='#f5f0e8', font=('Arial', 9)).pack(side=tk.LEFT, padx=5)
        
        tk.Button(log_toolbar, text="🗑️ 清空日志", 
                 command=self.clear_log,
                 bg='#d4c9b8', fg='#2c2c2c', font=('Arial', 9),
                 activebackground='#c4b9a8', activeforeground='#2c2c2c').pack(side=tk.RIGHT, padx=2)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=12,
                                                  bg='#faf8f5', fg='#2c2c2c',
                                                  font=('Consolas', 10),
                                                  insertbackground='#2c2c2c')
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_text.tag_config('info', foreground='#4a7c59')
        self.log_text.tag_config('success', foreground='#2e7d32')
        self.log_text.tag_config('error', foreground='#c62828')
        self.log_text.tag_config('warning', foreground='#e65100')
        self.log_text.tag_config('recording', foreground='#c62828')
        self.log_text.tag_config('mouse', foreground='#6a1b9a')
        self.log_text.tag_config('keyboard', foreground='#0d47a1')
        
        self.log_menu = tk.Menu(self.root, tearoff=0, bg='#f5f0e8', fg='#2c2c2c')
        self.log_menu.add_command(label="🗑️ 清空日志 (Ctrl+L)", command=self.clear_log)
        self.log_menu.add_separator()
        self.log_menu.add_command(label="📋 复制选中", command=self.copy_log)
        self.log_menu.add_command(label="📋 复制全部", command=self.copy_all_log)
        self.log_menu.add_separator()
        self.log_menu.add_command(label="🔍 查找", command=self.find_in_log)
        
        self.log_text.bind("<Button-3>", self.show_log_menu)
        self.log_text.bind("<Control-c>", lambda e: self.copy_log())
        
        bottom_frame = tk.Frame(main_frame, bg='#f5f0e8')
        bottom_frame.pack(fill=tk.X, pady=5)
        
        self.btn_load = tk.Button(bottom_frame, text="📂 加载录制", 
                                 command=self.load_recording,
                                 bg='#d4c9b8', fg='#2c2c2c',
                                 font=('Arial', 9), padx=10)
        self.btn_load.pack(side=tk.LEFT, padx=2)
        
        self.btn_save = tk.Button(bottom_frame, text="💾 保存录制", 
                                 command=self.save_recording,
                                 bg='#d4c9b8', fg='#2c2c2c',
                                 font=('Arial', 9), padx=10)
        self.btn_save.pack(side=tk.LEFT, padx=2)
        
        self.btn_test = tk.Button(bottom_frame, text="🧪 测试数据", 
                                 command=self.test_data,
                                 bg='#4a7c59', fg='white',
                                 font=('Arial', 9), padx=10)
        self.btn_test.pack(side=tk.LEFT, padx=2)
        
        self.btn_clear = tk.Button(bottom_frame, text="🗑️ 清空录制", 
                                  command=self.clear_recording,
                                  bg='#d4c9b8', fg='#2c2c2c',
                                  font=('Arial', 9), padx=10)
        self.btn_clear.pack(side=tk.LEFT, padx=2)
        
        self.btn_stats = tk.Button(bottom_frame, text="📊 统计", 
                                  command=self.show_stats,
                                  bg='#d4c9b8', fg='#2c2c2c',
                                  font=('Arial', 9), padx=10)
        self.btn_stats.pack(side=tk.LEFT, padx=2)
        
        status_frame = tk.Frame(self.root, bg='#e8e0d5', height=30)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_label = tk.Label(status_frame, text="就绪 ✅", 
                                    fg='#2e7d32', bg='#e8e0d5',
                                    font=('Arial', 9))
        self.status_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        self.info_label = tk.Label(status_frame, text="", 
                                  fg='#888', bg='#e8e0d5',
                                  font=('Arial', 9))
        self.info_label.pack(side=tk.RIGHT, padx=10, pady=5)
        
        admin_text = "🛡️ 管理员" if self.is_admin() else "⚠️ 普通用户"
        admin_color = '#2e7d32' if self.is_admin() else '#e65100'
        self.admin_label = tk.Label(status_frame, text=admin_text, fg=admin_color, 
                                    bg='#e8e0d5', font=('Arial', 9))
        self.admin_label.pack(side=tk.RIGHT, padx=10, pady=5)
        
        self.apply_theme()
        
    def show_log_menu(self, event):
        try:
            self.log_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.log_menu.grab_release()
            
    def clear_log(self):
        self.log_text.delete(1.0, tk.END)
        self.update_status("日志已清空", 'orange')
        self.root.after(2000, lambda: self.update_status("就绪 ✅", 'green'))
        
    def copy_log(self):
        try:
            selected = self.log_text.get(tk.SEL_FIRST, tk.SEL_LAST)
            if selected.strip():
                self.root.clipboard_clear()
                self.root.clipboard_append(selected)
                self.update_status("已复制选中内容", 'green')
                self.root.after(2000, lambda: self.update_status("就绪 ✅", 'green'))
            else:
                self.update_status("没有选中内容", 'orange')
                self.root.after(2000, lambda: self.update_status("就绪 ✅", 'green'))
        except tk.TclError:
            self.update_status("没有选中内容", 'orange')
            self.root.after(2000, lambda: self.update_status("就绪 ✅", 'green'))
            
    def copy_all_log(self):
        content = self.log_text.get(1.0, tk.END)
        if content.strip():
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.update_status("已复制全部日志", 'green')
            self.root.after(2000, lambda: self.update_status("就绪 ✅", 'green'))
        else:
            self.update_status("日志为空", 'orange')
            self.root.after(2000, lambda: self.update_status("就绪 ✅", 'green'))
            
    def find_in_log(self):
        find_window = tk.Toplevel(self.root)
        find_window.title("查找")
        find_window.geometry("350x120")
        find_window.configure(bg='#f5f0e8')
        find_window.resizable(False, False)
        find_window.transient(self.root)
        find_window.grab_set()
        
        tk.Label(find_window, text="查找内容:", fg='#3c3c3c', bg='#f5f0e8',
                font=('Arial', 10)).pack(pady=5)
        
        entry_frame = tk.Frame(find_window, bg='#f5f0e8')
        entry_frame.pack(pady=5)
        
        entry = tk.Entry(entry_frame, width=30, bg='#ffffff', fg='#2c2c2c',
                        insertbackground='#2c2c2c', font=('Arial', 10))
        entry.pack(side=tk.LEFT, padx=5)
        entry.focus_set()
        
        def do_find():
            search_text = entry.get()
            if not search_text:
                return
                
            self.log_text.tag_remove('found', '1.0', tk.END)
            
            start = '1.0'
            count = 0
            while True:
                start = self.log_text.search(search_text, start, tk.END, nocase=True)
                if not start:
                    break
                end = f"{start}+{len(search_text)}c"
                self.log_text.tag_add('found', start, end)
                self.log_text.tag_config('found', background='#ffeb3b', foreground='black')
                start = end
                count += 1
                
            if count > 0:
                self.log_text.see('1.0')
                self.update_status(f"找到 {count} 个匹配项", 'green')
                self.root.after(2000, lambda: self.update_status("就绪 ✅", 'green'))
            else:
                self.update_status("未找到匹配项", 'orange')
                self.root.after(2000, lambda: self.update_status("就绪 ✅", 'green'))
                
            find_window.destroy()
            
        tk.Button(entry_frame, text="查找", command=do_find,
                 bg='#4a7c59', fg='white', font=('Arial', 9),
                 padx=15, pady=3).pack(side=tk.LEFT, padx=5)
        
        entry.bind('<Return>', lambda e: do_find())
        find_window.bind('<Escape>', lambda e: find_window.destroy())
        
    def log_message(self, message, tag='info'):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_msg = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, formatted_msg, tag)
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
    def update_status(self, message, color='green'):
        self.status_label.config(text=message, fg=color)
        
    def update_info(self, message):
        self.info_label.config(text=message)
        
    def update_timer(self):
        try:
            if self._closing:
                return
                
            if self.recorder.recording and not self.recorder.paused:
                elapsed = time.time() - self.recorder.start_time
                hours = int(elapsed // 3600)
                minutes = int((elapsed % 3600) // 60)
                seconds = int(elapsed % 60)
                time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                self.timer_label.config(text=f"⏱️ {time_str}")
                self.duration_label.config(text=f"⏱️ 时长: {time_str}")
                
            x, y = pyautogui.position()
            self.mouse_pos_label.config(text=f"🖱️ 位置: ({x}, {y})")
            
            if self.recorder.actions:
                self.stats_label.config(text=f"📝 操作: {len(self.recorder.actions)}")
                
        except:
            pass
            
        if not self._closing:
            self.root.after(500, self.update_timer)
        
    def start_recording(self):
        if self.recorder.recording:
            return
            
        self.recorder.actions = []
        self.recorder.start_time = time.time()
        self.recorder.recording = True
        self.recorder.paused = False
        
        self.btn_record.config(state=tk.DISABLED, bg='#b71c1c')
        self.btn_stop.config(state=tk.NORMAL, bg='#c62828')
        self.btn_pause.config(state=tk.NORMAL, bg='#f57c00')
        self.btn_play.config(state=tk.DISABLED)
        self.progress_var.set(0)
        
        self.update_status("正在录制 🔴", 'red')
        self.log_message("🔴 开始录制... (按F10停止)", 'recording')
        
        self.recording_thread = threading.Thread(target=self.record_loop, daemon=True)
        self.recording_thread.start()
        
    def record_loop(self):
        try:
            keyboard.on_press(self.on_key_press)
            keyboard.on_release(self.on_key_release)
            
            while self.recorder.recording and not self._closing:
                if not self.recorder.paused:
                    x, y = pyautogui.position()
                    self.detect_mouse_clicks(x, y)
                time.sleep(0.01)
                
        except Exception as e:
            if not self._closing:
                self.log_message(f"❌ 录制错误: {e}", 'error')
        finally:
            keyboard.unhook_all()
            
    def detect_mouse_clicks(self, x, y):
        try:
            if not self.record_mouse_var.get():
                return
                
            if win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000:
                if not getattr(self, 'left_down', False):
                    self.left_down = True
                    self.recorder.record_action('mouse_down', {'x': x, 'y': y, 'button': 'left'})
                    self.log_message(f"🖱️ 左键按下: ({x}, {y})", 'mouse')
            else:
                if getattr(self, 'left_down', False):
                    self.left_down = False
                    self.recorder.record_action('mouse_up', {'x': x, 'y': y, 'button': 'left'})
                    self.log_message(f"🖱️ 左键释放: ({x}, {y})", 'mouse')
                    
            if win32api.GetAsyncKeyState(win32con.VK_RBUTTON) & 0x8000:
                if not getattr(self, 'right_down', False):
                    self.right_down = True
                    self.recorder.record_action('mouse_down', {'x': x, 'y': y, 'button': 'right'})
                    self.log_message(f"🖱️ 右键按下: ({x}, {y})", 'mouse')
            else:
                if getattr(self, 'right_down', False):
                    self.right_down = False
                    self.recorder.record_action('mouse_up', {'x': x, 'y': y, 'button': 'right'})
                    self.log_message(f"🖱️ 右键释放: ({x}, {y})", 'mouse')
                    
        except:
            pass
            
    def on_key_press(self, event):
        if not self.recorder.recording or self.recorder.paused:
            return
        if event.name in ['f9', 'f10', 'f11']:
            return
        if not self.record_keyboard_var.get():
            return
            
        self.recorder.record_action('key_down', {'key': event.name})
        if len(self.recorder.actions) % 20 == 0:
            self.log_message(f"⌨️ 已记录 {len(self.recorder.actions)} 个按键", 'keyboard')
        
    def on_key_release(self, event):
        if not self.recorder.recording or self.recorder.paused:
            return
        if event.name in ['f9', 'f10', 'f11']:
            return
        if not self.record_keyboard_var.get():
            return
            
        self.recorder.record_action('key_up', {'key': event.name})
        
    def stop_recording(self):
        if not self.recorder.recording:
            return
            
        self.recorder.recording = False
        self.recorder.paused = False
        
        self.btn_record.config(state=tk.NORMAL, bg='#d32f2f')
        self.btn_stop.config(state=tk.DISABLED, bg='#9e9e9e')
        self.btn_pause.config(state=tk.DISABLED, bg='#f57c00', text="⏸️ 暂停 (F11)")
        
        if self.recorder.actions:
            self.btn_play.config(state=tk.NORMAL)
            total_time = self.recorder.actions[-1]['time']
            self.log_message(f"📊 录制时长: {total_time:.2f} 秒", 'info')
            self.auto_save_recording()
            
        self.update_status("录制已停止 ⏹️", 'orange')
        self.log_message(f"⏹️ 录制停止! 共 {len(self.recorder.actions)} 个操作", 'success')
        
    def auto_save_recording(self):
        if not self.recorder.actions:
            return
            
        now = datetime.now()
        time_str = now.strftime("%Y-%m-%d-%H-%M-%S")
        filename = f"录制动作_{time_str}.json"
        
        file_path = os.path.join(os.getcwd(), filename)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.recorder.actions, f, ensure_ascii=False, indent=2)
            self.log_message(f"💾 自动保存: {filename}", 'success')
        except Exception as e:
            self.log_message(f"❌ 自动保存失败: {e}", 'error')
        
    def toggle_pause(self):
        if not self.recorder.recording:
            return
            
        self.recorder.paused = not self.recorder.paused
        if self.recorder.paused:
            self.btn_pause.config(text="▶️ 继续 (F11)", bg='#2e7d32')
            self.update_status("已暂停 ⏸️", 'orange')
            self.log_message("⏸️ 录制暂停", 'warning')
        else:
            self.btn_pause.config(text="⏸️ 暂停 (F11)", bg='#f57c00')
            self.update_status("正在录制 🔴", 'red')
            self.log_message("▶️ 录制继续", 'info')
            
    def start_playback(self):
        if not self.recorder.actions or self.recorder.playing:
            return
            
        try:
            self.loop_count = int(self.loop_count_var.get())
            if self.loop_count < 0:
                self.loop_count = 0
        except:
            self.loop_count = 1
            
        self.current_loop = 0
        self.recorder.playing = True
        self.recorder.play_speed = float(self.speed_var.get())
        
        self.btn_play.config(state=tk.DISABLED, bg='#1b5e20')
        self.btn_stop_play.config(state=tk.NORMAL, bg='#c62828')
        self.btn_record.config(state=tk.DISABLED)
        self.progress_var.set(0)
        
        if self.minimize_var.get():
            self.was_minimized = True
            self.root.iconify()
            self.log_message("⬇️ 窗口已最小化", 'info')
        else:
            self.was_minimized = False
        
        self.update_status("正在回放 ▶️", 'green')
        total_actions = len(self.recorder.actions)
        total_time = self.recorder.actions[-1]['time']
        
        loop_text = "无限循环" if self.loop_count == 0 else f"循环{self.loop_count}次"
        self.log_message(f"▶️ 回放开始 (速度: {self.recorder.play_speed}x, {loop_text})", 'info')
        self.log_message(f"📊 {total_actions}个操作, 原始时长: {total_time:.2f}秒", 'info')
        
        self.loop_info_label.config(text=f"🔄 循环: 0/{self.loop_count if self.loop_count > 0 else '∞'}")
        
        self.tray.update_progress(0, "回放中")
        
        self.play_thread = threading.Thread(target=self.play_loop, daemon=True)
        self.play_thread.start()
        
    def play_loop(self):
        try:
            actions = self.recorder.actions
            if not actions:
                return
                
            total = len(actions)
            base_time = actions[0]['time']
            
            loop_index = 0
            total_success = 0
            total_actions_executed = 0
            
            while self.recorder.playing and not self._closing:
                if self.loop_count > 0 and loop_index >= self.loop_count:
                    self.log_message(f"✅ 已完成 {self.loop_count} 次循环", 'success')
                    self.tray.update_progress(100, "完成")
                    break
                    
                self.current_loop = loop_index + 1
                display_loop = f"{self.current_loop}/{self.loop_count if self.loop_count > 0 else '∞'}"
                self.loop_info_label.config(text=f"🔄 循环: {display_loop}")
                
                if loop_index > 0:
                    self.log_message(f"🔄 开始第 {self.current_loop} 次循环", 'info')
                
                start_time = time.time()
                success_count = 0
                
                for i, action in enumerate(actions):
                    if not self.recorder.playing or self._closing:
                        break
                    
                    target_elapsed = (action['time'] - base_time) / self.recorder.play_speed
                    actual_elapsed = time.time() - start_time
                    
                    if target_elapsed > actual_elapsed:
                        sleep_time = target_elapsed - actual_elapsed
                        if sleep_time > 0.001:
                            time.sleep(sleep_time)
                    
                    success = self.recorder.execute_action(action)
                    if success:
                        success_count += 1
                        total_success += 1
                    
                    total_actions_executed += 1
                    
                    progress = ((i + 1) / total) * 100
                    self.progress_var.set(progress)
                    self.root.update_idletasks()
                    
                    self.tray.update_progress(progress, f"第{self.current_loop}次")
                    
                    if (i + 1) % 20 == 0 or (i + 1) == total:
                        elapsed = time.time() - start_time
                        self.log_message(f"📊 第{self.current_loop}次: {progress:.1f}% ({i+1}/{total})", 'info')
                
                actual_time = time.time() - start_time
                expected_time = (actions[-1]['time'] - actions[0]['time']) / self.recorder.play_speed
                
                self.log_message(f"📊 第{self.current_loop}次完成: 成功{success_count}/{total}, 用时{actual_time:.2f}s", 'info')
                
                if abs(actual_time - expected_time) > 0.5:
                    self.log_message(f"⚠️ 时间偏差: {abs(actual_time - expected_time):.2f}s", 'warning')
                
                loop_index += 1
                
                if self.loop_count > 0 and loop_index >= self.loop_count:
                    self.tray.update_progress(100, "完成")
                    break
                    
                if self.recorder.playing and not self._closing and (self.loop_count == 0 or loop_index < self.loop_count):
                    time.sleep(0.3)
            
            if self.recorder.playing and not self._closing:
                self.log_message(f"✅ 全部完成! 共执行 {total_actions_executed} 个操作, 成功 {total_success} 次", 'success')
                self.log_message(f"🔄 共循环 {self.current_loop} 次", 'info')
                self.tray.update_progress(100, "完成")
            
        except Exception as e:
            if not self._closing:
                self.log_message(f"❌ 回放错误: {e}", 'error')
                self.tray.update_progress(0, "错误")
        finally:
            self.stop_playback()
            
    def stop_playback(self):
        self.recorder.playing = False
        
        if self.was_minimized:
            try:
                self.root.deiconify()
            except:
                pass
            self.was_minimized = False
            self.log_message("⬆️ 窗口已恢复", 'info')
        
        try:
            self.btn_play.config(state=tk.NORMAL, bg='#2e7d32')
            self.btn_stop_play.config(state=tk.DISABLED, bg='#9e9e9e')
            self.btn_record.config(state=tk.NORMAL)
            self.progress_var.set(0)
        except:
            pass
        
        self.tray.update_progress(0, "就绪")
        
        self.update_status("回放已停止 ⏹️", 'orange')
        self.log_message("⏹️ 回放停止", 'success')
        
    def test_data(self):
        test_actions = [
            {'type': 'mouse_down', 'time': 0.2, 'x': 500, 'y': 300, 'button': 'left'},
            {'type': 'mouse_up', 'time': 0.5, 'x': 500, 'y': 300, 'button': 'left'},
            {'type': 'key_down', 'time': 0.8, 'key': 'a'},
            {'type': 'key_up', 'time': 1.0, 'key': 'a'},
            {'type': 'mouse_down', 'time': 1.3, 'x': 600, 'y': 400, 'button': 'right'},
            {'type': 'mouse_up', 'time': 1.6, 'x': 600, 'y': 400, 'button': 'right'},
            {'type': 'key_down', 'time': 1.9, 'key': 'b'},
            {'type': 'key_up', 'time': 2.1, 'key': 'b'},
        ]
        self.recorder.actions = test_actions
        self.btn_play.config(state=tk.NORMAL)
        total_time = test_actions[-1]['time']
        self.log_message("🧪 测试数据已加载 (8个操作)", 'success')
        self.log_message(f"⏱️ 总时长: {total_time:.2f}秒", 'info')
        self.log_message("💡 循环次数设为3可测试循环功能", 'info')
        
    def save_recording(self):
        if not self.recorder.actions:
            self.log_message("⚠️ 没有数据可保存", 'warning')
            return
            
        now = datetime.now()
        time_str = now.strftime("%Y-%m-%d-%H-%M-%S")
        default_name = f"录制动作_{time_str}.json"
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=default_name
        )
        
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.recorder.actions, f, ensure_ascii=False, indent=2)
            self.log_message(f"💾 保存成功: {os.path.basename(file_path)}", 'success')
            
    def load_recording(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.recorder.actions = json.load(f)
                self.btn_play.config(state=tk.NORMAL)
                total_time = self.recorder.actions[-1]['time'] - self.recorder.actions[0]['time'] if len(self.recorder.actions) > 1 else 0
                self.log_message(f"📂 加载成功: {os.path.basename(file_path)}", 'success')
                self.log_message(f"📊 {len(self.recorder.actions)}个操作, 时长: {total_time:.2f}秒", 'info')
            except Exception as e:
                self.log_message(f"❌ 加载失败: {e}", 'error')
            
    def clear_recording(self):
        if messagebox.askyesno("确认", "确定要清空所有录制数据吗？"):
            self.recorder.actions = []
            self.btn_play.config(state=tk.DISABLED)
            self.progress_var.set(0)
            self.loop_info_label.config(text="🔄 循环: 0/1")
            self.log_message("🗑️ 已清空录制数据", 'warning')
            
    def show_stats(self):
        if not self.recorder.actions:
            messagebox.showinfo("统计信息", "没有录制数据")
            return
            
        actions = self.recorder.actions
        mouse_downs = sum(1 for a in actions if a['type'] == 'mouse_down')
        mouse_ups = sum(1 for a in actions if a['type'] == 'mouse_up')
        key_downs = sum(1 for a in actions if a['type'] == 'key_down')
        key_ups = sum(1 for a in actions if a['type'] == 'key_up')
        total_duration = actions[-1]['time'] - actions[0]['time'] if len(actions) > 1 else 0
        
        stats_text = f"""📊 统计信息

📝 总操作数: {len(actions)}
🖱️ 鼠标按下: {mouse_downs}
🖱️ 鼠标释放: {mouse_ups}
⌨️ 键盘按下: {key_downs}
⌨️ 键盘释放: {key_ups}
⏱️ 录制时长: {total_duration:.2f} 秒
"""
        messagebox.showinfo("统计信息", stats_text)
        
    def on_closing(self):
        """点击关闭按钮 - 弹出确认对话框"""
        if self.recorder.recording or self.recorder.playing:
            msg = "正在录制或回放中，确定要退出吗？\n\n未保存的录制数据将丢失！"
            if not messagebox.askyesno("确认退出", msg, icon='warning'):
                return
        else:
            if not messagebox.askyesno("确认退出", "确定要退出程序吗？"):
                return
        
        self.quit_app()
        
    def quit_app(self):
        """完全退出应用 - 彻底清理托盘图标"""
        if self._closing:
            return
            
        self._closing = True
        
        # 1. 停止所有录制和回放
        self.recorder.recording = False
        self.recorder.playing = False
        self.recorder.paused = False
        
        # 2. 取消所有键盘钩子
        try:
            keyboard.unhook_all()
        except:
            pass
        
        # 3. 停止托盘图标（彻底移除）
        try:
            self.tray.stop()
        except:
            pass
        
        # 4. 延迟一下让托盘图标完全移除
        time.sleep(0.2)
        
        # 5. 销毁窗口
        try:
            self.root.destroy()
        except:
            pass
        
        # 6. 强制刷新系统托盘
        try:
            # 发送消息刷新托盘
            hwnd = win32gui.FindWindow("Shell_TrayWnd", None)
            if hwnd:
                win32gui.PostMessage(hwnd, win32con.WM_COMMAND, 0x1F5, 0)
        except:
            pass
        
        # 7. 退出
        sys.exit(0)

def main():
    try:
        import pyautogui, keyboard
        import pystray
        from PIL import Image, ImageDraw
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("请运行: pip install pyautogui keyboard pystray pillow")
        input("按任意键退出...")
        sys.exit(1)
        
    root = tk.Tk()
    app = SimpleRecorderGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()