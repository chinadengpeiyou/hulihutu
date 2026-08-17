class BaseWindow:
    """这是你的父类，不要修改它"""
    def __init__(self):
        # ...父类内部逻辑，创建主容器parent
        self.main_container = None

        # 父类内部会调用：把容器传给虚方法
        self.setup_content(self.main_container)

    def setup_content(self, parent):
        """虚方法，供子类扩展UI控件"""
        pass


# ========== 子类，在这里写你的界面，不动父类 ==========
class MySubWindow(BaseWindow):
    def setup_content(self, parent):
        """重写父类虚方法，parent就是父类传过来的主内容容器"""
        # 所有控件都挂载到 parent 上，不要自己新建根
        import tkinter as tk
        lbl = tk.Label(parent, text="我是子类添加的控件")
        lbl.pack()

        btn = tk.Button(parent, text="按钮")
        btn.pack()