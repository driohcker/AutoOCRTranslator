"""Edge 浏览器日文页面覆盖层显示测试.

恢复 Edge 窗口, 截图后 OCR+翻译, 然后在 Edge 窗口上显示覆盖层, 保存截图验证.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import win32con
import win32gui
from PIL import Image
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from src.capture.window_capture import WindowCapture
from src.config import config
from src.ocr.paddle_ocr import PaddleOCREngine
from src.overlay.overlay_window import OverlayWindow
from src.translate.translator import Translator


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python tests/manual_edge_overlay_test.py <hwnd>")
        return 1

    hwnd = int(sys.argv[1])

    app = QApplication.instance() or QApplication(sys.argv)

    print("恢复 Edge 窗口...")
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    time.sleep(0.5)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(1.0)

    print("初始化 OCR 和翻译...")
    ocr = PaddleOCREngine(lang="japan", use_gpu=False, drop_score=0.5)
    translator = Translator(provider_name="google_free")

    print("截图...")
    capture = WindowCapture()
    capture.set_target(hwnd)
    original_image = capture.capture()
    if original_image is None:
        print("截图失败")
        return 1

    original_size = original_image.size
    print(f"原始截图尺寸: {original_size}")

    # 缩放图片以加速 OCR
    max_width = 1280
    if original_image.width > max_width:
        ratio = max_width / original_image.width
        new_size = (max_width, int(original_image.height * ratio))
        scaled_image = original_image.resize(new_size, Image.Resampling.LANCZOS)
    else:
        scaled_image = original_image
        ratio = 1.0

    print(f"缩放后尺寸: {scaled_image.size}, 缩放比例: {ratio:.3f}")

    print("OCR 识别...")
    ocr_results = ocr.recognize(scaled_image)
    print(f"识别到 {len(ocr_results)} 个文本块")

    source_lang = config.get("translate.source_lang", "ja")
    target_lang = config.get("translate.target_lang", "zh-CN")

    print("翻译...")
    translation_items = []
    for item in ocr_results[:30]:  # 只取前 30 个, 避免覆盖层过于拥挤
        text = item["text"]
        box = item["box"]
        try:
            translated = translator.translate(text, source_lang, target_lang)
        except Exception as e:
            print(f"翻译失败 '{text}': {e}")
            translated = text

        # 将坐标放大回原始窗口尺寸
        scaled_box = [(int(x / ratio), int(y / ratio)) for x, y in box]

        translation_items.append(
            {
                "original": text,
                "translated": translated,
                "box": scaled_box,
                "score": item["score"],
            }
        )

    print(f"准备显示 {len(translation_items)} 条翻译")

    # 创建并显示覆盖层
    overlay = OverlayWindow()
    overlay.set_target_window(hwnd)
    overlay.update_translations(translation_items)
    overlay.show()

    print("覆盖层已显示, 5 秒后保存截图...")

    def finish() -> None:
        # 保存覆盖层内容
        overlay_img = overlay.grab().toImage()
        output_dir = Path("tests/edge_test_output")
        output_dir.mkdir(parents=True, exist_ok=True)
        overlay_path = output_dir / "overlay_display_test.png"
        overlay_img.save(str(overlay_path))
        print(f"覆盖层截图已保存: {overlay_path}")

        # 同时保存当前窗口截图(不含覆盖层)
        final_capture = capture.capture()
        if final_capture:
            final_capture.save(output_dir / "overlay_test_capture.png")

        overlay.hide()
        overlay.close()
        app.quit()

    QTimer.singleShot(5000, finish)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
