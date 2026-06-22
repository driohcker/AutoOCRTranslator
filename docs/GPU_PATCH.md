# AutoOCRTranslator GPU 补丁说明

基础版（`AutoOCRTranslator.7z`）默认内置 **RapidOCR（ONNXRuntime CPU）**，体积小巧、解压即用，适合大多数 CPU 场景。

如果你需要启用 GPU 加速，请按本说明操作。

## 前置条件

- NVIDIA 独立显卡，驱动已正确安装。
- 已解压基础版 `AutoOCRTranslator.7z` 到任意目录。
- 网络畅通（补丁包由安装器在线下载安装）。

## 推荐方案：在软件内一键安装

1. 启动 `AutoOCRTranslator.exe`。
2. 打开「设置 → OCR」。
3. 选择你想要的 OCR 引擎：
   - **RapidOCR**（推荐，补丁约 280MB）
   - **PaddleOCR**（补丁约 1GB+）
4. 若 GPU 补丁未安装，「启用 GPU 加速 OCR」复选框会显示为禁用状态，旁边会出现 **「安装 GPU 补丁」** 按钮。
5. 点击按钮：
   - **RapidOCR**：程序会内置下载器从清华镜像下载 `onnxruntime-gpu` 补丁并自动解压到 `_internal`。下载进度会实时显示在按钮左侧。
   - **PaddleOCR**：程序会调用发行包内的 `upgrade_to_gpu.exe --engine paddle` 进行安装，过程需要调用你系统中的 Python/pip。
6. 安装成功后，**重新启动 AutoOCRTranslator**。
7. 再次打开设置，勾选「启用 GPU 加速 OCR (实验性)」，保存即可。

## 备用方案：手动运行安装器

如果软件内安装失败，也可以直接运行发行包根目录下的 `upgrade_to_gpu.exe`：

```
AutoOCRTranslator\upgrade_to_gpu.exe --engine rapid
```

或安装 PaddleOCR GPU 补丁：

```
AutoOCRTranslator\upgrade_to_gpu.exe --engine paddle
```

## 常见问题

**Q: 为什么基础包不带 GPU？**
A: GPU 推理库体积较大（onnxruntime-gpu 约 280MB，paddlepaddle-gpu 约 1GB+）。基础包默认使用 RapidOCR CPU，已经能满足大多数实时翻译需求；GPU 作为可选补丁按需安装。

**Q: 安装 RapidOCR GPU 补丁后还能切换回 CPU 吗？**
A: 可以。在设置里取消勾选 GPU 加速即可；如需彻底卸载 GPU 补丁，可删除 `AutoOCRTranslator\_internal\` 下的 `onnxruntime` 和 `onnxruntime_gpu-*.dist-info`，然后重新解压基础包覆盖。

**Q: 我没有 NVIDIA 显卡，能运行 GPU 补丁吗？**
A: 不能。安装器最后的 GPU 验证会失败。

**Q: 安装失败怎么办？**
A: 检查网络连接、NVIDIA 驱动、CUDA/cuDNN 版本；也可手动运行 `upgrade_to_gpu.exe` 查看详细错误输出。RapidOCR 补丁安装失败时，还可尝试直接下载 [onnxruntime-gpu 1.20.1 (cp313-win_amd64)](https://pypi.tuna.tsinghua.edu.cn/packages/c7/87/1361640e9277622591926f84d10fcc289c20be03e1ff5480d66c3cd2402f/onnxruntime_gpu-1.20.1-cp313-cp313-win_amd64.whl) 并重命名为 `.zip` 解压到 `AutoOCRTranslator\_internal\`。
