import sys
import tkinter as tk
from tkinter import ttk, messagebox

class SoftMintUnifiedApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("莫兰迪护眼界面 - 融色设计")
        
        # 窗口设计尺寸
        self.win_width = 500
        self.win_height = 560
        self.geometry(f"{self.win_width}x{self.win_height}")
        
        # 统一核心背景色，去除纯白
        self.bg_color = "#EBF0EC"      # 全局主背景（柔和灰绿）
        self.card_bg = "#E1E8E3"       # 卡片背景（比主背景略深，形成微立体感）
        self.primary = "#3F6B4D"       # 主色调（森林绿）
        self.fg = "#223026"            # 文字色（深绿灰）
        
        self.configure(bg=self.bg_color)
        self.resizable(False, False)

        self.setup_styles()
        self.create_widgets()
        
        # 初始化定位：首先居中显示
        self.center_window()

    def setup_styles(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")

        # 1. 基础框架与卡片容器
        self.style.configure("Main.TFrame", background=self.bg_color)
        self.style.configure("Card.TLabelframe", background=self.card_bg, 
                             relief="flat", borderwidth=0)
        self.style.configure("Card.TLabelframe.Label", background=self.card_bg, 
                             foreground=self.primary, font=("Microsoft YaHei", 10, "bold"))

        # 2. 文本标签
        self.style.configure("Header.TLabel", background=self.bg_color, 
                             foreground=self.fg, font=("Microsoft YaHei", 16, "bold"))
        self.style.configure("Card.TLabel", background=self.card_bg, 
                             foreground=self.fg, font=("Microsoft YaHei", 9))

        # 3. 输入框 & 下拉框（彻底告别白色背景）
        self.style.configure("Custom.TEntry", fieldbackground="#D4DDD6", 
                             foreground=self.fg, borderwidth=0, relief="flat")
        self.style.configure("Custom.TCombobox", fieldbackground="#D4DDD6", 
                             background=self.card_bg, foreground=self.fg, borderwidth=0)

        # 4. 单选 & 复选框
        self.style.configure("Card.TRadiobutton", background=self.card_bg, 
                             foreground=self.fg, font=("Microsoft YaHei", 9))
        self.style.map("Card.TRadiobutton", foreground=[("selected", self.primary)])

        self.style.configure("Card.TCheckbutton", background=self.card_bg, 
                             foreground=self.fg, font=("Microsoft YaHei", 9))
        self.style.map("Card.TCheckbutton", foreground=[("selected", self.primary)])

        # 5. 滑块 & 进度条
        self.style.configure("Card.Horizontal.TScale", background=self.card_bg, 
                             troughcolor="#D4DDD6", borderwidth=0)
        self.style.configure("Custom.Horizontal.TProgressbar", troughcolor="#D4DDD6", 
                             background=self.primary, thickness=6, borderwidth=0)

        # 6. 按钮
        self.style.configure("Primary.TButton", background=self.primary, 
                             foreground="#FFFFFF", font=("Microsoft YaHei", 10, "bold"), borderwidth=0)
        self.style.map("Primary.TButton", background=[("active", "#31543C")])

    def create_widgets(self):
        main_frame = ttk.Frame(self, style="Main.TFrame", padding=20)
        main_frame.pack(fill="both", expand=True)

        # 标题
        ttk.Label(main_frame, text="清新护眼工作台", style="Header.TLabel").pack(anchor="w", pady=(0, 15))

        # 卡片 1: 基础选项
        card1 = ttk.LabelFrame(main_frame, text=" 基础选项 ", style="Card.TLabelframe", padding=15)
        card1.pack(fill="x", pady=(0, 12))

        ttk.Label(card1, text="项目名称:", style="Card.TLabel").grid(row=0, column=0, sticky="w", pady=6)
        entry = ttk.Entry(card1, style="Custom.TEntry", width=22)
        entry.insert(0, "无白光护眼模式")
        entry.grid(row=0, column=1, sticky="e", pady=6)

        ttk.Label(card1, text="主题风格:", style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=6)
        combo = ttk.Combobox(card1, values=["自然薄荷", "晨曦微光", "静谧山谷"], style="Custom.TCombobox", width=20)
        combo.current(0)
        combo.grid(row=1, column=1, sticky="e", pady=6)
        card1.columnconfigure(1, weight=1)

        # 卡片 2: 偏好控制
        card2 = ttk.LabelFrame(main_frame, text=" 偏好控制 ", style="Card.TLabelframe", padding=15)
        card2.pack(fill="x", pady=(0, 12))

        self.r_var = tk.IntVar(value=1)
        ttk.Radiobutton(card2, text="降蓝光模式", value=1, variable=self.r_var, style="Card.TRadiobutton").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(card2, text="原色显示", value=2, variable=self.r_var, style="Card.TRadiobutton").grid(row=0, column=1, sticky="w", padx=15)

        self.c_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(card2, text="开启夜间平滑过渡", variable=self.c_var, style="Card.TCheckbutton").grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 5))

        # 新增：停靠右下角复选框
        self.dock_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(card2, text="停靠右下角 (不覆盖任务栏)", variable=self.dock_var, 
                        style="Card.TCheckbutton", command=self.toggle_dock_position).grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 5))

        ttk.Label(card2, text="护眼强度:", style="Card.TLabel").grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.scale = ttk.Scale(card2, from_=0, to=100, value=70, style="Card.Horizontal.TScale", command=self.on_scale)
        self.scale.grid(row=3, column=1, sticky="ew", pady=(10, 0))
        card2.columnconfigure(1, weight=1)

        # 卡片 3: 状态指示
        card3 = ttk.LabelFrame(main_frame, text=" 状态指示 ", style="Card.TLabelframe", padding=15)
        card3.pack(fill="x", pady=(0, 15))

        self.progress = ttk.Progressbar(card3, style="Custom.Horizontal.TProgressbar", value=70)
        self.progress.pack(fill="x")

        # 底部按钮
        btn = ttk.Button(main_frame, text="保存设置", style="Primary.TButton", command=self.on_click)
        btn.pack(fill="x", ipady=5)

    def center_window(self):
        """窗口完美居中算法"""
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        x = (screen_width - self.win_width) // 2
        y = (screen_height - self.win_height) // 2
        self.geometry(f"{self.win_width}x{self.win_height}+{x}+{y}")

    def get_work_area(self):
        """获取扣除任务栏后的可工作区域 (X, Y, Width, Height)"""
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes
            
            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", wintypes.LONG),
                    ("top", wintypes.LONG),
                    ("right", wintypes.LONG),
                    ("bottom", wintypes.LONG)
                ]
            
            rect = RECT()
            # SPI_GETWORKAREA = 0x0030
            ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
            return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
        else:
            # 非 Windows 系统退化回全屏分辨率（也可防止报错）
            return 0, 0, self.winfo_screenwidth(), self.winfo_screenheight()

    def move_to_bottom_right(self):
        """移动到右下角并避开任务栏"""
        self.update_idletasks()
        work_x, work_y, work_w, work_h = self.get_work_area()
        
        # 计算紧贴工作区右下角的 X、Y 坐标
        padding = 10  # 留出 10px 边缘间隙显得更精致
        x = work_x + work_w - self.win_width - padding
        y = work_y + work_h - self.win_height - padding
        
        self.geometry(f"{self.win_width}x{self.win_height}+{x}+{y}")

    def toggle_dock_position(self):
        """复选框切换位置逻辑"""
        if self.dock_var.get():
            self.move_to_bottom_right()
        else:
            self.center_window()

    def on_scale(self, val):
        self.progress["value"] = float(val)

    def on_click(self):
        messagebox.showinfo("提示", "设置已保存！")

if __name__ == "__main__":
    SoftMintUnifiedApp().mainloop()