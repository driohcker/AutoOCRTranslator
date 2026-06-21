"""Edge 浏览器日文页面端到端翻译测试.

此脚本自动选择指定的 Edge 浏览器窗口, 启动 AutoOCRTranslator 翻译循环,
运行一段时间后保存截图, 用于验证日文文字是否被识别并覆盖显示为中文.

用法:
    python tests/manual_edge_test.py <hwnd>
"""

import logging
import sys
import time
from pathlib import Path

# 将项目根目录加入 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import win32con
import win32gui
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from src.app import App
from src.capture.window_capture import WindowCapture
from src.config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("edge_test")


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python tests/manual_edge_test.py <hwnd>")
        print("示例: python tests/manual_edge_test.py 1509670")
        return 1

    try:
        target_hwnd = int(sys.argv[1])
    except ValueError:
        print("hwnd 必须是整数")
        return 1

    app = QApplication.instance() or QApplication(sys.argv)
    auto_app = App()

    logger.info("初始化应用模块...")
    auto_app.init()

    # 验证目标窗口有效
    capture = WindowCapture()
    if not capture.find_window("Edge"):
        logger.error("未找到 Edge 窗口")
        return 1

    # 恢复并前置目标窗口, 确保窗口可见且尺寸正常
    win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
    time.sleep(0.5)
    win32gui.SetForegroundWindow(target_hwnd)
    time.sleep(0.5)

    auto_app.capture.set_target(target_hwnd)
    auto_app.overlay.set_target_window(target_hwnd)
    logger.info(f"已设置目标窗口: hwnd={target_hwnd}")

    # 清空缓存, 确保本次都是新翻译
    if auto_app.cache is not None:
        auto_app.cache.clear()
        logger.info("已清空翻译缓存")

    # 创建输出目录
    output_dir = Path("tests/edge_test_output")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 定期保存中间截图
    frame_count = [0]

    def save_snapshot() -> None:
        frame_count[0] += 1
        img = auto_app.capture.capture()
        if img is not None:
            path = output_dir / f"frame_{frame_count[0]:03d}.png"
            img.save(str(path))
            logger.info(f"保存中间截图: {path}")

    snapshot_timer = QTimer()
    snapshot_timer.timeout.connect(save_snapshot)
    snapshot_timer.start(3000)  # 每 3 秒保存一帧原始截图

    auto_app.start()
    logger.info("翻译循环已启动, 将在 25 秒后结束...")

    def finish() -> None:
        snapshot_timer.stop()
        auto_app.stop()

        # 保存最终带覆盖层的截图
        final_img = auto_app.capture.capture()
        if final_img is not None:
            final_path = output_dir / "final_capture.png"
            final_img.save(str(final_path))
            logger.info(f"保存最终原始截图: {final_path}")

        # 保存覆盖层截图（覆盖层窗口内容）
        overlay_img = auto_app.overlay.grab().toImage()
        overlay_path = output_dir / "overlay_content.png"
        overlay_img.save(str(overlay_path))
        logger.info(f"保存覆盖层内容: {overlay_path}")

        logger.info("测试结束")
        app.quit()

    # 25 秒后结束
    QTimer.singleShot(25000, finish)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
