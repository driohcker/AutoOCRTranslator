"""Edge 浏览器日文页面单帧 OCR+翻译测试.

恢复 Edge 窗口, 截图一帧, 进行 OCR 和翻译, 输出结果.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import win32con
import win32gui
from PIL import Image

from src.capture.window_capture import WindowCapture
from src.config import config
from src.ocr.paddle_ocr import PaddleOCREngine
from src.translate.translator import Translator


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python tests/manual_edge_single_frame.py <hwnd>")
        return 1

    hwnd = int(sys.argv[1])

    print(f"恢复窗口 hwnd={hwnd}...")
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    time.sleep(0.5)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(1.0)

    print("初始化 OCR...")
    ocr = PaddleOCREngine(lang="japan", use_gpu=False, drop_score=0.5)

    print("初始化翻译...")
    translator = Translator(provider_name="google_free")

    print("截图...")
    capture = WindowCapture()
    capture.set_target(hwnd)
    image = capture.capture()
    if image is None:
        print("截图失败")
        return 1

    output_dir = Path("tests/edge_test_output")
    output_dir.mkdir(parents=True, exist_ok=True)
    image.save(output_dir / "single_frame_capture.png")
    print(f"截图已保存: {image.size}")

    # 缩放图片以加速 OCR
    max_width = 1280
    if image.width > max_width:
        ratio = max_width / image.width
        new_size = (max_width, int(image.height * ratio))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
        print(f"缩放后尺寸: {image.size}")

    print("OCR 识别...")
    results = ocr.recognize(image)
    print(f"识别到 {len(results)} 个文本块")

    source_lang = config.get("translate.source_lang", "ja")
    target_lang = config.get("translate.target_lang", "zh-CN")

    output_file = output_dir / "translation_results.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"截图尺寸: {image.size}\n")
        f.write(f"识别到 {len(results)} 个文本块\n")
        f.write("\n--- 识别与翻译结果 ---\n")

        for i, item in enumerate(results[:20]):  # 只显示前 20 个
            text = item["text"]
            score = item["score"]
            f.write(f"\n[{i}] 原文: {text} (置信度: {score:.3f})\n")
            try:
                translated = translator.translate(text, source_lang, target_lang)
                f.write(f"    译文: {translated}\n")
            except Exception as e:
                f.write(f"    翻译失败: {e}\n")

    print(f"\n结果已保存到: {output_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
