# log_util.py
import logging


def setup_log(
    log_file: str = "app.log",
    log_level: int = logging.DEBUG,
    enable_file: bool = True,
    enable_console: bool = True,
) -> None:
    root = logging.getLogger()
    root.setLevel(log_level)

    # 关键：每次调用先清空所有旧handler，允许动态切换模式
    root.handlers.clear()

    fmt_str = "%(asctime)s %(levelname)-8s %(message)s"
    formatter = logging.Formatter(fmt_str)

    if enable_file:
        try:
            fh = logging.FileHandler(log_file, encoding="utf-8")
        except Exception:
            fh = logging.FileHandler(log_file, encoding="gbk", errors="replace")
        fh.setFormatter(formatter)
        root.addHandler(fh)

    if enable_console:
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        root.addHandler(ch)