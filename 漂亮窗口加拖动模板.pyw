# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk
import os
from tkinterdnd2 import DND_FILES, TkinterDnD


class BaseCustomWindow:
    """
    无边框自定义窗口通用基类模板
    包含：
    1. 完美无边框 + 任务栏挂载 + 最小化/还原逻辑
    2. 自定义标题栏（含拖拽移动、动态高亮关闭/最小化按钮）
    3. 柔和右下阴影效果
    """
    def __init__(self, root, title="自定义窗口", width=600, height=400):
        self.root = root
        self.window_title = title
        self.width = width
        self.height = height

        # ========== 1. 配色方案定义 (可根据需要在子类修改) ==========
        self.bg_color = "#EBF7DF"       # 主窗口背景色
        self.title_bg = "#d9eec9"      # 标题栏背景色
        self.btn_hover_bg = "#c5e3b2"  # 标题栏按钮悬停加深色
        self.shadow_color = "#c2d2b3"   # 右下淡绿阴影色

        # 拖拽坐标记录
        self.x_offset = None
        self.y_offset = None

        # 初始化窗口结构
        self._init_window_structure()
        self._setup_style()
        self._build_layout()
        
        # 构建 UI 内容（子类重写 setup_content 方法）
        self.setup_content(self.main_container)
        
        # 初始化定位并显示
        self._center_and_show()

    def _init_window_structure(self):
        """初始化主窗口与无边框 Toplevel 的绑定（解决无边框窗口任务栏最小化问题）"""
        # 主根节点设为完全透明并隐形，专门负责在任务栏占位
        self.root.title(self.window_title)
        self.root.geometry("0x0+0+0")
        self.root.attributes("-alpha", 0.0)

        # 真实承载界面的无边框子窗口
        self.top = tk.Toplevel(self.root)
        self.top.overrideredirect(True)  # 关闭原生标题栏
        self.top.geometry(f"{self.width}x{self.height}")
        self.top.resizable(False, False)
        self.top.withdraw()  # 先隐藏，避免初始化闪烁

        # 绑定任务栏还原事件
        self.root.bind("<Map>", self._on_restore)

    def _setup_style(self):
        """设置默认的 ttk 样式"""
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("WinBg.TFrame", background=self.bg_color)
        self.style.configure("WinBg.TLabelframe", background=self.bg_color)
        self.style.configure("WinBg.TLabelframe.Label", background=self.bg_color)
        self.style.configure(
            "NormalBtn.TButton",
            background=self.bg_color,
            padding=(12, 8),
        )
        self.style.map(
            "NormalBtn.TButton",
            background=[("active", self.bg_color), ("pressed", self.bg_color)],
        )
        # 新增：复选框样式，背景和窗口统一
        self.style.configure("WinBg.TCheckbutton", background=self.bg_color)
        self.style.map("WinBg.TCheckbutton", background=[("active", self.bg_color)])

    def _build_layout(self):
        """构建阴影容器与自定义标题栏"""
        # 1. 阴影外框
        self.shadow_frame = tk.Frame(self.top, bg=self.shadow_color)
        self.shadow_frame.pack(fill=tk.BOTH, expand=True)

        # 2. 内部主容器（向内偏移 offset 留出右下侧阴影效果）
        self.main_container = tk.Frame(self.shadow_frame, bg=self.bg_color)
        self.main_container.place(x=0, y=0, relwidth=1, relheight=1, width=-3, height=-3)

        # 3. 自定义标题栏
        self.title_bar = tk.Frame(self.main_container, bg=self.title_bg, height=36)
        self.title_bar.pack(fill=tk.X)
        self.title_bar.pack_propagate(False)

        # 标题文字
        tk.Label(self.title_bar, text=self.window_title, bg=self.title_bg, font=("微软雅黑", 11)).pack(side=tk.LEFT, padx=12)

        # 关闭按钮（最靠右，移入才高亮）
        btn_close = tk.Button(
            self.title_bar, text="×", bg=self.title_bg, activebackground=self.btn_hover_bg,
            relief="flat", font=("", 12), width=3, command=self.root.destroy
        )
        btn_close.pack(side=tk.RIGHT)
        btn_close.bind("<Enter>", lambda e: btn_close.config(bg=self.btn_hover_bg))
        btn_close.bind("<Leave>", lambda e: btn_close.config(bg=self.title_bg))

        # 最小化按钮（在关闭按钮左边，移入才高亮）
        btn_min = tk.Button(
            self.title_bar, text="−", bg=self.title_bg, activebackground=self.btn_hover_bg,
            relief="flat", font=("", 12), width=3, command=self._min_win
        )
        btn_min.pack(side=tk.RIGHT)
        btn_min.bind("<Enter>", lambda e: btn_min.config(bg=self.btn_hover_bg))
        btn_min.bind("<Leave>", lambda e: btn_min.config(bg=self.title_bg))

        # 4. 绑定标题栏拖拽移动事件
        self.title_bar.bind("<ButtonPress-1>", self._start_move)
        self.title_bar.bind("<ButtonRelease-1>", self._stop_move)
        self.title_bar.bind("<B1-Motion>", self._do_move)

    def _center_and_show(self):
        """计算屏幕居中位置并显示"""
        self.top.update()
        sw = self.top.winfo_screenwidth()
        sh = self.top.winfo_screenheight()
        x = (sw - self.width) // 2
        y = (sh - self.height) // 2
        self.top.geometry(f"{self.width}x{self.height}+{x}+{y}")
        self.top.deiconify()

    # ========== 窗口交互事件控制 ==========
    def _min_win(self):
        """隐藏界面并最小化任务栏根节点"""
        self.top.withdraw()
        self.root.iconify()

    def _on_restore(self, event):
        """任务栏被点击还原时重新显示无边框界面"""
        if self.root.state() == "normal":
            self.top.deiconify()

    def _start_move(self, event):
        self.x_offset = event.x
        self.y_offset = event.y

    def _stop_move(self, event):
        self.x_offset = None
        self.y_offset = None

    def _do_move(self, event):
        deltax = event.x - self.x_offset
        deltay = event.y - self.y_offset
        x = self.top.winfo_x() + deltax
        y = self.top.winfo_y() + deltay
        self.top.geometry(f"+{x}+{y}")

    # ========== 虚方法（供子类扩展 UI 控件）==========
    def setup_content(self, parent):
        """【重要】子类重写此方法，用于在 parent (主内容容器) 中添加新的控件"""
        pass


