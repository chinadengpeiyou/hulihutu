# -*- coding: utf-8 -*-

"""
Python 程序打包工具 v5.0
主程序入口 - 界面和逻辑分离
俏狐出品 QQ:86074731
"""

import os
import sys

# ==========================================
# 修复 EXE 打包后的导入路径问题
# ==========================================
if getattr(sys, 'frozen', False):
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    if base_path not in sys.path:
        sys.path.insert(0, base_path)
    exe_dir = os.path.dirname(sys.executable)
    if exe_dir not in sys.path:
        sys.path.insert(0, exe_dir)
    try:
        os.chdir(exe_dir)
    except Exception:
        pass

import multiprocessing
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import time

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    print("警告: tkinterdnd2 未安装，拖放功能将不可用")
    class TkinterDnD:
        class Tk(tk.Tk):
            pass
    DND_FILES = None

# 导入核心逻辑
from builder_core import PyBuilderCore


class PyBuilderGUI:
    """打包工具界面类"""
    
    def __init__(self, root):
        self.root = root
        
        if not getattr(sys, 'frozen', False):
            self.root.withdraw()
        
        self.root.title("Python 程序打包工具 v5.0 (俏狐出品 QQ:86074731)")
        
        self.desktop_path = self.get_desktop_path()
        
        self.source_file = tk.StringVar()
        self.use_venv = tk.BooleanVar(value=True)
        self.delete_venv = tk.BooleanVar(value=True)
        self.use_upx = tk.BooleanVar(value=False)
        self.use_pyarmor = tk.BooleanVar(value=False)
        self.is_building = False
        self.build_thread = None
        self.detected_packages = []
        
        self.output_dir_var = tk.StringVar(value=self.desktop_path)
        
        self.core = PyBuilderCore()
        self.core.set_msg_callback(self.msg_callback)
        
        self.colors = {
            'bg': '#f0f2f5',
            'frame_bg': '#ffffff',
            'title': '#2c3e50',
            'accent': '#3498db',
            'success': '#27ae60',
            'warning': '#f39c12',
            'danger': '#e74c3c',
            'log_bg': '#1e1e2e',
            'log_fg': '#cdd6f4',
            'log_info': '#89b4fa',
            'log_success': '#a6e3a1',
            'log_error': '#f38ba8',
            'log_warning': '#f9e2af',
            'log_build': '#cba6f7',
            'drop_bg': '#e8ebf0',
            'drop_border': '#d5d9e0'
        }
        
        self.setup_ui()
        self.setup_drag_drop()
        self.setup_log_menu()
        self.center_window()
        
        if not getattr(sys, 'frozen', False):
            self.root.deiconify()
    
    def get_desktop_path(self):
        """获取当前用户的桌面路径"""
        try:
            if sys.platform == 'win32':
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
                )
                desktop, _ = winreg.QueryValueEx(key, "Desktop")
                desktop = os.path.expandvars(desktop)
                winreg.CloseKey(key)
                if os.path.exists(desktop):
                    return desktop
        except Exception:
            pass
        
        try:
            desktop = os.environ.get('USERPROFILE') or os.environ.get('HOME')
            if desktop:
                desktop = os.path.join(desktop, 'Desktop')
                if os.path.exists(desktop):
                    return desktop
        except Exception:
            pass
        
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            if os.path.exists(desktop):
                return desktop
        except Exception:
            pass
        
        return os.path.expanduser("~")
    
    def msg_callback(self, msg_type, content, tag='info'):
        if msg_type == 'log':
            self.log(content, tag)
        elif msg_type == 'progress':
            self.update_progress(content['value'], content['status'])
        elif msg_type == 'finish':
            self.is_building = False
            self.build_btn.config(state=tk.NORMAL)
            self.log("✅ 打包流程全部完成！", 'success')
            self.show_build_result()
        elif msg_type == 'error':
            self.is_building = False
            self.build_btn.config(state=tk.NORMAL)
            self.log(f"❌ {content}", 'error')
    
    def center_window(self):
        self.root.update_idletasks()
        width = 920
        height = 820
        x = (self.root.winfo_screenwidth() - width) // 2
        y = (self.root.winfo_screenheight() - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.resizable(True, True)
        self.root.minsize(850, 700)
    
    def setup_ui(self):
        main_frame = tk.Frame(self.root, bg=self.colors['bg'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        title_frame = tk.Frame(main_frame, bg=self.colors['bg'], height=80)
        title_frame.pack(fill=tk.X, pady=(0, 10))
        title_frame.pack_propagate(False)
        
        left_frame = tk.Frame(title_frame, bg=self.colors['bg'])
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        self.drop_frame = tk.Frame(left_frame, bg=self.colors['drop_bg'], height=80, relief=tk.FLAT, bd=0)
        self.drop_frame.pack(fill=tk.BOTH, expand=True)
        self.drop_frame.pack_propagate(False)
        
        border_frame = tk.Frame(self.drop_frame, bg=self.colors['drop_border'], height=1)
        border_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        if DND_FILES:
            self.drop_frame.drop_target_register(DND_FILES)
            self.drop_frame.dnd_bind('<<Drop>>', self.on_drop_file)
        
        self.drop_label = tk.Label(
            self.drop_frame,
            text="📂 拖放 .py 或 .pyw 文件到此处",
            bg=self.colors['drop_bg'],
            fg='#4a5568',
            font=('微软雅黑', 14, 'bold'),
            cursor='hand2'
        )
        self.drop_label.pack(expand=True)
        
        if DND_FILES:
            self.drop_label.drop_target_register(DND_FILES)
            self.drop_label.dnd_bind('<<Drop>>', self.on_drop_file)
        
        right_frame = tk.Frame(title_frame, bg=self.colors['bg'], width=280)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)
        right_frame.pack_propagate(False)
        
        title_inner = tk.Frame(right_frame, bg=self.colors['bg'])
        title_inner.pack(expand=True)
        
        title_label = tk.Label(title_inner, text="🐍 Python 程序打包工具", font=('微软雅黑', 18, 'bold'),
                               fg=self.colors['title'], bg=self.colors['bg'])
        title_label.pack()
        
        version_label = tk.Label(title_inner, text="v5.0 (俏狐出品 QQ:86074731)",
                                 font=('微软雅黑', 10), fg='#95a5a6', bg=self.colors['bg'])
        version_label.pack()
        
        path_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        path_frame.pack(fill=tk.X, pady=(0, 8))
        
        tk.Label(path_frame, text="文件路径:", font=('微软雅黑', 9), bg=self.colors['bg'], fg='#555').pack(side=tk.LEFT, padx=(0, 5))
        
        self.file_entry = tk.Entry(path_frame, textvariable=self.source_file, font=('Consolas', 9),
                                   bg='#f8f9fa', relief=tk.FLAT, bd=1)
        self.file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        if DND_FILES:
            self.file_entry.drop_target_register(DND_FILES)
            self.file_entry.dnd_bind('<<Drop>>', self.on_drop_file)
        
        tk.Button(path_frame, text="📁 浏览", command=self.browse_file, font=('微软雅黑', 9),
                  bg=self.colors['accent'], fg='white', relief=tk.FLAT, padx=10, pady=2, cursor='hand2').pack(side=tk.LEFT, padx=2)
        tk.Button(path_frame, text="✕ 清空", command=self.clear_file, font=('微软雅黑', 9),
                  bg='#95a5a6', fg='white', relief=tk.FLAT, padx=10, pady=2, cursor='hand2').pack(side=tk.LEFT, padx=2)
        
        dep_frame = tk.Frame(main_frame, bg=self.colors['frame_bg'], relief=tk.FLAT, bd=1)
        dep_frame.pack(fill=tk.X, pady=(0, 8))
        
        dep_inner = tk.Frame(dep_frame, bg=self.colors['frame_bg'])
        dep_inner.pack(fill=tk.X, padx=10, pady=6)
        
        dep_row1 = tk.Frame(dep_inner, bg=self.colors['frame_bg'])
        dep_row1.pack(fill=tk.X, pady=2)
        
        tk.Label(dep_row1, text="📦 依赖列表 (每行一个包名，可编辑):", font=('微软雅黑', 9),
                 bg=self.colors['frame_bg'], fg='#555').pack(side=tk.LEFT, padx=(0, 10))
        
        tk.Button(dep_row1, text="🔍 自动扫描", command=self.scan_dependencies, font=('微软雅黑', 9),
                  bg='#3498db', fg='white', relief=tk.FLAT, padx=10, pady=2, cursor='hand2').pack(side=tk.LEFT, padx=2)
        tk.Button(dep_row1, text="➕ 添加", command=self.add_package, font=('微软雅黑', 9),
                  bg='#27ae60', fg='white', relief=tk.FLAT, padx=10, pady=2, cursor='hand2').pack(side=tk.LEFT, padx=2)
        tk.Button(dep_row1, text="🗑️ 删除选中", command=self.delete_selected_package, font=('微软雅黑', 9),
                  bg='#e74c3c', fg='white', relief=tk.FLAT, padx=10, pady=2, cursor='hand2').pack(side=tk.LEFT, padx=2)
        tk.Button(dep_row1, text="🧹 清空", command=self.clear_packages, font=('微软雅黑', 9),
                  bg='#95a5a6', fg='white', relief=tk.FLAT, padx=10, pady=2, cursor='hand2').pack(side=tk.LEFT, padx=2)
        
        dep_row2 = tk.Frame(dep_inner, bg=self.colors['frame_bg'])
        dep_row2.pack(fill=tk.X, pady=2)
        
        self.dep_text = scrolledtext.ScrolledText(dep_row2, height=3, font=('Consolas', 9),
                                                   bg='#f8f9fa', fg='#2c3e50', relief=tk.FLAT, bd=1, wrap=tk.NONE)
        self.dep_text.pack(fill=tk.X, pady=(2, 0))
        self.dep_text.bind('<KeyRelease>', self.on_dep_text_change)
        
        self.dep_count_label = tk.Label(dep_inner, text="共 0 个依赖包", font=('微软雅黑', 8),
                                        bg=self.colors['frame_bg'], fg='#95a5a6')
        self.dep_count_label.pack(anchor='e', pady=(2, 0))
        
        option_frame = tk.Frame(main_frame, bg=self.colors['frame_bg'], relief=tk.FLAT, bd=1)
        option_frame.pack(fill=tk.X, pady=(0, 8))
        
        option_inner = tk.Frame(option_frame, bg=self.colors['frame_bg'])
        option_inner.pack(fill=tk.X, padx=10, pady=8)
        
        option_row = tk.Frame(option_inner, bg=self.colors['frame_bg'])
        option_row.pack(fill=tk.X)
        
        options = [
            ("虚拟环境", self.use_venv, "#2980b9"),
            ("删除环境", self.delete_venv, "#555555"),
            ("UPX压缩", self.use_upx, "#16a085"),
            ("PyArmor加密", self.use_pyarmor, "#8e44ad"),
        ]
        
        for txt, var, color in options:
            tk.Checkbutton(option_row, text=txt, variable=var, bg=self.colors['frame_bg'],
                           fg=color, font=('微软雅黑', 9, 'bold')).pack(side=tk.LEFT, padx=8)
        
        row2 = tk.Frame(option_inner, bg=self.colors['frame_bg'])
        row2.pack(fill=tk.X, pady=6)
        
        tk.Label(row2, text="输出名称:", bg=self.colors['frame_bg']).pack(side=tk.LEFT)
        self.output_name = tk.Entry(row2, width=25)
        self.output_name.pack(side=tk.LEFT, padx=15)
        
        tk.Label(row2, text="镜像源:", bg=self.colors['frame_bg']).pack(side=tk.LEFT)
        self.mirror_var = tk.StringVar(value="清华")
        ttk.Combobox(row2, textvariable=self.mirror_var, values=["清华", "阿里云", "豆瓣", "中科大", "官方"],
                     width=10, state="readonly").pack(side=tk.LEFT)
        
        row3 = tk.Frame(option_inner, bg=self.colors['frame_bg'])
        row3.pack(fill=tk.X, pady=6)
        
        tk.Label(row3, text="输出目录:", bg=self.colors['frame_bg'], font=('微软雅黑', 9)).pack(side=tk.LEFT)
        
        self.output_dir_entry = tk.Entry(row3, textvariable=self.output_dir_var, width=40,
                                          font=('Consolas', 9), bg='#f8f9fa', relief=tk.FLAT, bd=1)
        self.output_dir_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        tk.Button(row3, text="📁 浏览", command=self.select_output_dir, font=('微软雅黑', 8),
                  bg='#3498db', fg='white', relief=tk.FLAT, padx=10, pady=2, cursor='hand2').pack(side=tk.LEFT, padx=2)
        
        btn_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        btn_frame.pack(fill=tk.X, pady=(0, 8))
        
        self.build_btn = tk.Button(btn_frame, text="🚀 开始打包", command=self.start_build,
                                   font=('微软雅黑', 11, 'bold'), bg=self.colors['success'],
                                   fg='white', relief=tk.FLAT, padx=25, pady=8, cursor='hand2')
        self.build_btn.pack(side=tk.LEFT, padx=2)
        
        tk.Button(btn_frame, text="🧹 清理缓存", command=self.clean_cache, font=('微软雅黑', 9),
                  bg='#e67e22', fg='white', relief=tk.FLAT, padx=15, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="📂 输出目录", command=self.open_output, font=('微软雅黑', 9),
                  bg='#9b59b6', fg='white', relief=tk.FLAT, padx=15, pady=5, cursor='hand2').pack(side=tk.LEFT, padx=2)
        
        progress_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        progress_frame.pack(fill=tk.X, pady=(0, 8))
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100, length=400, style='TProgressbar')
        self.progress_bar.pack(fill=tk.X, pady=(0, 3))
        
        self.status_label = tk.Label(progress_frame, text="✅ 就绪", font=('微软雅黑', 9),
                                     bg=self.colors['bg'], fg='#7f8c8d')
        self.status_label.pack()
        
        log_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        log_header = tk.Frame(log_frame, bg=self.colors['bg'])
        log_header.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(log_header, text="📋 编译日志", font=('微软雅黑', 10, 'bold'),
                 bg=self.colors['bg'], fg='#2c3e50').pack(side=tk.LEFT)
        
        log_actions = tk.Frame(log_header, bg=self.colors['bg'])
        log_actions.pack(side=tk.RIGHT)
        
        tk.Button(log_actions, text="清空", command=self.clear_log, font=('微软雅黑', 8),
                  bg='#95a5a6', fg='white', relief=tk.FLAT, padx=8, pady=2, cursor='hand2').pack(side=tk.LEFT, padx=2)
        tk.Button(log_actions, text="导出", command=self.export_log, font=('微软雅黑', 8),
                  bg='#3498db', fg='white', relief=tk.FLAT, padx=8, pady=2, cursor='hand2').pack(side=tk.LEFT, padx=2)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, bg=self.colors['log_bg'], fg=self.colors['log_fg'],
                                                   font=('Consolas', 10), height=10, relief=tk.FLAT, bd=1)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        self.log_text.tag_config('info', foreground=self.colors['log_info'])
        self.log_text.tag_config('success', foreground=self.colors['log_success'])
        self.log_text.tag_config('error', foreground=self.colors['log_error'])
        self.log_text.tag_config('warning', foreground=self.colors['log_warning'])
        self.log_text.tag_config('build', foreground=self.colors['log_build'])
        
        status_frame = tk.Frame(main_frame, bg='#dfe6e9', height=25)
        status_frame.pack(fill=tk.X, pady=(5, 0))
        status_frame.pack_propagate(False)
        
        self.status_bar = tk.Label(status_frame, text="✅ 就绪 | 等待操作...", font=('微软雅黑', 8),
                                   bg='#dfe6e9', fg='#636e72', anchor='w')
        self.status_bar.pack(fill=tk.X, padx=10, pady=3)
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TProgressbar', background=self.colors['success'], troughcolor='#dfe6e9',
                        bordercolor='#dfe6e9', lightcolor=self.colors['success'], darkcolor=self.colors['success'])
    
    def select_output_dir(self):
        dir_path = filedialog.askdirectory(title="选择输出目录", initialdir=self.output_dir_var.get())
        if dir_path:
            self.output_dir_var.set(dir_path)
            self.log(f"📂 输出目录设置为: {dir_path}", 'info')
    
    def setup_log_menu(self):
        self.log_menu = tk.Menu(self.root, tearoff=0, bg='#2d2d2d', fg='#cdd6f4')
        self.log_menu.add_command(label="📋 复制选中", command=self.copy_selected_log, accelerator="Ctrl+C")
        self.log_menu.add_command(label="📋 复制全部", command=self.copy_all_log)
        self.log_menu.add_separator()
        self.log_menu.add_command(label="🗑️ 清空日志", command=self.clear_log, accelerator="Ctrl+L")
        self.log_menu.add_command(label="💾 导出日志", command=self.export_log)
        self.log_menu.add_separator()
        self.log_menu.add_command(label="🔍 查找", command=self.find_in_log, accelerator="Ctrl+F")
        
        self.log_text.bind("<Button-3>", self.show_log_menu)
        self.log_text.bind("<Control-c>", lambda e: self.copy_selected_log())
        self.log_text.bind("<Control-l>", lambda e: self.clear_log())
        self.log_text.bind("<Control-L>", lambda e: self.clear_log())
        self.log_text.bind("<Control-f>", lambda e: self.find_in_log())
        self.log_text.bind("<Control-F>", lambda e: self.find_in_log())
    
    def show_log_menu(self, event):
        try:
            self.log_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.log_menu.grab_release()
    
    def copy_selected_log(self):
        try:
            selected = self.log_text.get(tk.SEL_FIRST, tk.SEL_LAST)
            if selected.strip():
                self.root.clipboard_clear()
                self.root.clipboard_append(selected)
                self.status_bar.config(text="✅ 已复制选中内容")
                self.root.after(2000, lambda: self.status_bar.config(text="✅ 就绪 | 等待操作..."))
        except:
            pass
    
    def copy_all_log(self):
        content = self.log_text.get(1.0, tk.END)
        if content.strip():
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.status_bar.config(text="✅ 已复制全部日志")
            self.root.after(2000, lambda: self.status_bar.config(text="✅ 就绪 | 等待操作..."))
    
    def clear_log(self):
        self.log_text.delete(1.0, tk.END)
        self.status_bar.config(text="🗑️ 日志已清空")
        self.root.after(2000, lambda: self.status_bar.config(text="✅ 就绪 | 等待操作..."))
    
    def export_log(self):
        content = self.log_text.get(1.0, tk.END)
        if not content.strip():
            messagebox.showinfo("提示", "日志为空")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="导出日志", defaultextension=".log",
            filetypes=[("日志文件", "*.log"), ("文本文件", "*.txt")],
            initialfile=f"build_log_{time.strftime('%Y%m%d_%H%M%S')}.log"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.status_bar.config(text="✅ 日志已导出")
                messagebox.showinfo("成功", f"日志已导出到:\n{file_path}")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {e}")
    
    def find_in_log(self):
        find_window = tk.Toplevel(self.root)
        find_window.title("查找")
        find_window.geometry("400x120")
        find_window.configure(bg='#2d2d2d')
        find_window.resizable(False, False)
        find_window.transient(self.root)
        find_window.grab_set()
        
        find_window.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 200
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 60
        find_window.geometry(f"+{x}+{y}")
        
        tk.Label(find_window, text="查找内容:", font=('微软雅黑', 10), bg='#2d2d2d', fg='#cdd6f4').pack(pady=(15, 5))
        
        entry_frame = tk.Frame(find_window, bg='#2d2d2d')
        entry_frame.pack(pady=5)
        
        entry = tk.Entry(entry_frame, width=35, font=('微软雅黑', 10), bg='#3d3d3d', fg='#cdd6f4',
                        insertbackground='#cdd6f4', relief=tk.FLAT, bd=1)
        entry.pack(side=tk.LEFT, padx=5)
        entry.focus_set()
        
        def do_find():
            search_text = entry.get().strip()
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
                self.log_text.tag_config('found', background='#f9e2af', foreground='#1e1e2e')
                start = end
                count += 1
            
            if count > 0:
                self.status_bar.config(text=f"🔍 找到 {count} 个匹配项")
            else:
                self.status_bar.config(text="🔍 未找到匹配项")
            self.root.after(2000, lambda: self.status_bar.config(text="✅ 就绪 | 等待操作..."))
            find_window.destroy()
        
        tk.Button(entry_frame, text="查找", command=do_find, font=('微软雅黑', 9),
                 bg='#3498db', fg='white', relief=tk.FLAT, padx=20, pady=3, cursor='hand2').pack(side=tk.LEFT, padx=5)
        entry.bind('<Return>', lambda e: do_find())
        find_window.bind('<Escape>', lambda e: find_window.destroy())
    
    def setup_drag_drop(self):
        if DND_FILES:
            self.log("✅ 拖放功能已就绪", 'success')
        else:
            self.log("⚠️ tkinterdnd2未安装，拖放功能不可用", 'warning')
    
    def on_drop_file(self, event):
        try:
            path = event.data.strip('{}').strip('"')
            if path.endswith(('.py', '.pyw')):
                self.source_file.set(path)
                self.log(f"📂 拖放文件: {os.path.basename(path)}", 'info')
                self.auto_set_output_name(path)
                self.scan_dependencies()
                
                self.drop_frame.config(bg='#d5d9e0')
                self.drop_label.config(bg='#d5d9e0')
                self.root.after(300, lambda: self.drop_frame.config(bg=self.colors['drop_bg']))
                self.root.after(300, lambda: self.drop_label.config(bg=self.colors['drop_bg']))
            else:
                self.log("⚠️ 请拖放 .py 或 .pyw 文件", 'warning')
        except Exception as e:
            self.log(f"❌ 拖放处理失败: {e}", 'error')
    
    def browse_file(self):
        file_path = filedialog.askopenfilename(
            title="选择Python程序",
            filetypes=[("Python文件", "*.py *.pyw"), ("所有文件", "*.*")]
        )
        if file_path:
            self.source_file.set(file_path)
            self.log(f"📂 选择文件: {os.path.basename(file_path)}", 'info')
            self.auto_set_output_name(file_path)
            self.scan_dependencies()
    
    def clear_file(self):
        self.source_file.set("")
        self.output_name.delete(0, tk.END)
        self.dep_text.delete(1.0, tk.END)
        self.detected_packages = []
        self.update_dep_count()
        self.log("🗑️ 已清空文件", 'info')
    
    def auto_set_output_name(self, file_path):
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        self.output_name.delete(0, tk.END)
        self.output_name.insert(0, base_name)
        self.log(f"📝 输出名称: {base_name}", 'info')
    
    def on_dep_text_change(self, event=None):
        self.update_dep_count()
    
    def update_dep_count(self):
        content = self.dep_text.get(1.0, tk.END).strip()
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        count = len(lines)
        self.dep_count_label.config(text=f"共 {count} 个依赖包")
        return lines
    
    def get_package_list(self):
        content = self.dep_text.get(1.0, tk.END).strip()
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        return lines
    
    def add_package(self):
        pkg = simpledialog.askstring("添加依赖", "请输入包名:")
        if pkg and pkg.strip():
            pkg = pkg.strip()
            current = self.get_package_list()
            if pkg not in current:
                if current:
                    self.dep_text.insert(tk.END, f"\n{pkg}")
                else:
                    self.dep_text.insert(tk.END, pkg)
                self.update_dep_count()
                self.log(f"➕ 添加依赖: {pkg}", 'info')
            else:
                messagebox.showinfo("提示", f"'{pkg}' 已存在")
    
    def delete_selected_package(self):
        try:
            selected = self.dep_text.get(tk.SEL_FIRST, tk.SEL_LAST)
            if selected.strip():
                content = self.dep_text.get(1.0, tk.END)
                lines = content.split('\n')
                new_lines = []
                deleted = False
                for line in lines:
                    if line.strip() == selected.strip() and not deleted:
                        deleted = True
                        continue
                    new_lines.append(line)
                self.dep_text.delete(1.0, tk.END)
                self.dep_text.insert(1.0, '\n'.join(new_lines))
                self.update_dep_count()
                self.log(f"🗑️ 删除依赖: {selected.strip()}", 'info')
        except:
            messagebox.showinfo("提示", "请先选中要删除的包名")
    
    def clear_packages(self):
        if messagebox.askyesno("确认", "清空所有依赖包？"):
            self.dep_text.delete(1.0, tk.END)
            self.detected_packages = []
            self.update_dep_count()
            self.log("🧹 已清空依赖列表", 'info')
    
    def scan_dependencies(self):
        source = self.source_file.get().strip()
        if not source or not os.path.exists(source):
            self.log("⚠️ 请先选择有效的源文件", 'warning')
            return []
        
        self.log("🔍 正在扫描依赖...", 'info')
        packages = self.core.detect_packages(source)
        
        if packages:
            self.dep_text.delete(1.0, tk.END)
            self.dep_text.insert(1.0, '\n'.join(packages))
            self.update_dep_count()
            self.log(f"📦 检测到 {len(packages)} 个依赖包: {', '.join(packages)}", 'success')
        else:
            self.dep_text.delete(1.0, tk.END)
            self.update_dep_count()
            self.log("✅ 未检测到第三方依赖", 'success')
        
        return packages
    
    def log(self, message, tag='info'):
        timestamp = time.strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, formatted, tag)
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def update_progress(self, value, status):
        self.progress_var.set(value)
        self.status_label.config(text=status)
        self.status_bar.config(text=f"⏳ {status}")
        self.root.update_idletasks()
    
    def start_build(self):
        if self.is_building:
            messagebox.showwarning("提示", "正在打包中，请等待完成")
            return
        
        source = self.source_file.get().strip()
        if not source:
            messagebox.showerror("错误", "请选择要打包的源文件")
            return
        if not os.path.exists(source):
            messagebox.showerror("错误", "源文件不存在")
            return
        
        output_name = self.output_name.get().strip()
        if not output_name:
            output_name = os.path.splitext(os.path.basename(source))[0]
            self.output_name.insert(0, output_name)
        
        packages = self.get_package_list()
        
        confirm_msg = (
            f"即将打包:\n{os.path.basename(source)}\n\n"
            f"输出名称: {output_name}\n"
            f"输出目录: {self.output_dir_var.get()}\n"
            f"依赖包: {', '.join(packages) if packages else '无'}\n"
            f"使用虚拟环境: {'是' if self.use_venv.get() else '否'}\n"
            f"UPX压缩: {'启用' if self.use_upx.get() else '禁用'}\n"
            f"PyArmor加密: {'启用' if self.use_pyarmor.get() else '禁用'}\n\n"
            f"是否继续？"
        )
        
        if not messagebox.askyesno("确认", confirm_msg):
            return
        
        self.log_text.delete(1.0, tk.END)
        self.progress_var.set(0)
        
        self.is_building = True
        self.build_btn.config(state=tk.DISABLED)
        
        import threading
        self.build_thread = threading.Thread(
            target=self.core.build_process,
            args=(source, output_name, packages, {
                'use_venv': self.use_venv.get(),
                'delete_venv': self.delete_venv.get(),
                'use_upx': self.use_upx.get(),
                'use_pyarmor': self.use_pyarmor.get(),
                'mirror': self.mirror_var.get(),
                'output_dir': self.output_dir_var.get(),
            })
        )
        self.build_thread.daemon = True
        self.build_thread.start()
    
    def clean_cache(self):
        if messagebox.askyesno("确认", "清理所有构建缓存？"):
            source = self.source_file.get()
            self.core.clean_cache(source)
            self.log("✅ 缓存清理完成", 'success')
    
    def open_output(self):
        output_dir = self.output_dir_var.get()
        if os.path.exists(output_dir):
            os.startfile(output_dir)
            self.log(f"📂 打开输出目录: {output_dir}", 'info')
        else:
            messagebox.showinfo("提示", "输出目录不存在")
    
    def show_build_result(self):
        dist_dir = self.output_dir_var.get()
        if os.path.exists(dist_dir):
            output_name = self.output_name.get().strip()
            exe_files = [f for f in os.listdir(dist_dir) if f.endswith('.exe')]
            if exe_files:
                matched = [f for f in exe_files if output_name in f]
                target_file = matched[0] if matched else exe_files[0]
                exe_path = os.path.join(dist_dir, target_file)
                size = os.path.getsize(exe_path) / (1024 * 1024)
                
                if messagebox.askyesno(
                    "打包完成",
                    f"🎉 可执行程序构建成功！\n\n"
                    f"📄 文件名称: {target_file}\n"
                    f"📦 文件大小: {size:.2f} MB\n"
                    f"📁 保存路径: {dist_dir}\n\n"
                    f"是否立即打开输出目录？"
                ):
                    os.startfile(dist_dir)


def main():
    multiprocessing.freeze_support()
    
    root = TkinterDnD.Tk()
    root.withdraw()
    
    app = PyBuilderGUI(root)
    
    root.deiconify()
    root.mainloop()


if __name__ == "__main__":
    main()