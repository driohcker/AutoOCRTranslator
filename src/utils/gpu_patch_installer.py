"""RapidOCR GPU 补丁在线安装（不依赖 pip）.

直接下载 onnxruntime-gpu 的 wheel 并解压到 AutoOCRTranslator/_internal，
从而把基础包体积控制在最小。安装成功后需要重启程序才能加载 GPU 版。
"""

import os
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Callable, Optional

import requests


# 清华镜像上 onnxruntime-gpu 1.20.1 (cp313-win_amd64) 的直链。
# 该 URL 相对稳定；如镜像更新导致失效，可替换为新的 wheel 地址。
ONNXRUNTIME_GPU_WHL_URL = (
    "https://pypi.tuna.tsinghua.edu.cn/packages/c7/87/"
    "1361640e9277622591926f84d10fcc289c20be03e1ff5480d66c3cd2402f/"
    "onnxruntime_gpu-1.20.1-cp313-cp313-win_amd64.whl"
)

CHUNK_SIZE = 1024 * 1024  # 1 MB


def _get_internal_dir() -> Path:
    """返回当前运行环境的 _internal 目录."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "_internal"
    return Path(__file__).resolve().parent.parent.parent / "_internal"


def _remove_old_onnxruntime(internal: Path) -> None:
    """删除 _internal 中已有的 onnxruntime CPU/GPU 包，避免冲突."""
    for item in list(internal.iterdir()):
        if not item.is_dir():
            continue
        name = item.name.lower()
        if name == "onnxruntime" or name.startswith("onnxruntime-"):
            shutil.rmtree(item, ignore_errors=True)


def _has_gpu_files(internal: Path) -> bool:
    """检查 _internal/onnxruntime 是否包含 CUDA provider DLL."""
    cuda_dll = internal / "onnxruntime" / "capi" / "onnxruntime_providers_cuda.dll"
    return cuda_dll.exists()


def install_rapidocr_gpu_patch(
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> bool:
    """下载并安装 RapidOCR GPU 补丁.

    Args:
        progress_callback: 可选回调，参数为 (已下载字节, 总字节)。

    Returns:
        安装成功返回 True，否则返回 False。
    """
    internal = _get_internal_dir()
    if not internal.exists():
        raise FileNotFoundError(f"找不到 _internal 目录: {internal}")

    response = requests.get(ONNXRUNTIME_GPU_WHL_URL, stream=True, timeout=30)
    response.raise_for_status()
    total = int(response.headers.get("content-length", 0))

    whl_path = internal / "onnxruntime_gpu.tmp.whl"
    downloaded = 0
    with open(whl_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if not chunk:
                continue
            f.write(chunk)
            downloaded += len(chunk)
            if progress_callback:
                progress_callback(downloaded, total)

    try:
        _remove_old_onnxruntime(internal)
        with zipfile.ZipFile(whl_path, "r") as zf:
            zf.extractall(internal)
    finally:
        whl_path.unlink(missing_ok=True)

    return _has_gpu_files(internal)


def rapidocr_gpu_patch_installed() -> bool:
    """判断 RapidOCR GPU 补丁是否已安装."""
    return _has_gpu_files(_get_internal_dir())
