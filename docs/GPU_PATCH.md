# AutoOCRTranslator GPU 补丁说明

基础版（`AutoOCRTranslator.7z`）默认内置 **RapidOCR（ONNXRuntime CPU）**，体积小巧、解压即用，适合大多数 CPU 场景。

如果你需要启用 GPU 加速，请按本说明安装对应补丁。

## 前置条件

- NVIDIA 独立显卡，驱动已正确安装。
- 已解压基础版 `AutoOCRTranslator.7z` 到任意目录。
- 本机已安装 **Python 3.13** 并已加入系统 PATH（基础包不含 Python 解释器）。
- 网络畅通（补丁包由 pip 在线下载安装）。

## 推荐方案：RapidOCR GPU 补丁（体积小）

RapidOCR 使用 ONNXRuntime 作为推理后端。将其切换为 `onnxruntime-gpu` 即可利用 NVIDIA GPU 加速。

1. 进入解压后的 `AutoOCRTranslator` 文件夹。
2. 双击运行根目录下的 **`upgrade_to_gpu.py`**。
3. 脚本会自动：
   - 卸载 CPU 版 `onnxruntime`；
   - 安装 `onnxruntime-gpu==1.20.1`（目标 CUDA 12.6 + cuDNN 9.x）；
   - 验证 `CUDAExecutionProvider` 可用。
4. 安装完成后，重新启动 `AutoOCRTranslator.exe`。
5. 在「设置 → OCR」中勾选 **「启用 GPU 加速 OCR（实验性）」**，保存设置后翻译循环会自动重启。

> 命令行高级用法：默认安装 RapidOCR GPU 补丁，如需安装 PaddleOCR GPU 补丁可执行
> `upgrade_to_gpu.py --engine paddle`。

## 可选方案：PaddleOCR GPU 补丁（体积大）

如果你更偏好 PaddleOCR 引擎，可安装 `paddlepaddle-gpu`：

```
upgrade_to_gpu.py --engine paddle
```

此补丁约 1GB+，下载和安装时间较长。

## 常见问题

**Q: 为什么基础包不带 GPU？**
A: GPU 推理库体积较大（onnxruntime-gpu 约 200MB，paddlepaddle-gpu 约 1GB+）。基础包默认使用 RapidOCR CPU，已经能满足大多数实时翻译需求；GPU 作为可选补丁按需安装。

**Q: 安装 RapidOCR GPU 补丁后还能切换回 CPU 吗？**
A: 可以。重新运行 `upgrade_to_gpu.py` 前，在设置里取消勾选 GPU 加速即可；如需彻底换回 CPU 版，可在命令行执行：
```
_internal\python.exe -m pip uninstall -y onnxruntime-gpu
_internal\python.exe -m pip install onnxruntime==1.27.0
```

**Q: 我没有 NVIDIA 显卡，能运行 GPU 补丁吗？**
A: 不能。脚本最后的 GPU 验证会失败。

**Q: 补丁安装失败怎么办？**
A: 检查网络连接、NVIDIA 驱动、CUDA/cuDNN 版本；也可在命令行中运行 `upgrade_to_gpu.py` 查看详细错误。
