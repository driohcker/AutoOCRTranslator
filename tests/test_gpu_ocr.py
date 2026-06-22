"""PaddleOCR CPU/GPU 速度对比测试.

此测试会分别初始化 CPU 与 GPU 版 PaddleOCR 引擎，
对同一张图片执行多次识别并输出平均耗时。
"""

import sys
import time
from pathlib import Path

from PIL import Image

# 将项目根目录加入路径，支持从 tests 目录直接运行
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def _warm_and_benchmark(engine, image, rounds: int = 5):
    """预热并测试识别耗时."""
    # 预热一次，让 GPU 完成初始化/显存分配
    results = engine.recognize(image)

    times = []
    for _ in range(rounds):
        start = time.perf_counter()
        engine.recognize(image)
        times.append(time.perf_counter() - start)
    return times, results


def main():
    test_image_path = Path(__file__).parent / "ocr_test_input.png"
    if not test_image_path.exists():
        print(f"测试图片不存在: {test_image_path}")
        return 1

    image = Image.open(test_image_path)
    print(f"测试图片尺寸: {image.size}, 模式: {image.mode}")

    # CPU 引擎
    print("\n初始化 CPU 引擎...")
    from src.ocr.paddle_ocr import PaddleOCREngine

    cpu_engine = PaddleOCREngine(
        lang="japan",
        use_gpu=False,
        drop_score=0.3,
        det_db_thresh=0.5,
        det_db_box_thresh=0.5,
    )
    print("CPU 引擎初始化完成，开始测试...")
    cpu_times, cpu_results = _warm_and_benchmark(cpu_engine, image)
    print(f"CPU 识别结果: {[r['text'] for r in cpu_results]}")
    print(f"CPU 平均耗时: {sum(cpu_times) / len(cpu_times):.3f}s")
    print(f"CPU 单次耗时: {[f'{t:.3f}s' for t in cpu_times]}")

    # GPU 引擎
    print("\n初始化 GPU 引擎...")
    gpu_engine = PaddleOCREngine(
        lang="japan",
        use_gpu=True,
        drop_score=0.3,
        det_db_thresh=0.5,
        det_db_box_thresh=0.5,
    )
    print("GPU 引擎初始化完成，开始测试...")
    gpu_times, gpu_results = _warm_and_benchmark(gpu_engine, image)
    print(f"GPU 识别结果: {[r['text'] for r in gpu_results]}")
    print(f"GPU 平均耗时: {sum(gpu_times) / len(gpu_times):.3f}s")
    print(f"GPU 单次耗时: {[f'{t:.3f}s' for t in gpu_times]}")

    speedup = sum(cpu_times) / sum(gpu_times)
    print(f"\nGPU 相对 CPU 加速比: {speedup:.2f}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
