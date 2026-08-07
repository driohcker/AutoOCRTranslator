"""应用主入口."""

import multiprocessing
import os
import sys

# 同 run.py：onnxruntime 冻结环境死锁需在导入前禁用 OpenMP 线程池
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OMP_WAIT_POLICY", "PASSIVE")

from src.app import main

if __name__ == "__main__":
    # 同 run.py：冻结环境下的 multiprocessing spawn 需要 freeze_support()
    multiprocessing.freeze_support()
    sys.exit(main())
