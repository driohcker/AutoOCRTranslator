"""GPU 补丁可用性检测.

用于在设置界面/启动时判断当前 AutoOCRTranslator 是否已安装对应 GPU 补丁。
对 PyInstaller 打包后的程序，通过检查 _internal 中的关键文件判断；
对源码运行模式，可额外通过 import 检测 CUDA provider 是否真实可用。
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def get_internal_dir() -> Path:
    """返回当前运行环境的 _internal 目录."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "_internal"
    return Path(__file__).resolve().parent.parent.parent / "_internal"


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _check_files(paths: list) -> bool:
    """只要任一关键文件存在，就认为补丁已安装."""
    return any(Path(p).exists() for p in paths)


def rapidocr_gpu_available() -> bool:
    """检测 RapidOCR 的 onnxruntime-gpu 补丁是否可用."""
    internal = get_internal_dir()
    cuda_dll = internal / "onnxruntime" / "capi" / "onnxruntime_providers_cuda.dll"

    if _is_frozen():
        # 打包后无法再用 -c 执行 import，直接检查关键文件
        return cuda_dll.exists()

    # 源码模式下通过 import 二次确认
    script = (
        "import onnxruntime as ort; "
        "assert 'CUDAExecutionProvider' in ort.get_available_providers(), "
        "'CUDA not available'"
    )
    return _run_check_script(script) or cuda_dll.exists()


def paddleocr_gpu_available() -> bool:
    """检测 PaddleOCR 的 paddlepaddle-gpu 补丁是否可用."""
    internal = get_internal_dir()
    phi_dll = internal / "paddle" / "libs" / "phi.dll"

    if _is_frozen():
        return phi_dll.exists()

    script = (
        "import paddle; "
        "assert paddle.is_compiled_with_cuda(), 'Paddle CUDA not available'"
    )
    return _run_check_script(script) or phi_dll.exists()


def gpu_patch_available(engine: str) -> bool:
    """根据引擎名称判断对应 GPU 补丁是否可用."""
    if engine == "rapid":
        return rapidocr_gpu_available()
    if engine == "paddle":
        return paddleocr_gpu_available()
    return False


def get_upgrade_exe_path() -> Optional[Path]:
    """返回 upgrade_to_gpu.exe 的路径（若存在）.

    该 exe 用于 PaddleOCR GPU 补丁安装；RapidOCR GPU 补丁由程序内置下载器安装。
    """
    if _is_frozen():
        exe = Path(sys.executable).resolve().parent / "upgrade_to_gpu.exe"
    else:
        exe = Path(__file__).resolve().parent.parent.parent / "upgrade_to_gpu.exe"
    return exe if exe.exists() else None


def _run_check_script(script: str) -> bool:
    """在独立子进程中执行一段 Python 代码，返回是否成功."""
    import subprocess

    internal = get_internal_dir()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(internal) + os.pathsep + env.get("PYTHONPATH", "")
    try:
        proc = subprocess.run(
            [sys.executable, "-c", script],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0 and proc.stderr:
            logger.debug(f"GPU 检测输出: {proc.stderr.strip()}")
        return proc.returncode == 0
    except Exception as exc:
        logger.warning(f"GPU 检测失败: {exc}")
        return False
