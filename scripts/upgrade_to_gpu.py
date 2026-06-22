# -*- coding: utf-8 -*-
"""AutoOCRTranslator GPU 补丁安装器.

此脚本既可直接在开发环境运行，也可被 PyInstaller 打包为独立的
upgrade_to_gpu.exe 放入发行包中。打包为 exe 后，用户无需额外安装
Python 即可运行补丁。

用法（开发/脚本模式）：
    python scripts/upgrade_to_gpu.py [--engine rapid|paddle]

用法（发行包模式，exe 应位于 AutoOCRTranslator/ 目录）：
    AutoOCRTranslator\\upgrade_to_gpu.exe [--engine rapid|paddle]
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Tuple


def get_target_dirs() -> Tuple[Path, Path]:
    """返回 (AutoOCRTranslator 根目录, _internal 目录).

    在 PyInstaller onefile 模式下，升级器 exe 应放在 AutoOCRTranslator 根目录；
    在脚本开发模式下，脚本位于 scripts/，向上退一级即为项目/发行包根目录。
    """
    if getattr(sys, "frozen", False):
        # PyInstaller bundle: exe 父目录即目标根目录
        target_root = Path(sys.executable).resolve().parent
    else:
        target_root = Path(__file__).resolve().parent.parent
        if target_root.name.lower() == "scripts":
            target_root = target_root.parent
    return target_root, target_root / "_internal"


def get_python() -> Path:
    """返回可用于运行 pip 的 Python 解释器路径.

    在 PyInstaller onefile 模式下，sys.executable 就是打包后的 exe，
    它自身已包含 Python 运行时与 pip 模块；脚本模式下回退到系统 python。
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()

    system_python = shutil.which("python")
    if system_python:
        return Path(system_python)
    raise FileNotFoundError(
        "找不到 Python 解释器。运行 GPU 补丁需要本机已安装 Python 3.13。"
    )


def run_pip(python: Path, target: Path, *args: str) -> int:
    """调用 pip 并指定 --target 安装到目标 _internal."""
    cmd = [str(python), "-m", "pip", "--target", str(target), *args]
    print(">>> " + " ".join(cmd))
    return subprocess.call(cmd)


def remove_package(target: Path, pkg_name: str) -> None:
    """手动清理目标目录中已存在的同名包，避免 --target 安装冲突."""
    for item in target.iterdir():
        if not item.is_dir():
            continue
        lower = item.name.lower()
        if lower == pkg_name or lower.startswith(pkg_name + "-"):
            print(f"[cleanup] 删除旧包: {item.name}")
            shutil.rmtree(item, ignore_errors=True)


def verify_onnx_gpu(target_internal: Path) -> bool:
    """验证目标 _internal 中的 onnxruntime-gpu 是否可用."""
    python = get_python()
    script = (
        "import sys; "
        f"sys.path.insert(0, r'{target_internal}'); "
        "import onnxruntime as ort; "
        "print('providers:', ort.get_available_providers()); "
        "assert 'CUDAExecutionProvider' in ort.get_available_providers(), "
        "'CUDAExecutionProvider 不可用'"
    )
    return subprocess.call([str(python), "-c", script]) == 0


def install_rapidocr_gpu(target_internal: Path) -> int:
    """安装 RapidOCR 的 onnxruntime-gpu 补丁."""
    print("\n[1/3] 清理旧版 onnxruntime...")
    remove_package(target_internal, "onnxruntime")

    print("\n[2/3] 安装 GPU 版 onnxruntime 到目标目录...")
    rc = run_pip(
        get_python(),
        target_internal,
        "install",
        "onnxruntime-gpu==1.20.1",
        "-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
        "--default-timeout", "300",
    )
    if rc != 0:
        print("错误: 安装 onnxruntime-gpu 失败。请检查网络连接。")
        return rc

    print("\n[3/3] 验证 GPU 可用性...")
    if verify_onnx_gpu(target_internal):
        print("\nRapidOCR GPU 补丁安装完成。")
        print("请重新启动 AutoOCRTranslator，")
        print("在「设置 → OCR」中勾选「启用 GPU 加速 OCR (实验性)」并保存。")
        return 0
    print("错误: GPU 验证失败。请检查 NVIDIA 驱动、CUDA 和 cuDNN 版本。")
    return 1


def verify_paddle_gpu(target_internal: Path) -> bool:
    """验证目标 _internal 中的 paddlepaddle-gpu 是否可用."""
    python = get_python()
    script = (
        "import sys; "
        f"sys.path.insert(0, r'{target_internal}'); "
        "import paddle; "
        "print('CUDA compiled:', paddle.is_compiled_with_cuda()); "
        "print('Device:', paddle.get_device()); "
        "assert paddle.is_compiled_with_cuda(), 'GPU 不可用'"
    )
    return subprocess.call([str(python), "-c", script]) == 0


def install_paddleocr_gpu(target_internal: Path) -> int:
    """安装 PaddleOCR 的 paddlepaddle-gpu 补丁（体积约 1GB+）."""
    print("\n[1/4] 清理旧版 paddle/paddleocr/paddlex...")
    for pkg in ("paddle", "paddleocr", "paddlex", "paddlepaddle"):
        remove_package(target_internal, pkg)

    python = get_python()

    print("\n[2/4] 安装 paddlepaddle-gpu (CUDA 12.6)...")
    rc = run_pip(
        python,
        target_internal,
        "install",
        "paddlepaddle-gpu==3.3.1",
        "-i", "https://www.paddlepaddle.org.cn/packages/stable/cu126/",
        "--default-timeout", "300",
    )
    if rc != 0:
        print("错误: 安装 paddlepaddle-gpu 失败。")
        return rc

    print("\n[3/4] 安装 paddleocr...")
    rc = run_pip(
        python,
        target_internal,
        "install",
        "paddleocr>=3.7.0,<3.8.0",
        "-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
        "--default-timeout", "300",
    )
    if rc != 0:
        print("错误: 安装 paddleocr 失败。")
        return rc

    print("\n[4/4] 验证 GPU 可用性...")
    if verify_paddle_gpu(target_internal):
        print("\nPaddleOCR GPU 补丁安装完成。")
        print("请重新启动 AutoOCRTranslator，")
        print("在「设置 → OCR」中选择 PaddleOCR 并勾选 GPU 加速，保存即可。")
        return 0
    print("错误: GPU 验证失败。请检查 NVIDIA 驱动和 CUDA 版本。")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="AutoOCRTranslator GPU 补丁安装工具"
    )
    parser.add_argument(
        "--engine",
        choices=["rapid", "paddle"],
        default="rapid",
        help="选择要启用 GPU 的 OCR 引擎（默认 rapid，体积更小）",
    )
    args = parser.parse_args()

    target_root, target_internal = get_target_dirs()
    print(f"目标目录: {target_root}")
    print(f"安装目标: {target_internal}")

    if not target_internal.exists():
        print("错误: 找不到 _internal 目录，请确认升级器位于 AutoOCRTranslator 目录内。")
        return 1

    if args.engine == "rapid":
        return install_rapidocr_gpu(target_internal)
    return install_paddleocr_gpu(target_internal)


if __name__ == "__main__":
    sys.exit(main())
