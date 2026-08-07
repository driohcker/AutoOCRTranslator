"""Create a GitHub release and upload the asset."""

import json
import os
import sys
from pathlib import Path

import requests


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN not set", file=sys.stderr)
        return 1

    repo = "driohcker/AutoOCRTranslator"
    tag = "v0.0.4"
    name = "AutoOCRTranslator v0.0.4"
    body = """## v0.0.4

- **异步翻译管道重构**（借鉴 BetterGI 架构）：OCR 与联网翻译彻底解耦，识别循环永不等待网络。
- **画面变化检测**：dHash 感知哈希跳过无变化帧，静止画面近零负载。
- **识别频率提升**：默认 3000ms → 300ms，识别慢于间隔自动追帧。
- **译文异步回填**：先显示原文/缓存译文，译文返回后按文本合并，过期结果丢弃。
- **截图改用 pywin32 原生 BitBlt**：修复打包环境下的截图噪声问题。
- **打包修复**：freeze_support（重复界面）、numpy 崩溃、rapidocr 数据与动态依赖收集、onnxruntime 死锁。
- **翻译调优**：超时 10s→5s、重试 2→1 次、并发 2 线程。

下载 `AutoOCRTranslator.7z` 解压后即可使用。如需 GPU 加速，请在设置 → OCR 中安装对应引擎的 GPU 补丁。
"""

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Create release
    create_url = f"https://api.github.com/repos/{repo}/releases"
    payload = {
        "tag_name": tag,
        "name": name,
        "body": body,
        "prerelease": True,
    }
    print(f"Creating release {tag}...")
    resp = requests.post(create_url, headers=headers, json=payload, timeout=60)
    if resp.status_code != 201:
        print(f"Failed to create release: {resp.status_code} {resp.text}", file=sys.stderr)
        return 1
    release = resp.json()
    release_id = release["id"]
    upload_url = release["upload_url"].replace("{?name,label}", "")
    print(f"Release created: {release['html_url']}")

    # Upload asset
    asset_path = Path("AutoOCRTranslator.7z")
    if not asset_path.exists():
        print(f"Asset not found: {asset_path}", file=sys.stderr)
        return 1

    upload_headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/x-7z-compressed",
    }
    params = {"name": asset_path.name}
    print(f"Uploading {asset_path} ({asset_path.stat().st_size / 1024 / 1024:.1f} MB)...")
    with open(asset_path, "rb") as f:
        resp = requests.post(upload_url, headers=upload_headers, params=params, data=f, timeout=300)
    if resp.status_code != 201:
        print(f"Failed to upload asset: {resp.status_code} {resp.text}", file=sys.stderr)
        return 1
    print(f"Asset uploaded: {resp.json()['browser_download_url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