# ==============================================================================
# 使用示例：继承通用模板类，实现具体的业务/UI界面
# ==============================================================================
class MyDragDropApp(BaseCustomWindow):
    def __init__(self, root):
        # 窗口高度从342 修改为 420
        super().__init__(root, title="📄 文件拖拽演示", width=602, height=420)

    def setup_content(self, parent):
        """在此编写特定窗口的 UI 内容"""
        self.source_file = tk.StringVar()
        self.file_list = []

        main_frame = ttk.Frame(parent, padding="12", style="WinBg.TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="📂 文件拖拽测试", font=("微软雅黑", 14, "bold"), background=self.bg_color).pack(pady=(0, 10))

        # 拖放区域
        file_frame = ttk.LabelFrame(main_frame, text="拖放区域", padding=10, style="WinBg.TLabelframe")
        file_frame.pack(fill=tk.X, pady=5)

        self.drop_label = tk.Label(
            file_frame,
            text="✅ 将文件拖放到此处",
            bg="#d4edda",
            width=55,
            height=4,
            font=("微软雅黑", 12),
            relief=tk.RAISED
        )
        self.drop_label.pack(pady=5)

        # 输入框行
        entry_row = ttk.Frame(file_frame, style="WinBg.TFrame")
        entry_row.pack(fill=tk.X, pady=(12, 14))

        self.file_entry = ttk.Entry(entry_row, textvariable=self.source_file, font=("Consolas", 10))
        self.file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)

        ttk.Button(entry_row, text="🗑️清空", command=self.clear_file, style="NormalBtn.TButton").pack(side=tk.LEFT, padx=(8, 0))

        self.show_files_label = ttk.Label(file_frame, text="未拖入任何文件", foreground="#666", background=self.bg_color)
        self.show_files_label.pack(pady=(0, 6))

        # ========== 新增：一行4个水果复选框，使用统一背景样式 ==========
        fruit_frame = ttk.Frame(main_frame, style="WinBg.TFrame")
        fruit_frame.pack(pady=(10, 0))

        # 4个布尔变量
        self.var_apple = tk.BooleanVar()
        self.var_banana = tk.BooleanVar()
        self.var_orange = tk.BooleanVar()
        self.var_grape = tk.BooleanVar()

        ttk.Checkbutton(fruit_frame, text="苹果", variable=self.var_apple, style="WinBg.TCheckbutton").pack(side=tk.LEFT, padx=12)
        ttk.Checkbutton(fruit_frame, text="香蕉", variable=self.var_banana, style="WinBg.TCheckbutton").pack(side=tk.LEFT, padx=12)
        ttk.Checkbutton(fruit_frame, text="橙子", variable=self.var_orange, style="WinBg.TCheckbutton").pack(side=tk.LEFT, padx=12)
        ttk.Checkbutton(fruit_frame, text="葡萄", variable=self.var_grape, style="WinBg.TCheckbutton").pack(side=tk.LEFT, padx=12)

        # 直接进行拖拽绑定，无需条件判断
        self.setup_drag_drop()

    def setup_drag_drop(self):
        """直接注册拖拽事件"""
        self.drop_label.drop_target_register(DND_FILES)
        self.drop_label.dnd_bind("<<Drop>>", self.on_drop_file)

    def on_drop_file(self, event):
        try:
            raw_data = event.data
            self.file_list = self.root.tk.splitlist(raw_data)
            if self.file_list:
                self.source_file.set(self.file_list[0])
                names = [os.path.basename(p) for p in self.file_list]
                self.show_files_label.config(text=f"已拖入：{', '.join(names)}", foreground="#000000")
            print(f"📥收到文件列表: {self.file_list}")
        except Exception as e:
            print(f"❌拖拽处理失败：{e}")

    def clear_file(self):
        self.source_file.set("")
        self.file_list.clear()
        self.show_files_label.config(text="未拖入任何文件", foreground="#666")


def main():
    # 强制使用 TkinterDnD.Tk() 创建主根窗口
    root = TkinterDnD.Tk()
    app = MyDragDropApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()