"""等价于运行 run.py，但自动选择 Edge 窗口，并截取整个屏幕观察效果."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mss
import win32con
import win32gui
from PIL import Image
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from src.app import App
from src.capture.window_capture import WindowCapture


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    auto_app = App()

    print("初始化应用...")
    auto_app.init()

    # 自动查找 Edge 窗口
    capture = WindowCapture()
    edge = capture.find_window("Edge")
    if not edge:
        print("未找到 Edge 窗口")
        return 1

    hwnd, title = edge
    safe_title = title.encode("ascii", "ignore").decode("ascii")
    print(f"找到 Edge 窗口: hwnd={hwnd}, title={safe_title}")

    # 恢复并前置窗口
    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    time.sleep(0.5)
    win32gui.SetForegroundWindow(hwnd)
    time.sleep(1.0)

    auto_app.capture.set_target(hwnd)
    auto_app.overlay.set_target_window(hwnd)

    print("启动翻译循环...")
    auto_app.start()

    if not auto_app.is_running:
        print("翻译循环未启动")
        return 1

    print("等待 OCR 和翻译运行，期间会截取多张全屏...")

    screenshot_count = [0]

    def take_screenshot() -> None:
        screenshot_count[0] += 1
        print(f"截取第 {screenshot_count[0]} 张全屏...")
        with mss.MSS() as sct:
            sct_img = sct.grab(sct.monitors[0])  # 主屏幕
            img = Image.frombytes(
                "RGB", sct_img.size, sct_img.bgra, "raw", "BGRX"
            )
            output_path = Path(f"tests/fullscreen_run_test_{screenshot_count[0]:02d}.png")
            img.save(output_path)
            print(f"全屏截图已保存: {output_path}")

    def finish() -> None:
        take_screenshot()
        auto_app.stop()
        app.quit()

    # 启动后 3 秒截第一张（看窗口是否出现）
    QTimer.singleShot(3000, take_screenshot)
    # 启动后 30 秒截第二张
    QTimer.singleShot(30000, take_screenshot)
    # 启动后 90 秒截第三张并退出
    QTimer.singleShot(90000, finish)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
