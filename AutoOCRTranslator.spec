# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for AutoOCRTranslator (CPU portable build).

This spec produces a directory-style executable.  After PyInstaller collects
files, a cleanup step removes large runtime components that are not required
for OCR/translation (video codecs, PDF support, HuggingFace xet downloader,
unused Qt plugins, tkinter, etc.) to keep the distribution as small as possible.
"""

import os
import shutil
from pathlib import Path


block_cipher = None


a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[('config', 'config'), ('assets', 'assets')],
    hiddenimports=['src'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Unused standard library modules
        'tkinter',
        'unittest',
        'test',
        'pdb',
        'doctest',
        'turtledemo',
        # Heavy optional dependencies that PaddleX pulls but we do not use
        'pypdfium2_raw',
        'hf_xet',
        # Build/test tooling
        'pytest',
        'pluggy',
        'iniconfig',
        '_pytest',
        # PaddleOCR is provided as an optional GPU upgrade patch to keep the
        # base package small. The base build only ships RapidOCR (ONNXRuntime).
        'paddle',
        'paddlex',
        'paddlepaddle',
    ],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AutoOCRTranslator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AutoOCRTranslator',
)


# ---------------------------------------------------------------------------
# Post-build cleanup: remove files that are safe to drop for our use case.
# ---------------------------------------------------------------------------
def remove_path(path: Path) -> None:
    """Delete a file or directory if it exists."""
    if not path.exists():
        return
    try:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink()
        print(f"[cleanup] removed: {path.relative_to(DISTPATH)}")
    except Exception as exc:
        print(f"[cleanup] failed to remove {path}: {exc}")


dist_root = Path(DISTPATH) / 'AutoOCRTranslator'
internal = dist_root / '_internal'

# OpenCV video codecs are not needed for screenshot OCR.
for ffmpeg_dll in [
    internal / 'cv2' / 'opencv_videoio_ffmpeg4100_64.dll',
    internal / 'cv2' / 'opencv_videoio_ffmpeg4130_64.dll',
]:
    remove_path(ffmpeg_dll)

# PDF processing is not used by the translator.
remove_path(internal / 'pypdfium2_raw')

# HuggingFace xet downloader is not used at runtime.
remove_path(internal / 'hf_xet')

# Tkinter / Tcl are not used by this PyQt6 application.
remove_path(internal / 'tk86t.dll')
remove_path(internal / 'tcl86t.dll')
remove_path(internal / '_tk_data')
remove_path(internal / '_tcl_data')
remove_path(internal / 'tcl8')

# Qt plugins we do not need.
qt_plugins = internal / 'PyQt6' / 'Qt6' / 'plugins'
for plugin_dir in [
    'qmltooling',
    'qml',
    'scxmldatamodel',
    'scenegraph',
    'sqldrivers',
    'designer',
    'canbus',
    'position',
    'geoservices',
    'printsupport',
    'multimedia',
    'audio',
    'mediaservice',
    'playlistformats',
    'renderplugins',
    'assetimporters',
    'iconengines',
    'virtualkeyboard',
    'tls',
]:
    remove_path(qt_plugins / plugin_dir)

# Qt translations: keep only a few common locales, drop the rest.
qt_translations = internal / 'PyQt6' / 'Qt6' / 'translations'
if qt_translations.exists():
    keep_prefixes = ('qt_', 'qtbase_')
    keep_locales = {'en', 'zh', 'zh_CN', 'zh_TW'}
    for trans_file in qt_translations.iterdir():
        if not trans_file.is_file():
            continue
        name = trans_file.name
        if not name.startswith(keep_prefixes):
            remove_path(trans_file)
            continue
        # qtbase_zh_CN.qm -> zh_CN
        locale = name.split('_', 1)[1].rsplit('.', 1)[0]
        # handle compound names like qtbase_en_GB
        base_locale = locale.split('_')[0]
        if locale not in keep_locales and base_locale not in keep_locales:
            remove_path(trans_file)

# Large runtime libraries that are safe to drop for our use case.
# (verified by launching the executable after removal)
remove_path(internal / 'paddle' / 'libs' / 'mkldnn.dll')  # oneDNN disabled via FLAGS_use_mkldnn=0
remove_path(internal / 'pandas')
remove_path(internal / 'pandas.libs')
remove_path(internal / 'PyQt6' / 'Qt6' / 'bin' / 'opengl32sw.dll')
remove_path(internal / 'PyQt6' / 'Qt6' / 'bin' / 'Qt6Pdf.dll')
remove_path(internal / 'PIL' / '_avif.cp313-win_amd64.pyd')

# OpenCV contrib/extension submodules are not required by RapidOCR.
# RapidOCR only uses the main cv2.pyd functions (resize, cvtColor, etc.).
cv2_unused_subdirs = [
    'aruco', 'barcode', 'bgsegm', 'bioinspired', 'ccm', 'colored_kinfu',
    'cuda', 'datasets', 'detail', 'dnn', 'dnn_superres', 'dpm', 'dynafu',
    'face', 'fisheye', 'flann', 'ft', 'gapi', 'hfs', 'img_hash', 'instr',
    'intensity_transform', 'ipp', 'kinfu', 'large_kinfu', 'legacy',
    'line_descriptor', 'linemod', 'mcc', 'misc', 'ml', 'motempl', 'multicalib',
    'ocl', 'ogl', 'omnidir', 'optflow', 'parallel', 'phase_unwrapping', 'plot',
    'ppf_match_3d', 'quality', 'rapid', 'reg', 'rgbd', 'saliency',
    'samples', 'segmentation', 'signal', 'stereo', 'structured_light', 'text',
    'tracking', 'typing', 'utils', 'videoio_registry', 'videostab',
    'wechat_qrcode', 'xfeatures2d', 'ximgproc', 'xphoto',
]
cv2_dir = internal / 'cv2'
for sub in cv2_unused_subdirs:
    remove_path(cv2_dir / sub)

# Qt6 DLLs that are collected by PyInstaller but not used by this Widgets app.
qt_bin = internal / 'PyQt6' / 'Qt6' / 'bin'
qt_unused_dlls = [
    'Qt6Bluetooth.dll', 'Qt6Concurrent.dll', 'Qt6DBus.dll', 'Qt6Designer.dll',
    'Qt6Help.dll', 'Qt6LabsAnimation.dll', 'Qt6LabsFolderListModel.dll',
    'Qt6LabsPlatform.dll', 'Qt6LabsQmlModels.dll', 'Qt6LabsSettings.dll',
    'Qt6LabsSharedImage.dll', 'Qt6LabsWavefrontMesh.dll',
    'Qt6Multimedia.dll', 'Qt6MultimediaQuick.dll', 'Qt6MultimediaWidgets.dll',
    'Qt6Network.dll', 'Qt6Nfc.dll', 'Qt6OpenGLWidgets.dll',
    'Qt6Pdf.dll', 'Qt6PdfQuick.dll', 'Qt6PdfWidgets.dll',
    'Qt6Positioning.dll', 'Qt6PositioningQuick.dll', 'Qt6PrintSupport.dll',
    'Qt6Qml.dll', 'Qt6QmlMeta.dll', 'Qt6QmlModels.dll', 'Qt6QmlWorkerScript.dll',
    'Qt6Quick.dll', 'Qt6Quick3D.dll', 'Qt6Quick3DAssetImport.dll',
    'Qt6Quick3DAssetUtils.dll', 'Qt6Quick3DEffects.dll',
    'Qt6Quick3DGlslParser.dll', 'Qt6Quick3DHelpers.dll',
    'Qt6Quick3DHelpersImpl.dll', 'Qt6Quick3DIblBaker.dll',
    'Qt6Quick3DParticles.dll', 'Qt6Quick3DPhysics.dll',
    'Qt6Quick3DPhysicsHelpers.dll', 'Qt6Quick3DRuntimeRender.dll',
    'Qt6Quick3DSpatialAudio.dll', 'Qt6Quick3DUtils.dll', 'Qt6Quick3DXr.dll',
    'Qt6QuickControls2.dll', 'Qt6QuickControls2Basic.dll',
    'Qt6QuickControls2BasicStyleImpl.dll', 'Qt6QuickControls2Fusion.dll',
    'Qt6QuickControls2FusionStyleImpl.dll', 'Qt6QuickControls2Imagine.dll',
    'Qt6QuickControls2ImagineStyleImpl.dll', 'Qt6QuickControls2Impl.dll',
    'Qt6QuickControls2Material.dll', 'Qt6QuickControls2MaterialStyleImpl.dll',
    'Qt6QuickControls2Universal.dll', 'Qt6QuickControls2UniversalStyleImpl.dll',
    'Qt6QuickDialogs2.dll', 'Qt6QuickDialogs2QuickImpl.dll',
    'Qt6QuickDialogs2Utils.dll', 'Qt6QuickEffects.dll', 'Qt6QuickLayouts.dll',
    'Qt6QuickParticles.dll', 'Qt6QuickShapes.dll', 'Qt6QuickTemplates2.dll',
    'Qt6QuickTest.dll', 'Qt6QuickTimeline.dll', 'Qt6QuickTimelineBlendTrees.dll',
    'Qt6QuickVectorImage.dll', 'Qt6QuickVectorImageGenerator.dll',
    'Qt6QuickWidgets.dll', 'Qt6RemoteObjects.dll', 'Qt6Sensors.dll',
    'Qt6SensorsQuick.dll', 'Qt6SerialPort.dll', 'Qt6Sql.dll',
    'Qt6StateMachine.dll', 'Qt6StateMachineQml.dll', 'Qt6SvgWidgets.dll',
    'Qt6Test.dll', 'Qt6TextToSpeech.dll', 'Qt6WebChannel.dll',
    'Qt6WebChannelQuick.dll', 'Qt6WebSockets.dll', 'Qt6Xml.dll',
    # Qt Multimedia/ffmpeg codecs
    'avcodec-61.dll', 'avformat-61.dll', 'avutil-59.dll',
    'swresample-5.dll', 'swscale-8.dll',
]
for dll in qt_unused_dlls:
    remove_path(qt_bin / dll)

# Drop dist-info and other metadata to save space.
for meta_dir in internal.glob('*.dist-info'):
    remove_path(meta_dir)

# Drop __pycache__ directories that may have been collected.
for pycache_dir in internal.rglob('__pycache__'):
    remove_path(pycache_dir)

# Remove unused Qt image format plugins.
imgformats = internal / 'PyQt6' / 'Qt6' / 'plugins' / 'imageformats'
for img_plugin in ['qtiff.dll', 'qwebp.dll', 'qicns.dll', 'qpdf.dll',
                   'qwbmp.dll', 'qtga.dll']:
    remove_path(imgformats / img_plugin)

# Qt6Svg is only needed if the application ships SVG icons/assets.
remove_path(internal / 'PyQt6' / 'Qt6' / 'bin' / 'Qt6Svg.dll')
remove_path(imgformats / 'qsvg.dll')

# Copy GPU patch readme to the distribution root.
# RapidOCR GPU 补丁由程序内置下载器安装；PaddleOCR GPU 补丁需要单独下载
# upgrade_to_gpu.exe，作为 Release 附件提供，不放入主程序包。
repo_root = Path(SPECPATH)

readme_src = repo_root / 'docs' / 'GPU_PATCH.md'
if readme_src.exists():
    try:
        shutil.copy2(readme_src, dist_root / 'GPU_PATCH_README.md')
        print("[cleanup] copied: GPU_PATCH_README.md")
    except Exception as exc:
        print(f"[cleanup] failed to copy GPU_PATCH_README.md: {exc}")

print("[cleanup] post-build cleanup finished")
