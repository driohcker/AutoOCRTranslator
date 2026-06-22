"""为已打包的 AutoOCRTranslator 启用 GPU 加速（实验性）.

本脚本运行在 AutoOCRTranslator 解压目录中，操作其嵌入式 Python 环境
（_internal/python.exe）。默认安装 RapidOCR 所需的 onnxruntime-gpu 补丁；
如需使用 PaddleOCR GPU，可手动选择安装 paddlepaddle-gpu（体积更大）。

前置条件：
1. 本机有 NVIDIA 独立显卡，驱动正常。
2. 已安装与 onnxruntime-gpu 版本匹配的 CUDA/cuDNN（本包目标 CUDA 12.6）。
3. 网络畅通（onnxruntime-gpu 约 200MB，paddlepaddle-gpu 约 1GB+）。
"""

import argparse
import subprocess
import sys
from pathlib import Path


def get_internal_python() -> Path:
    """返回可用于运行 pip 的 Python 解释器.

    PyInstaller onedir 不会自带 python.exe，因此优先查找 AutoOCRTranslator
    目录内可能随包附带的 python.exe；否则回退到系统 PATH 中的 python。
    运行 GPU 补丁需要 Python 3.13 且已安装 pip。
    """
    import shutil

    base = Path(__file__).resolve().parent
    candidates = [
        base / "_internal" / "python.exe",
        base / "python.exe",
    ]
    for c in candidates:
        if c.exists():
            return c

    system_python = shutil.which("python")
    if system_python:
        return Path(system_python)

    raise FileNotFoundError(
        "找不到 Python 解释器。AutoOCRTranslator 基础包不包含 python.exe，"
        "运行 GPU 补丁需要本机已安装 Python 3.13 并将其加入 PATH。"
    )


def run_pip(python: Path, *args: str) -> int:
    """调用嵌入式 Python 的 pip."""
    cmd = [str(python), "-m", "pip", *args]
    print(">>> " + " ".join(cmd))
    return subprocess.call(cmd)


def verify_onnx_gpu(python: Path) -> bool:
    """验证 onnxruntime-gpu 可用."""
    script = (
        "import onnxruntime as ort; "
        "print('providers:', ort.get_available_providers()); "
        "assert 'CUDAExecutionProvider' in ort.get_available_providers(), "
        "'CUDAExecutionProvider 不可用'"
    )
    return subprocess.call([str(python), "-c", script]) == 0


def install_rapidocr_gpu(python: Path) -> int:
    """安装/切换到 RapidOCR 的 onnxruntime-gpu."""
    print("\n[1/3] 卸载 CPU 版 onnxruntime（如果存在）...")
    run_pip(python, "uninstall", "-y", "onnxruntime")

    print("\n[2/3] 安装 GPU 版 onnxruntime...")
    rc = run_pip(
        python,
        "install",
        "onnxruntime-gpu==1.20.1",
        "-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
        "--default-timeout", "300",
    )
    if rc != 0:
        print("错误: 安装 onnxruntime-gpu 失败。请检查网络连接。")
        return rc

    print("\n[3/3] 验证 GPU 可用性...")
    if verify_onnx_gpu(python):
        print("\nRapidOCR GPU 补丁安装完成。")
        print("请重新启动 AutoOCRTranslator，")
        print("在「设置 → OCR」中勾选「启用 GPU 加速 OCR (实验性)」并保存。")
        return 0
    print("错误: GPU 验证失败。请检查 NVIDIA 驱动、CUDA 和 cuDNN 版本。")
    return 1


def install_paddleocr_gpu(python: Path) -> int:
    """安装 PaddleOCR 所需的 paddlepaddle-gpu（体积约 1GB+）."""
    print("\n[1/3] 卸载 CPU 版 paddlepaddle（如果存在）...")
    run_pip(python, "uninstall", "-y", "paddlepaddle")

    print("\n[2/3] 安装 GPU 版 paddlepaddle-gpu (CUDA 12.6)...")
    rc = run_pip(
        python,
        "install",
        "paddlepaddle-gpu==3.3.1",
        "-i", "https://www.paddlepaddle.org.cn/packages/stable/cu126/",
        "--default-timeout", "300",
    )
    if rc != 0:
        print("错误: 安装 paddlepaddle-gpu 失败。")
        return rc

    print("\n[3/3] 验证 GPU 可用性...")
    script = (
        "import paddle; "
        "print('CUDA compiled:', paddle.is_compiled_with_cuda()); "
        "print('Device:', paddle.get_device()); "
        "assert paddle.is_compiled_with_cuda(), 'GPU 不可用'"
    )
    if subprocess.call([str(python), "-c", script]) == 0:
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

    python = get_internal_python()
    print(f"使用嵌入式 Python: {python}")

    if args.engine == "rapid":
        return install_rapidocr_gpu(python)
    return install_paddleocr_gpu(python)


if __name__ == "__main__":
    sys.exit(main())
