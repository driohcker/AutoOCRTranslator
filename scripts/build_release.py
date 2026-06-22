"""AutoOCRTranslator 基础包构建脚本.

用法：
    .venv-build-cpu\\Scripts\\python scripts\\build_release.py

环境要求：
- 已创建并激活独立的打包虚拟环境（推荐 .venv-build-cpu）。
- 该环境中安装：
    pip install -r requirements-build.txt
- 将 UPX 放在 tools/upx-4.2.4-win64/upx.exe（或修改脚本中的 UPX_DIR）。
- 系统中可用 Bandizip CLI（D:\\Bandizip\\bandizip.exe）来生成 .7z；
  如不可用，脚本会跳过压缩步骤。
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "dist"
BUILD_DIR = REPO_ROOT / "build"
SPEC_FILE = REPO_ROOT / "AutoOCRTranslator.spec"
UPX_DIR = REPO_ROOT / "tools" / "upx-4.2.4-win64"
BANDIZIP = Path(r"D:\Bandizip\bandizip.exe")


def run(cmd: list[str | Path], **kwargs) -> int:
    print(">>> " + " ".join(str(c) for c in cmd))
    return subprocess.call(cmd, cwd=REPO_ROOT, **kwargs)


def main() -> int:
    if not (REPO_ROOT / ".venv-build-cpu").exists():
        print("警告：未检测到 .venv-build-cpu，请确认使用了正确的打包虚拟环境。")

    # 清理旧构建产物
    for d in (DIST_DIR / "AutoOCRTranslator", BUILD_DIR / "AutoOCRTranslator"):
        if d.exists():
            print(f"清理: {d}")
            shutil.rmtree(d, ignore_errors=True)

    env = os.environ.copy()
    if UPX_DIR.exists():
        env["PATH"] = str(UPX_DIR) + os.pathsep + env.get("PATH", "")
        print(f"UPX 路径: {UPX_DIR}")
    else:
        print("警告：未找到 UPX，打包体积会显著增大。")

    # 执行 PyInstaller
    pyinstaller = REPO_ROOT / ".venv-build-cpu" / "Scripts" / "pyinstaller.exe"
    rc = run([pyinstaller, "--clean", "-y", str(SPEC_FILE)], env=env)
    if rc != 0:
        print("PyInstaller 构建失败。")
        return rc

    # 验证体积
    output_dir = DIST_DIR / "AutoOCRTranslator"
    total_size = sum(
        f.stat().st_size for f in output_dir.rglob("*") if f.is_file()
    )
    print(f"\n解压后体积: {total_size / 1024 / 1024:.1f} MB")

    # 压缩发行包
    archive = REPO_ROOT / "AutoOCRTranslator.7z"
    if BANDIZIP.exists():
        if archive.exists():
            archive.unlink()
        rc = run([BANDIZIP, "c", "-fmt:7z", "-l:9", str(archive), str(output_dir)])
        if rc == 0 and archive.exists():
            print(f"发行包: {archive} ({archive.stat().st_size / 1024 / 1024:.1f} MB)")
    else:
        print("未找到 Bandizip，跳过压缩。请手动压缩 dist/AutoOCRTranslator。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
