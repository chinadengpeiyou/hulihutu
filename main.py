import logging
from log_util import setup_log

# 模式1：只写文件，关闭控制台
setup_log(enable_console=False, enable_file=True)
logging.info("【模式1】这条只会写入文件，屏幕看不到")

# 模式2：只控制台输出，关闭文件
setup_log(enable_file=False, enable_console=True)
logging.info("【模式2】仅屏幕输出，不写文件")

# ✅模式3：双输出：文件 + 控制台同时开启
setup_log(enable_file=True, enable_console=True)
logging.info("【模式3】文件、控制台两边同时输出")

# ⚠️注意：log_file只第一次初始化生效，后面调用传log_file不会切换文件
# 下面这句 log_file 参数无效，仍然写 app.log
setup_log(log_file="软件调试.log", enable_console=False)
logging.info("【模式4】依旧写入app.log，不会切换到软件调试.log")