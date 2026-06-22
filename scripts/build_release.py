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
BANDIZIP = Path(r"D:\Bandizip\bz.exe")


def run(cmd: list[str | Path], **kwargs) -> int:
    print(">>> " + " ".join(str(c) for c in cmd))
    return subprocess.call(cmd, cwd=REPO_ROOT, **kwargs)


def build_base_package() -> int:
    """构建 AutoOCRTranslator 基础包."""
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

    pyinstaller = REPO_ROOT / ".venv-build-cpu" / "Scripts" / "pyinstaller.exe"
    rc = run([pyinstaller, "--clean", "-y", str(SPEC_FILE)], env=env)
    return rc


def build_gpu_patch_installer() -> Path | None:
    """打包 upgrade_to_gpu.py 为独立 exe，返回 exe 路径."""
    print("\n构建 GPU 补丁安装器 upgrade_to_gpu.exe...")
    out_dir = DIST_DIR
    out_dir.mkdir(exist_ok=True)

    # 清理旧产物
    for d in (BUILD_DIR / "upgrade_to_gpu", out_dir / "upgrade_to_gpu.exe"):
        if isinstance(d, Path) and d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
        elif isinstance(d, Path) and d.exists():
            d.unlink()

    pyinstaller = REPO_ROOT / ".venv-build-cpu" / "Scripts" / "pyinstaller.exe"
    rc = run(
        [
            pyinstaller,
            "--onefile",
            "--console",
            "--name", "upgrade_to_gpu",
            "--distpath", str(out_dir),
            "--hidden-import", "pip",
            str(REPO_ROOT / "scripts" / "upgrade_to_gpu.py"),
        ]
    )
    if rc != 0:
        print("GPU 补丁安装器构建失败。")
        return None

    exe = out_dir / "upgrade_to_gpu.exe"
    if exe.exists():
        print(f"GPU 补丁安装器: {exe} ({exe.stat().st_size / 1024 / 1024:.1f} MB)")
        return exe
    print("未找到生成的 upgrade_to_gpu.exe")
    return None


def main() -> int:
    if not (REPO_ROOT / ".venv-build-cpu").exists():
        print("警告：未检测到 .venv-build-cpu，请确认使用了正确的打包虚拟环境。")

    rc = build_base_package()
    if rc != 0:
        print("PyInstaller 基础包构建失败。")
        return rc

    output_dir = DIST_DIR / "AutoOCRTranslator"
    total_size = sum(
        f.stat().st_size for f in output_dir.rglob("*") if f.is_file()
    )
    print(f"\n基础包解压后体积: {total_size / 1024 / 1024:.1f} MB")

    # 压缩基础发行包（不含 GPU 补丁安装器，以控制体积）
    base_archive = REPO_ROOT / "AutoOCRTranslator.7z"
    if BANDIZIP.exists():
        if base_archive.exists():
            base_archive.unlink()
        rc = run([BANDIZIP, "c", "-fmt:7z", "-l:9", str(base_archive), str(output_dir)])
        if rc == 0 and base_archive.exists():
            print(
                f"基础发行包: {base_archive} "
                f"({base_archive.stat().st_size / 1024 / 1024:.1f} MB)"
            )
    else:
        print("未找到 Bandizip，跳过基础包压缩。请手动压缩 dist/AutoOCRTranslator。")

    # 单独构建 GPU 补丁安装器并打包为独立附件
    installer = build_gpu_patch_installer()
    if installer and BANDIZIP.exists():
        patch_archive = REPO_ROOT / "upgrade_to_gpu.7z"
        if patch_archive.exists():
            patch_archive.unlink()
        # 临时目录用于打包，附带说明文档
        patch_temp = DIST_DIR / "upgrade_to_gpu_pkg"
        if patch_temp.exists():
            shutil.rmtree(patch_temp, ignore_errors=True)
        patch_temp.mkdir(parents=True, exist_ok=True)
        shutil.copy2(installer, patch_temp / "upgrade_to_gpu.exe")
        readme = REPO_ROOT / "docs" / "GPU_PATCH.md"
        if readme.exists():
            shutil.copy2(readme, patch_temp / "GPU_PATCH_README.md")
        rc = run(
            [BANDIZIP, "c", "-fmt:7z", "-l:9", str(patch_archive), str(patch_temp)]
        )
        if rc == 0 and patch_archive.exists():
            print(
                f"GPU 补丁安装器包: {patch_archive} "
                f"({patch_archive.stat().st_size / 1024 / 1024:.1f} MB)"
            )
        shutil.rmtree(patch_temp, ignore_errors=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
