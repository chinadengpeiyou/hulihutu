# -*- coding: utf-8 -*-

"""
Python 程序打包工具 v5.0
核心逻辑模块 - 处理打包的所有底层操作
俏狐出品 QQ:86074731
"""

import os
import sys
import subprocess
import shutil
import time
import glob
import ast
import urllib.request
import zipfile


class PyBuilderCore:
    """打包核心逻辑类"""
    
    def __init__(self):
        self.msg_callback = None
        self.cancelled = False
    
    def set_msg_callback(self, callback):
        self.msg_callback = callback
    
    def _log(self, message, tag='info'):
        if self.msg_callback:
            self.msg_callback('log', message, tag)
    
    def _progress(self, value, status):
        if self.msg_callback:
            self.msg_callback('progress', {'value': value, 'status': status})
    
    def _finish(self):
        if self.msg_callback:
            self.msg_callback('finish', None)
    
    def _error(self, message):
        if self.msg_callback:
            self.msg_callback('error', message)
    
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
    
    def get_python_exe(self):
        if getattr(sys, 'frozen', False):
            python = shutil.which("python")
            if python:
                return python
            python = shutil.which("python3")
            if python:
                return python
            raise Exception("当前电脑没有安装 Python")
        else:
            return sys.executable
    
    def get_venv_dir(self):
        base = os.path.join(os.path.expanduser("~"), ".pybuilder")
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, "venv_build")
    
    def get_pyinstaller_cache(self):
        cache_dir = os.path.join(os.path.expanduser("~"), ".pybuilder", "pyinstaller_cache")
        os.makedirs(cache_dir, exist_ok=True)
        return cache_dir
    
    def detect_packages(self, source):
        """AST 依赖分析"""
        packages = set()
        
        stdlib = set(sys.builtin_module_names)
        if hasattr(sys, 'stdlib_module_names'):
            stdlib.update(sys.stdlib_module_names)
        else:
            stdlib.update({
                'abc', 'argparse', 'array', 'ast', 'asyncio', 'atexit', 'base64',
                'binascii', 'bisect', 'builtins', 'bz2', 'calendar', 'cmath', 'cmd',
                'codecs', 'collections', 'configparser', 'contextlib', 'copy', 'csv',
                'ctypes', 'datetime', 'decimal', 'difflib', 'dis', 'email', 'enum',
                'errno', 'fcntl', 'filecmp', 'fileinput', 'fnmatch', 'fractions',
                'ftplib', 'functools', 'gc', 'getopt', 'getpass', 'gettext', 'glob',
                'gzip', 'hashlib', 'heapq', 'hmac', 'html', 'http', 'imaplib', 'importlib',
                'inspect', 'io', 'ipaddress', 'itertools', 'json', 'keyword', 'linecache',
                'locale', 'logging', 'lzma', 'mailbox', 'math', 'mimetypes', 'mmap',
                'multiprocessing', 'numbers', 'operator', 'optparse', 'os', 'pathlib',
                'pdb', 'pickle', 'pkgutil', 'platform', 'plistlib', 'poplib', 'pprint',
                'profile', 'pstats', 'pty', 'pwd', 'queue', 'random', 're', 'readline',
                'reprlib', 'resource', 'runpy', 'sched', 'secrets', 'select', 'shelve',
                'shlex', 'shutil', 'signal', 'socket', 'socketserver', 'sqlite3', 'ssl',
                'stat', 'statistics', 'string', 'struct', 'subprocess', 'symtable', 'sys',
                'sysconfig', 'tabnanny', 'tarfile', 'telnetlib', 'tempfile', 'termios',
                'textwrap', 'threading', 'time', 'timeit', 'tkinter', 'tokenize', 'traceback',
                'tracemalloc', 'tty', 'types', 'typing', 'unicodedata', 'unittest', 'urllib',
                'uu', 'uuid', 'warnings', 'wave', 'weakref', 'webbrowser', 'winreg', 'xml',
                'xmlrpc', 'zipfile', 'zipimport', 'zlib'
            })
        
        source_abs_path = os.path.abspath(source)
        source_dir = os.path.dirname(source_abs_path)
        source_filename = os.path.basename(source_abs_path)
        
        local_modules = set()
        if os.path.exists(source_dir):
            for item in os.listdir(source_dir):
                if item == source_filename:
                    continue
                item_path = os.path.join(source_dir, item)
                if os.path.isfile(item_path) and item.endswith('.py'):
                    local_modules.add(os.path.splitext(item)[0])
                elif os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, '__init__.py')):
                    local_modules.add(item)
        
        package_mapping = {
            'win32api': 'pywin32', 'win32con': 'pywin32', 'win32gui': 'pywin32',
            'win32ui': 'pywin32', 'win32com': 'pywin32', 'win32process': 'pywin32',
            'win32clipboard': 'pywin32', 'pywintypes': 'pywin32', 'pythoncom': 'pywin32',
            'PIL': 'Pillow', 'cv2': 'opencv-python', 'sklearn': 'scikit-learn',
            'bs4': 'beautifulsoup4', 'yaml': 'PyYAML', 'dateutil': 'python-dateutil',
            'crypto': 'pycryptodome', 'Crypto': 'pycryptodome', 'fitz': 'PyMuPDF',
            'serial': 'pyserial', 'docx': 'python-docx', 'pptx': 'python-pptx',
            'openpyxl': 'openpyxl', 'xlrd': 'xlrd', 'pyspark': 'pyspark',
            'OpenGL': 'PyOpenGL', 'django': 'Django', 'flask': 'Flask',
            'fastapi': 'fastapi', 'sqlalchemy': 'SQLAlchemy', 'requests': 'requests',
            'numpy': 'numpy', 'pandas': 'pandas', 'matplotlib': 'matplotlib'
        }
        
        try:
            with open(source, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=source)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top_module = alias.name.split('.')[0]
                        packages.add(top_module)
                elif isinstance(node, ast.ImportFrom):
                    if node.level == 0 and node.module:
                        top_module = node.module.split('.')[0]
                        packages.add(top_module)
            
            filtered_packages = set()
            for pkg in packages:
                if (pkg not in stdlib and pkg not in local_modules and 
                    not pkg.startswith('_') and len(pkg) > 1):
                    mapped_name = package_mapping.get(pkg, pkg)
                    filtered_packages.add(mapped_name)
            
            return sorted(list(filtered_packages))
        
        except Exception as e:
            self._log(f"⚠️ 依赖解析异常: {e}", 'warning')
            return []
    
    def _run_subprocess(self, cmd, capture_output=False, timeout=None):
        """统一的 subprocess 调用，修复编码问题"""
        startupinfo = None
        creationflags = 0
        
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creationflags = subprocess.CREATE_NO_WINDOW
        
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        env['PIP_CONFIG_FILE'] = 'nul' if sys.platform == 'win32' else '/dev/null'
        env['PIP_NO_CACHE_DIR'] = '1'
        
        if capture_output:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                startupinfo=startupinfo,
                creationflags=creationflags,
                env=env,
                encoding='utf-8',
                errors='ignore'
            )
            return result
        else:
            result = subprocess.run(
                cmd,
                timeout=timeout,
                startupinfo=startupinfo,
                creationflags=creationflags,
                env=env,
                encoding='utf-8',
                errors='ignore'
            )
            return result
    
    def run_pip(self, python, args, mirror=""):
        """统一 pip 调用 - 修复编码问题"""
        cmd = [python, "-m", "pip"]
        cmd.extend(args)
        if mirror:
            cmd.extend(["-i", mirror])
        
        result = self._run_subprocess(cmd, capture_output=True)
        
        if result.returncode != 0:
            # 如果返回码非0，检查是否真的安装失败
            # 有些情况下返回码非0但实际安装成功（如 pip 自身升级）
            if "Successfully installed" not in str(result.stdout) and "Requirement already satisfied" not in str(result.stdout):
                raise Exception(f"pip 安装失败 (返回码: {result.returncode})")
    
    def download_upx_if_missing(self):
        """下载 UPX"""
        upx_path = shutil.which("upx")
        if upx_path:
            return os.path.dirname(upx_path)
        
        user_upx_dir = os.path.join(os.path.expanduser("~"), ".pybuilder", "upx")
        user_upx_exe = os.path.join(user_upx_dir, "upx.exe" if sys.platform == 'win32' else "upx")
        if os.path.exists(user_upx_exe):
            return user_upx_dir
        
        local_upx_dir = os.path.join(os.getcwd(), "upx_bin")
        local_upx_exe = os.path.join(local_upx_dir, "upx.exe" if sys.platform == 'win32' else "upx")
        if os.path.exists(local_upx_exe):
            return local_upx_dir
        
        self._log("🌐 正在联网下载 UPX ...", 'warning')
        
        upx_url = "https://ghfast.top/https://github.com/upx/upx/releases/download/v4.2.2/upx-4.2.2-win64.zip"
        zip_path = os.path.join(os.getcwd(), "upx_temp.zip")
        
        try:
            req = urllib.request.Request(upx_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as response, open(zip_path, 'wb') as out_file:
                out_file.write(response.read())
            
            os.makedirs(user_upx_dir, exist_ok=True)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for file_info in zip_ref.infolist():
                    if file_info.filename.endswith("upx.exe"):
                        file_info.filename = "upx.exe"
                        zip_ref.extract(file_info, user_upx_dir)
                        break
            
            if os.path.exists(zip_path):
                os.remove(zip_path)
            
            self._log("✅ UPX 下载并解压完成！", 'success')
            return user_upx_dir
        except Exception as e:
            self._log(f"⚠️ UPX 下载失败: {e}", 'warning')
            if os.path.exists(zip_path):
                os.remove(zip_path)
            return None
    
    def install_packages(self, packages, mirror, use_venv):
        """安装依赖包 - 修复 pip.ini 编码问题"""
        
        # 修复 pip.ini 编码问题
        try:
            pip_dir = os.path.join(os.environ.get('USERPROFILE', ''), 'pip')
            pip_ini = os.path.join(pip_dir, 'pip.ini')
            if os.path.exists(pip_ini):
                try:
                    with open(pip_ini, 'r', encoding='utf-8') as f:
                        f.read()
                except UnicodeDecodeError:
                    self._log("⚠️ pip.ini 编码损坏，正在修复...", 'warning')
                    backup = pip_ini + '.bak'
                    if not os.path.exists(backup):
                        os.rename(pip_ini, backup)
                    else:
                        os.remove(pip_ini)
                    self._log("✅ pip.ini 已重置", 'success')
        except Exception:
            pass
        
        all_req_packages = list(packages)
        
        # 自动添加 pywin32
        if sys.platform == 'win32':
            has_win32 = any('win32' in p.lower() or 'pywin32' in p.lower() for p in all_req_packages)
            if not has_win32:
                all_req_packages.append('pywin32')
                self._log("📦 自动添加 pywin32 依赖", 'info')
        
        # PyArmor 必须安装，不管用户是否勾选
        # 因为后面加密需要用到
        has_pyarmor = any('pyarmor' in p.lower() for p in all_req_packages)
        if not has_pyarmor:
            all_req_packages.append('pyarmor')
            self._log("📦 添加 pyarmor 依赖（加密功能）", 'info')
        
        if use_venv:
            self._log("📦 准备虚拟环境...", 'info')
            venv_dir = self.get_venv_dir()
            python_exe = self.get_python_exe()
            
            if not os.path.exists(venv_dir):
                self._log("  正在创建 venv 环境...", 'info')
                cmd = [python_exe, "-m", "venv", "--clear", venv_dir]
                result = self._run_subprocess(cmd, capture_output=True)
                if result.returncode != 0:
                    raise Exception("虚拟环境创建失败:\n" + (result.stderr or ""))
                self._log("  ✅ 虚拟环境创建成功", 'success')
            
            venv_python = os.path.join(venv_dir, 'Scripts', 'python.exe') if sys.platform == 'win32' else os.path.join(venv_dir, 'bin', 'python')
            
            # 升级 pip
            try:
                self.run_pip(venv_python, ["install", "--upgrade", "pip"], mirror)
            except:
                pass
            
            # 安装 PyInstaller
            self._log("  安装 PyInstaller...", 'info')
            self.run_pip(venv_python, ["install", "pyinstaller"], mirror)
            
            # 安装所有依赖包
            for pkg in all_req_packages:
                if pkg and pkg.strip():
                    self._log(f"  安装 {pkg}...", 'info')
                    try:
                        self.run_pip(venv_python, ["install", pkg], mirror)
                        self._log(f"  ✅ {pkg} 安装完成", 'success')
                    except Exception as e:
                        self._log(f"  ⚠️ {pkg} 安装失败: {e}", 'warning')
            
            self._log("✅ 虚拟环境构建完毕", 'success')
            return venv_python
        
        else:
            self._log("📦 使用系统 Python 环境", 'info')
            python_exe = self.get_python_exe()
            
            # 安装 PyInstaller
            try:
                self.run_pip(python_exe, ["install", "pyinstaller"], mirror)
            except:
                pass
            
            # 安装所有依赖包
            for pkg in all_req_packages:
                if pkg and pkg.strip():
                    self._log(f"  安装 {pkg}...", 'info')
                    try:
                        self.run_pip(python_exe, ["install", pkg], mirror)
                        self._log(f"  ✅ {pkg} 安装完成", 'success')
                    except Exception as e:
                        self._log(f"  ⚠️ {pkg} 安装失败: {e}", 'warning')
            
            return python_exe
    
    def build_exe(self, source, output_name, packages, use_venv, use_upx, use_pyarmor, output_dir, python_exe):
        """执行 PyInstaller 打包"""
        self._log("🔨 开始调用 PyInstaller 编译...", 'info')
        
        pyinstaller_args = [
            '--onefile',
            '--windowed',
            '--name', output_name,
            '--clean',
            '--noconfirm',
            '--workpath', self.get_pyinstaller_cache(),
            '--distpath', output_dir,
            '--specpath', self.get_pyinstaller_cache(),
        ]
        
        if use_upx:
            upx_dir = self.download_upx_if_missing()
            if upx_dir:
                pyinstaller_args.extend(['--upx-dir', upx_dir])
                self._log(f"⚡ UPX 已启用", 'success')
            else:
                pyinstaller_args.append('--noupx')
        else:
            pyinstaller_args.append('--noupx')
        
        try:
            pyinstaller_args.extend(["--collect-all", "tkinterdnd2"])
            self._log("📦 已加入 tkinterdnd2 资源", 'info')
        except:
            pass
        
        hidden_imports = set([
            'multiprocessing', 'multiprocessing.process', 'multiprocessing.queues',
            'multiprocessing.pool', 'multiprocessing.managers', 'multiprocessing.reduction',
            'multiprocessing.spawn', 'multiprocessing.synchronize', 'multiprocessing.sharedctypes',
            'multiprocessing.connection', 'queue', 'threading', '_thread',
            'tkinter', 'tkinter.ttk', 'tkinter.filedialog', 'tkinter.messagebox',
            'tkinter.scrolledtext', 'tkinter.simpledialog', 'tkinterdnd2',
            'glob', 'shutil', 'tempfile', 'zipfile', 'os', 'sys', 'subprocess',
            'time', 'datetime', 'json', 'csv', 're', 'ast', 'string', 'struct',
            'io', 'codecs', 'urllib', 'urllib.request', 'socket', 'ssl',
            'logging', 'traceback', 'warnings', 'collections', 'functools',
            'hashlib', 'base64', 'uuid', 'random', 'copy', 'types', 'typing',
            'enum', 'dataclasses', 'inspect', 'importlib', 'pkgutil',
            'ctypes', 'ctypes.util', 'ctypes.wintypes',
        ])
        
        if sys.platform == 'win32':
            hidden_imports.update([
                'winreg', 'msvcrt', '_winapi',
                'win32gui', 'win32api', 'win32con', 'win32com',
                'pywintypes', 'pythoncom', 'win32process', 'win32clipboard', 'win32ui',
            ])
        
        for pkg in packages:
            if pkg and pkg.strip():
                hidden_imports.add(pkg)
        
        # PyArmor 相关隐藏导入（无论是否启用都加上，因为可能已经安装了）
        hidden_imports.update([
            'pyarmor', 'pyarmor.cli', 'pyarmor.pyarmor',
            'Crypto', 'Crypto.Cipher', 'Crypto.Cipher.AES',
            'Crypto.Util', 'Crypto.Util.Padding',
        ])
        
        for module in sorted(hidden_imports):
            pyinstaller_args.extend(['--hidden-import', module])
        
        try:
            import tkinterdnd2
            dnd_path = os.path.dirname(tkinterdnd2.__file__)
            for file in glob.glob(os.path.join(dnd_path, '*.dll')):
                pyinstaller_args.extend(['--add-binary', f'{file};tkinterdnd2'])
                self._log(f"  包含 DLL: {os.path.basename(file)}", 'info')
        except:
            pass
        
        cmd = [python_exe, '-m', 'PyInstaller'] + pyinstaller_args + [source]
        
        self._log(f"🎯 输出目录: {output_dir}", 'info')
        
        try:
            result = self._run_subprocess(cmd, capture_output=True, timeout=600)
            
            if result.returncode != 0:
                if result.stderr:
                    for line in result.stderr.split('\n'):
                        if line.strip():
                            self._log(f"  {line}", 'error')
                raise Exception("PyInstaller 编译失败")
            
            self._log("✅ 编译生成成功", 'success')
            
            if os.path.exists(output_dir):
                exe_files = [f for f in os.listdir(output_dir) if f.endswith('.exe') and output_name in f]
                if exe_files:
                    exe_path = os.path.join(output_dir, exe_files[0])
                    size = os.path.getsize(exe_path) / (1024 * 1024)
                    self._log(f"📦 文件大小: {size:.2f} MB", 'info')
            
        except subprocess.TimeoutExpired:
            raise Exception("打包超时（超过10分钟）")
    
    def clean_venv(self):
        venv_dir = self.get_venv_dir()
        if os.path.exists(venv_dir):
            try:
                shutil.rmtree(venv_dir)
                self._log("🧹 虚拟环境已移除", 'info')
            except Exception as e:
                self._log(f"⚠️ 删除虚拟环境失败: {e}", 'warning')
    
    def clean_cache(self, source):
        base_dir = os.path.dirname(source) if source and os.path.exists(source) else os.getcwd()
        
        for d in ['build', 'dist', '__pycache__', 'obf_dist']:
            dir_path = os.path.join(base_dir, d)
            if os.path.exists(dir_path):
                try:
                    shutil.rmtree(dir_path)
                    self._log(f"🧹 清理: {d}", 'info')
                except:
                    pass
        
        for f in glob.glob(os.path.join(base_dir, '*.spec')):
            try:
                os.remove(f)
                self._log(f"🧹 清理: {os.path.basename(f)}", 'info')
            except:
                pass
        
        cache_dir = self.get_pyinstaller_cache()
        if os.path.exists(cache_dir):
            try:
                shutil.rmtree(cache_dir)
                self._log("🧹 清理 PyInstaller 缓存", 'info')
            except:
                pass
    
    def build_process(self, source, output_name, packages, options):
        """完整的打包流程"""
        try:
            self._log("=" * 60, 'build')
            self._log("🚀 开始自动化打包构建流程", 'build')
            self._log("=" * 60, 'build')
            self._progress(5, "初始化...")
            
            mirrors = {
                "清华": "https://pypi.tuna.tsinghua.edu.cn/simple",
                "阿里云": "https://mirrors.aliyun.com/pypi/simple/",
                "豆瓣": "https://pypi.douban.com/simple/",
                "中科大": "https://pypi.mirrors.ustc.edu.cn/simple/",
                "官方": ""
            }
            mirror = mirrors.get(options.get('mirror', '清华'), '')
            
            self._progress(10, "安装构建依赖包...")
            
            # 无论是否启用 PyArmor，都安装 pyarmor（因为可能用到）
            # 将 pyarmor 添加到 packages 中
            pkg_list = list(packages)
            if options.get('use_pyarmor', False):
                if 'pyarmor' not in [p.lower() for p in pkg_list]:
                    pkg_list.append('pyarmor')
            
            python_exe = self.install_packages(
                pkg_list, mirror, options.get('use_venv', True)
            )
            
            target_source = source
            pyarmor_out_dir = None
            
            # ===== PyArmor 加密 =====
            if options.get('use_pyarmor', False):
                self._progress(25, "正在进行 PyArmor 加密...")
                self._log("🔒 开始加密混淆...", 'info')
                
                pyarmor_out_dir = os.path.join(os.path.dirname(source), "obf_dist")
                if os.path.exists(pyarmor_out_dir):
                    shutil.rmtree(pyarmor_out_dir)
                
                # 先验证 pyarmor 是否安装成功
                check_cmd = [python_exe, "-c", "import pyarmor; print('OK')"]
                check_result = self._run_subprocess(check_cmd, capture_output=True)
                if check_result.returncode != 0:
                    self._log("⚠️ PyArmor 未正确安装，尝试重新安装...", 'warning')
                    self.run_pip(python_exe, ["install", "pyarmor"], mirror)
                
                # 执行加密
                # 使用更可靠的命令格式
                cmd_obf = [python_exe, "-m", "pyarmor.cli", "gen", "-O", pyarmor_out_dir, source]
                self._log(f"  执行: {' '.join(cmd_obf)}", 'info')
                
                try:
                    result = self._run_subprocess(cmd_obf, capture_output=True, timeout=300)
                    
                    if result.returncode != 0:
                        error_msg = result.stderr or result.stdout or 'PyArmor 返回未知错误'
                        self._log(f"  PyArmor 输出: {error_msg}", 'warning')
                        raise Exception(error_msg)
                    
                    obf_file = os.path.join(pyarmor_out_dir, os.path.basename(source))
                    if os.path.exists(obf_file):
                        target_source = os.path.abspath(obf_file)
                        self._log("✅ 加密成功", 'success')
                    else:
                        # 检查是否生成了其他文件
                        if os.path.exists(pyarmor_out_dir):
                            files = os.listdir(pyarmor_out_dir)
                            if files:
                                self._log(f"  加密输出目录: {files}", 'info')
                                # 尝试找 .py 文件
                                py_files = [f for f in files if f.endswith('.py')]
                                if py_files:
                                    obf_file = os.path.join(pyarmor_out_dir, py_files[0])
                                    target_source = os.path.abspath(obf_file)
                                    self._log(f"✅ 找到加密文件: {py_files[0]}", 'success')
                                else:
                                    raise Exception("未找到加密输出文件")
                            else:
                                raise Exception("加密输出目录为空")
                except subprocess.TimeoutExpired:
                    self._log("⚠️ PyArmor 超时，退回普通编译", 'warning')
                except Exception as e:
                    self._log(f"❌ PyArmor 失败: {e}", 'error')
                    self._log("⚠️ 退回普通编译", 'warning')
            
            # ===== PyInstaller 打包 =====
            self._progress(40, "正在生成可执行文件...")
            self.build_exe(
                target_source, output_name, packages,
                options.get('use_venv', True),
                options.get('use_upx', False),
                options.get('use_pyarmor', False),
                options.get('output_dir', self.get_desktop_path()),
                python_exe
            )
            
            # ===== 清理 =====
            if pyarmor_out_dir and os.path.exists(pyarmor_out_dir):
                try:
                    shutil.rmtree(pyarmor_out_dir)
                    self._log("🧹 加密临时文件已清理", 'info')
                except:
                    pass
            
            if options.get('use_venv', True) and options.get('delete_venv', True):
                self.clean_venv()
            
            self._progress(100, "完成！")
            self._log("=" * 60, 'build')
            self._finish()
            
        except Exception as e:
            import traceback
            self._error(str(e))
            self._log(traceback.format_exc(), 'error')