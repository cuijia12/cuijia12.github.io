# 串口助手 v1.1 源码

本目录包含串口助手与 T5L 在线下载模块的完整 Python 源码。

## 文件说明

- `serial_assistant.py`：主程序、多路串口会话、串口收发、快捷指令及界面。
- `t5l_download.py`：T5L 在线下载与 T5L51 更新模块。
- `SerialAssistant.spec`：PyInstaller 单文件打包配置。
- `version_info.txt`：Windows EXE 版本信息。
- `run.bat`：Windows 源码启动脚本。

## 运行环境

- Windows 10/11
- Python 3.10 或更高版本
- 仅使用 Python 标准库，无需安装 `pyserial`

## v1.1 多路串口

- 每个 COM 口分别维护串口句柄、接收线程、通讯记录和收发计数。
- 标签可独立打开、关闭、切换和移除。
- T5L 下载只互斥占用实际选择的串口，其余串口保持运行。

## 运行

```powershell
python serial_assistant.py
```

也可以双击 `run.bat` 启动。

## 打包 EXE

安装 PyInstaller：

```powershell
python -m pip install pyinstaller
```

在本目录执行：

```powershell
pyinstaller SerialAssistant.spec
```

## 用户数据

程序运行时会在程序目录生成 `config.json`，用于保存窗口、串口、快捷指令及下载目录等设置。该文件属于用户数据，不包含在开源仓库中。

## 许可证

本项目采用仓库根目录中的 [MIT License](../LICENSE)。
