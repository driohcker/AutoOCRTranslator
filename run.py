"""快速启动脚本."""

import multiprocessing
import os
import sys

# onnxruntime 在 PyInstaller 冻结环境存在已知死锁：全局线程池在
# 第二次初始化会话时阻塞（表现为首次推理卡死、进程无响应）。
# 必须在 onnxruntime 导入之前禁用 OpenMP 线程池。
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OMP_WAIT_POLICY", "PASSIVE")

from src.app import main

if __name__ == "__main__":
    # PyInstaller 冻结环境 + Windows spawn 必调：否则翻译子进程会重跑整个
    # 程序入口（表现为再打开一个相同的 GUI 窗口）而不是执行 worker 逻辑。
    multiprocessing.freeze_support()
    sys.exit(main())
 