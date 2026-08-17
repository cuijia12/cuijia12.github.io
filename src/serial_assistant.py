import ctypes
from ctypes import wintypes
from datetime import datetime
import binascii
import json
import os
from pathlib import Path
import queue
import re
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, simpledialog, ttk
from agent_api import AgentAPIController, DEFAULT_PORT as AGENT_API_DEFAULT_PORT
from t5l_download import DownloadWindow, file_id


APP_DIR = (os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, "frozen", False)
           else os.path.dirname(os.path.abspath(__file__)))
APP_VERSION = "1.1"
MAX_TRAFFIC_RECORDS = 5000
VISIBLE_TRAFFIC_RECORDS = 1000
RX_UI_TIME_BUDGET = 0.010
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
REFERENCE_INI = os.path.abspath(os.path.join(APP_DIR, "..", "sscom5.13", "sscom51.ini"))
T5L_TOOL_DIR = os.path.abspath(os.path.join(APP_DIR, "..", "DGUS_V7649", "DGUS_V7649-6", "TOOL"))
T5L_TOOL_EXE = os.path.join(T5L_TOOL_DIR, "AllTool.exe")
HELP_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>串口助手 v1.1 使用帮助</title>
<style>
:root{--bg:#f4f7fb;--card:#fff;--text:#243247;--muted:#66758a;--line:#dce5f0;--blue:#3478f6;--green:#16845b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:"Segoe UI Variable Text","Microsoft YaHei UI",sans-serif;line-height:1.75}
header{background:linear-gradient(135deg,#172b4d,#285d9f);color:#fff;padding:50px 24px 42px}header div,main,footer{max-width:1020px;margin:auto}
h1{font-size:34px;margin:0 0 8px}.subtitle{opacity:.8;margin:0}.badge{display:inline-block;margin-top:16px;padding:4px 12px;border:1px solid #ffffff55;border-radius:20px}
main{padding:26px 18px 40px}.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:22px 26px;margin-bottom:18px;box-shadow:0 5px 18px #1e35540d}
h2{font-size:21px;margin:0 0 13px;color:#172b4d}h3{font-size:16px;margin:18px 0 7px}ol,ul{padding-left:24px;margin:8px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}.grid .card{margin:0}
code{font-family:"Cascadia Code",Consolas,monospace;background:#edf3fb;padding:2px 6px;border-radius:5px}.tip{border-left:4px solid var(--blue);padding:9px 14px;background:#eef5ff;border-radius:4px}.warn{border-left-color:#d99020;background:#fff7e9}.ok{color:var(--green);font-weight:600}
nav a{color:#dbeaff;margin-right:18px;text-decoration:none}footer{padding:0 18px 32px;color:var(--muted);text-align:center}@media(max-width:600px){h1{font-size:28px}.card{padding:18px}}
</style>
</head>
<body>
<header><div><h1>串口助手</h1><p class="subtitle">多串口调试与 T5L 在线下载一体化工具</p><span class="badge">版本 v1.1 · Windows</span><nav><a href="#serial">串口调试</a><a href="#quick">快捷指令</a><a href="#t5l">T5L下载</a><a href="#api">Agent API</a><a href="#faq">注意事项</a><a href="https://cuijia12.github.io/" target="_blank" rel="noopener">作者主页</a></nav></div></header>
<main>
<section class="card"><h2>快速开始</h2><ol><li>在“串口连接”区域选择端口和波特率，其他参数可在“串口设置”中调整。</li><li>点击“打开串口”，在数据发送区输入文本或 HEX 数据。</li><li>按需选择 HEX 发送、自动换行、校验算法及校验范围，然后点击“发送数据”。</li><li>发送和接收内容会实时显示在同一个通讯记录区域。</li></ol><p class="tip">发布版为单文件 EXE，可直接在 Windows 电脑运行，无需安装 Python 或 pyserial。</p></section>
<div class="grid">
<section class="card" id="serial"><h2>多串口调试</h2><ul><li>可同时创建并打开多个 COM 口，每个串口使用独立标签、句柄和接收线程。</li><li>标签状态点：绿色表示已打开，红色表示已关闭，黄色表示正被 T5L 下载占用。</li><li>点击标签切换当前串口；通讯记录、收发计数和参数跟随标签独立切换。</li><li>点击标签右侧 × 可关闭串口并移除标签，不影响其他已打开串口。</li><li>自动扫描 COM 端口并显示驱动名称，支持常用波特率、数据位、校验位和停止位。</li><li>支持 HEX/字符收发、GBK/UTF-8/ASCII 编码、自动滚屏和日志保存。</li></ul></section>
<section class="card"><h2>发送与校验</h2><ul><li>支持定时发送和自动追加 CRLF。</li><li>支持 Modbus CRC16、CCITT CRC16、CRC32、ADD8、ADD16、XOR8。</li><li>校验范围可选择第1至第32字节开始，结束位置支持末尾或倒数第1至第32字节。</li><li>校验同时作用于普通发送、快捷指令和循环发送。</li></ul><p>HEX 示例：<code>5A A5 04 83 00 14 01</code></p></section>
</div>
<section class="card" id="quick"><h2>快捷指令</h2><ul><li>共10页，每页30条，可保存300条指令。</li><li>每条指令可单独设置 HEX/字符模式、备注、延时和是否参与循环发送。</li><li>双击备注按钮可修改名称；支持导入 SSCOM INI 配置。</li><li>通过“快捷指令 → 显示快捷指令”可打开或关闭右侧区域，状态自动保存。</li></ul></section>
<section class="card" id="t5l"><h2>T5L 在线下载</h2><ul><li>点击顶部“T5L 下载”在主窗口内切换，无需打开额外窗口。</li><li>下载只临时占用当前选中的串口标签，其他已打开串口继续正常收发。</li><li>下载结束后恢复被占用标签原来的串口开关状态和参数。</li><li>记忆上次 DWIN_SET 文件夹和下载列表。</li><li>支持选择目录、单独选择文件、移出下载列表；移出只影响本次下载列表，不删除源文件。</li><li>快速选择支持13文件、14文件、22文件和 <code>T5L51.bin</code>。</li><li>支持 T5L51 8051代码更新以及 ICL 下载前停止 DGUS 刷新的防卡死处理。</li></ul><p class="tip warn">下载过程中请保持供电和串口连接稳定。目标屏幕内核必须支持相应的在线更新协议。</p></section>
<section class="card" id="api"><h2>Agent API</h2><ul><li>程序运行后在 <code>127.0.0.1:18765</code> 提供本机 HTTP JSON 接口。</li><li>支持状态查询、打开/关闭串口、HEX/字符发送与最新接收数据读取、启动/停止 T5L 下载。</li><li>接口与 GUI 共用串口会话，并使用 <code>config.json</code> 中的随机 Token 鉴权。</li><li>源码包中的 <code>agent_api.py</code> 可作为 Codex 和自动化脚本的命令行客户端。</li></ul></section>
<section class="card"><h2>界面与数据保存</h2><ul><li>20种界面风格，分为明亮、深色、科技、护眼和经典五类。</li><li>窗口尺寸与位置、串口参数、发送内容、快捷指令、主题和工程路径都会自动保存。</li><li>配置保存在程序同目录的 <code>config.json</code>，移动 EXE 时可按需一同复制。</li></ul></section>
<section class="card" id="faq"><h2>注意事项</h2><ul><li>本程序仅支持 Windows，串口层直接调用 Windows API。</li><li>HEX 输入可使用空格、逗号、分号、冒号或短横线分隔，必须保持每个字节为两位十六进制。</li><li>同一串口不能同时被其他串口软件占用。</li><li>若端口列表未更新，请点击“刷新”并检查 USB 串口驱动。</li></ul></section>
<section class="card"><h2>作者信息</h2><p>微信号：<strong>c402306805</strong></p><p>个人网页：<a href="https://cuijia12.github.io/" target="_blank" rel="noopener">https://cuijia12.github.io/</a></p><p class="ok">感谢使用串口助手。</p></section>
</main><footer>串口助手 v1.1 · 本帮助页面内置于程序，可离线查看</footer>
</body></html>"""
THEMES = {
    "现代浅色": {"bg":"#F3F6FA","card":"#FFFFFF","header":"#172B4D","header_fg":"#FFFFFF","muted":"#52647A","text":"#27364B","field":"#F8FAFD","border":"#DCE4EF","primary":"#3478F6","primary_hover":"#2367DA","status_bg":"#EAF2FF","status_fg":"#2865C7","rx":"#25364D","tx":"#16744A"},
    "纯净白色": {"bg":"#FAFAFA","card":"#FFFFFF","header":"#333333","header_fg":"#FFFFFF","muted":"#666666","text":"#202020","field":"#FFFFFF","border":"#DDDDDD","primary":"#246BCE","primary_hover":"#1758B0","status_bg":"#E9F1FC","status_fg":"#205FAF","rx":"#222222","tx":"#17734A"},
    "暖阳米色": {"bg":"#F8F2E8","card":"#FFFDF8","header":"#6D543A","header_fg":"#FFFFFF","muted":"#756451","text":"#40362C","field":"#FFFCF5","border":"#E4D6C3","primary":"#C77B30","primary_hover":"#A96325","status_bg":"#F8E8D2","status_fg":"#985A20","rx":"#44382E","tx":"#4D794E"},
    "樱花粉色": {"bg":"#FFF2F6","card":"#FFFAFC","header":"#7A4056","header_fg":"#FFFFFF","muted":"#805C69","text":"#4A2F39","field":"#FFF8FB","border":"#EACBD6","primary":"#D85E87","primary_hover":"#BC466F","status_bg":"#FBE1EA","status_fg":"#A63D62","rx":"#50343E","tx":"#308064"},
    "深色夜间": {"bg":"#151A23","card":"#202733","header":"#0D1117","header_fg":"#E6EDF3","muted":"#AAB6C5","text":"#E6EDF3","field":"#111720","border":"#344052","primary":"#4D8DFF","primary_hover":"#6AA0FF","status_bg":"#263955","status_fg":"#8AB4FF","rx":"#D8E1EC","tx":"#62D69B"},
    "暗夜蓝黑": {"bg":"#0C1420","card":"#152234","header":"#07101B","header_fg":"#EAF3FF","muted":"#91A7C0","text":"#DCE9F7","field":"#0B1726","border":"#29415D","primary":"#378BFF","primary_hover":"#5BA0FF","status_bg":"#17365A","status_fg":"#83B9FF","rx":"#D7E6F5","tx":"#4CD6A0"},
    "炭黑橙光": {"bg":"#1B1A18","card":"#292724","header":"#11100F","header_fg":"#FFF5E8","muted":"#B9AA98","text":"#F0E6D8","field":"#171614","border":"#484039","primary":"#E58836","primary_hover":"#F29C50","status_bg":"#50351E","status_fg":"#FFC17D","rx":"#EEE3D4","tx":"#8DD39C"},
    "深紫暮色": {"bg":"#191522","card":"#282137","header":"#100C18","header_fg":"#F3EAFF","muted":"#B3A3C8","text":"#ECE3F8","field":"#15101F","border":"#443758","primary":"#9A6BE8","primary_hover":"#B184F3","status_bg":"#3C2B58","status_fg":"#C9A7FF","rx":"#E9DFF5","tx":"#70D2B1"},
    "科技蓝": {"bg":"#EAF3FB","card":"#F8FCFF","header":"#063B66","header_fg":"#EAF7FF","muted":"#426984","text":"#123B57","field":"#EEF8FF","border":"#BCD9ED","primary":"#0089D6","primary_hover":"#0075B8","status_bg":"#D9F2FF","status_fg":"#006B9F","rx":"#174963","tx":"#008563"},
    "赛博青色": {"bg":"#E6FAFA","card":"#F6FFFF","header":"#064E55","header_fg":"#E9FFFF","muted":"#39747A","text":"#123F43","field":"#ECFFFF","border":"#A9DCDD","primary":"#00A9AD","primary_hover":"#008C91","status_bg":"#D1F4F3","status_fg":"#007D80","rx":"#174A4D","tx":"#08745C"},
    "电光紫色": {"bg":"#F2EDFF","card":"#FBF9FF","header":"#422477","header_fg":"#FFFFFF","muted":"#705C8F","text":"#382755","field":"#F8F5FF","border":"#D5C8EB","primary":"#7952D6","primary_hover":"#6240BB","status_bg":"#E9E0FC","status_fg":"#603DB5","rx":"#412E5E","tx":"#23816B"},
    "量子靛蓝": {"bg":"#EDEFFC","card":"#F9FAFF","header":"#1C3271","header_fg":"#F3F6FF","muted":"#596B98","text":"#26345D","field":"#F3F5FF","border":"#C8CEE8","primary":"#425ED4","primary_hover":"#3049B8","status_bg":"#DEE4FC","status_fg":"#354DB5","rx":"#2D3C68","tx":"#197A68"},
    "护眼绿色": {"bg":"#EDF3EB","card":"#F9FCF7","header":"#315847","header_fg":"#F5FFF8","muted":"#587064","text":"#29453A","field":"#F2F8EF","border":"#C8D9C7","primary":"#3B8264","primary_hover":"#2F6E53","status_bg":"#DDEEE2","status_fg":"#286247","rx":"#334D42","tx":"#217A51"},
    "薄荷清新": {"bg":"#ECF8F2","card":"#F9FFFC","header":"#286554","header_fg":"#F2FFF9","muted":"#52786B","text":"#284C40","field":"#F2FCF7","border":"#BFDCCE","primary":"#35A279","primary_hover":"#288966","status_bg":"#D9F1E6","status_fg":"#257458","rx":"#315448","tx":"#167653"},
    "森林晨雾": {"bg":"#E7EEE8","card":"#F6F9F6","header":"#354D3A","header_fg":"#F5FFF5","muted":"#647468","text":"#354239","field":"#EFF4EF","border":"#C4D0C5","primary":"#577D5D","primary_hover":"#45684B","status_bg":"#DCE8DD","status_fg":"#44684A","rx":"#39493D","tx":"#2A7048"},
    "茶园浅褐": {"bg":"#F1EFE3","card":"#FCFAF2","header":"#5B5840","header_fg":"#FFFFF4","muted":"#78745B","text":"#464432","field":"#F8F6EB","border":"#D8D3B9","primary":"#7B8151","primary_hover":"#666C40","status_bg":"#E9E6CE","status_fg":"#62683D","rx":"#4C4937","tx":"#547041"},
    "经典灰色": {"bg":"#E8E8E8","card":"#F4F4F4","header":"#454545","header_fg":"#FFFFFF","muted":"#595959","text":"#222222","field":"#FFFFFF","border":"#BDBDBD","primary":"#5C6B7A","primary_hover":"#485664","status_bg":"#DDE1E5","status_fg":"#3C4B59","rx":"#202020","tx":"#175F91"},
    "Windows经典": {"bg":"#D4D0C8","card":"#ECE9D8","header":"#0A246A","header_fg":"#FFFFFF","muted":"#444444","text":"#000000","field":"#FFFFFF","border":"#9A9A9A","primary":"#316AC5","primary_hover":"#2557A0","status_bg":"#D6E3F7","status_fg":"#173F7A","rx":"#000000","tx":"#005E8A"},
    "复古米灰": {"bg":"#E7E1D5","card":"#F4F0E7","header":"#5A5146","header_fg":"#FFFDF7","muted":"#6D655B","text":"#35312C","field":"#FFFDF8","border":"#C8BFB0","primary":"#786B5C","primary_hover":"#625548","status_bg":"#E4DCCF","status_fg":"#5C5044","rx":"#38332E","tx":"#3C6B5A"},
    "工业银色": {"bg":"#DDE1E4","card":"#F0F2F3","header":"#39434B","header_fg":"#FFFFFF","muted":"#59636B","text":"#252C31","field":"#F9FAFA","border":"#B7C0C6","primary":"#546D7C","primary_hover":"#435B69","status_bg":"#D5E0E6","status_fg":"#405B69","rx":"#283137","tx":"#296A58"},
}
THEME_GROUPS = {
    "明亮风格": ["现代浅色","纯净白色","暖阳米色","樱花粉色"],
    "深色风格": ["深色夜间","暗夜蓝黑","炭黑橙光","深紫暮色"],
    "科技风格": ["科技蓝","赛博青色","电光紫色","量子靛蓝"],
    "护眼风格": ["护眼绿色","薄荷清新","森林晨雾","茶园浅褐"],
    "经典风格": ["经典灰色","Windows经典","复古米灰","工业银色"],
}
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class DCB(ctypes.Structure):
    _fields_ = [("DCBlength", wintypes.DWORD), ("BaudRate", wintypes.DWORD),
                ("flags", wintypes.DWORD), ("wReserved", wintypes.WORD),
                ("XonLim", wintypes.WORD), ("XoffLim", wintypes.WORD),
                ("ByteSize", ctypes.c_ubyte), ("Parity", ctypes.c_ubyte),
                ("StopBits", ctypes.c_ubyte), ("XonChar", ctypes.c_char),
                ("XoffChar", ctypes.c_char), ("ErrorChar", ctypes.c_char),
                ("EofChar", ctypes.c_char), ("EvtChar", ctypes.c_char),
                ("wReserved1", wintypes.WORD)]


class COMMTIMEOUTS(ctypes.Structure):
    _fields_ = [("ReadIntervalTimeout", wintypes.DWORD),
                ("ReadTotalTimeoutMultiplier", wintypes.DWORD),
                ("ReadTotalTimeoutConstant", wintypes.DWORD),
                ("WriteTotalTimeoutMultiplier", wintypes.DWORD),
                ("WriteTotalTimeoutConstant", wintypes.DWORD)]


class WindowsSerial:
    def __init__(self):
        self.handle = None
        self.k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.k32.CreateFileW.restype = wintypes.HANDLE
        self.k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                         ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        self.k32.GetCommState.argtypes = [wintypes.HANDLE, ctypes.POINTER(DCB)]
        self.k32.GetCommState.restype = wintypes.BOOL
        self.k32.SetCommState.argtypes = [wintypes.HANDLE, ctypes.POINTER(DCB)]
        self.k32.SetCommState.restype = wintypes.BOOL
        self.k32.BuildCommDCBW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(DCB)]
        self.k32.BuildCommDCBW.restype = wintypes.BOOL
        self.k32.SetCommTimeouts.argtypes = [wintypes.HANDLE, ctypes.POINTER(COMMTIMEOUTS)]
        self.k32.SetCommTimeouts.restype = wintypes.BOOL
        self.k32.SetupComm.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD]
        self.k32.SetupComm.restype = wintypes.BOOL
        self.k32.PurgeComm.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.k32.PurgeComm.restype = wintypes.BOOL
        self.k32.FlushFileBuffers.argtypes = [wintypes.HANDLE]
        self.k32.FlushFileBuffers.restype = wintypes.BOOL
        self.k32.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                      ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        self.k32.ReadFile.restype = wintypes.BOOL
        self.k32.WriteFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                       ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        self.k32.WriteFile.restype = wintypes.BOOL
        self.k32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.k32.CloseHandle.restype = wintypes.BOOL

    @property
    def is_open(self):
        return self.handle not in (None, INVALID_HANDLE_VALUE)

    def open(self, port, baud, data_bits, parity, stop_bits):
        self.close()
        path = "\\\\.\\" + port
        self.handle = self.k32.CreateFileW(path, 0xC0000000, 0, None, 3, 0, None)
        if self.handle == INVALID_HANDLE_VALUE:
            self.handle = None
            raise ctypes.WinError(ctypes.get_last_error())
        self.configure(baud,data_bits,parity,stop_bits)
        timeouts = COMMTIMEOUTS(30, 0, 30, 0, 1000)
        if not self.k32.SetCommTimeouts(self.handle, ctypes.byref(timeouts)):
            self.close(); raise ctypes.WinError(ctypes.get_last_error())
        if not self.k32.SetupComm(self.handle, 65536, 65536):
            self.close(); raise ctypes.WinError(ctypes.get_last_error())
        self.k32.PurgeComm(self.handle, 0x000F)

    def configure(self, baud, data_bits, parity, stop_bits):
        """保持端口打开，立即修改线路参数。"""
        if not self.is_open: raise RuntimeError("串口未打开")
        # 从驱动当前 DCB 开始修改，保留该 USB 串口驱动的专有标志。
        dcb = DCB(); dcb.DCBlength = ctypes.sizeof(DCB)
        if not self.k32.GetCommState(self.handle,ctypes.byref(dcb)):
            raise ctypes.WinError(ctypes.get_last_error())
        dcb.BaudRate=int(baud); dcb.ByteSize=int(data_bits)
        dcb.Parity={"无":0,"奇":1,"偶":2,"标记":3,"空格":4}[parity]
        dcb.StopBits={"1":0,"1.5":1,"2":2}[stop_bits]
        # fBinary=1、fParity 按选择设置；关闭软/硬件流控，避免数据被握手阻塞。
        dcb.flags |= 0x00000001
        if parity != "无": dcb.flags |= 0x00000002
        else: dcb.flags &= ~0x00000002
        dcb.flags &= ~((1<<2)|(1<<3)|(3<<4)|(1<<6)|(1<<7)|(1<<8)|(1<<9))
        dcb.flags = (dcb.flags & ~(3<<12)) | (1<<12)  # RTS_CONTROL_ENABLE
        dcb.flags = (dcb.flags & ~(3<<4)) | (1<<4)   # DTR_CONTROL_ENABLE
        if not self.k32.SetCommState(self.handle, ctypes.byref(dcb)):
            raise ctypes.WinError(ctypes.get_last_error())
        return self.get_settings()

    def read(self, size=4096):
        if not self.is_open: return b""
        buf = ctypes.create_string_buffer(size)
        count = wintypes.DWORD()
        if not self.k32.ReadFile(self.handle, buf, size, ctypes.byref(count), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return buf.raw[:count.value]

    def write(self, data):
        if not self.is_open: raise RuntimeError("串口未打开")
        count = wintypes.DWORD()
        buf = ctypes.create_string_buffer(data)
        if not self.k32.WriteFile(self.handle, buf, len(data), ctypes.byref(count), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return count.value

    def flush_output(self):
        """等待驱动发送队列中的字节全部送出。"""
        if not self.is_open: raise RuntimeError("串口未打开")
        if not self.k32.FlushFileBuffers(self.handle):
            raise ctypes.WinError(ctypes.get_last_error())

    def purge_input(self):
        """清除已经收到、但本阶段不再需要的数据包 OK 应答。"""
        if self.is_open and not self.k32.PurgeComm(self.handle, 0x0008):
            raise ctypes.WinError(ctypes.get_last_error())

    def set_read_timeout(self, milliseconds):
        """调整当前句柄读取超时；T5L实时应答使用更短超时。"""
        if not self.is_open: raise RuntimeError("串口未打开")
        ms = max(1, int(milliseconds))
        timeouts = COMMTIMEOUTS(ms, 0, ms, 0, 1000)
        if not self.k32.SetCommTimeouts(self.handle, ctypes.byref(timeouts)):
            raise ctypes.WinError(ctypes.get_last_error())

    def get_settings(self):
        """读取串口驱动当前实际生效的线路参数。"""
        if not self.is_open: raise RuntimeError("串口未打开")
        dcb=DCB(); dcb.DCBlength=ctypes.sizeof(DCB)
        if not self.k32.GetCommState(self.handle,ctypes.byref(dcb)):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"baud":int(dcb.BaudRate),"data":int(dcb.ByteSize),"parity":int(dcb.Parity),
                "stop":int(dcb.StopBits),"fParity":bool(dcb.flags & 0x2),"flags":int(dcb.flags)}

    def close(self):
        if self.is_open: self.k32.CloseHandle(self.handle)
        self.handle = None


def list_port_details():
    details = []
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM") as h:
            for i in range(winreg.QueryInfoKey(h)[1]):
                device_path,port=winreg.EnumValue(h,i)[0:2]
                friendly=""
                # SERIALCOMM 的值名通常是 \Device\...；到 Enum 中查对应 PortName 和 FriendlyName。
                def walk(key_path,depth=0):
                    nonlocal friendly
                    if friendly or depth>4: return
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,key_path) as key:
                            try:
                                if winreg.QueryValueEx(key,"PortName")[0]==port:
                                    parent=key_path.rsplit("\\",1)[0]
                                    try:
                                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,parent) as p: friendly=winreg.QueryValueEx(p,"FriendlyName")[0]
                                    except OSError: pass
                            except OSError: pass
                            for n in range(winreg.QueryInfoKey(key)[0]): walk(key_path+"\\"+winreg.EnumKey(key,n),depth+1)
                    except OSError: pass
                walk(r"SYSTEM\CurrentControlSet\Enum")
                label=friendly or device_path.replace("\\Device\\","")
                label=re.sub(r"\s*\("+re.escape(port)+r"\)\s*$","",label)
                details.append((port,f"{port}  {label}" if label else port))
    except OSError:
        pass
    unique={p:l for p,l in details}
    return sorted(unique.items(),key=lambda x:int(re.search(r"\d+",x[0]).group()))

def list_ports(): return [p for p,_ in list_port_details()]

def port_number(value):
    m=re.match(r"\s*(COM\d+)",value,re.IGNORECASE)
    return m.group(1).upper() if m else value.strip()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        # Tk 默认会在控件和主题尚未创建完成时先绘制主窗口，复杂表格会短暂
        # 显示成黑色占位块。启动阶段先隐藏，全部布局完成后再一次性呈现。
        self.withdraw()
        self.title(f"串口助手 v{APP_VERSION}")
        screen_w=self.winfo_screenwidth(); screen_h=self.winfo_screenheight()
        self.minsize(860, 560)
        self.configure(bg="#F3F6FA")
        self.serial = WindowsSerial()
        self.sessions = {}
        self.active_session_key = None
        self.t5l_active = False
        self.t5l_restore_open = False
        self.t5l_restore_session = None
        self.rx_queue = queue.Queue()
        self.reconfigure_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.rx_count = self.tx_count = 0
        self.traffic_history = []
        self.display_trim_counter = 0
        self.rx_pending = bytearray(); self.rx_pending_started = None; self.rx_flush_job = None
        self.cycle_job = None
        self.cycle_index = 0
        self.send_save_job = None
        self.timer_generation = 0
        self.loading_session = False
        self.poll_job = None
        self.config_data = self.load_config()
        self.agent_api_token=self.config_data.get("agent_api_token") or secrets.token_hex(24)
        self.agent_api_port=int(self.config_data.get("agent_api_port",AGENT_API_DEFAULT_PORT))
        self.agent_api=None; self.agent_api_job=None
        saved_geometry=self.config_data.get("window_geometry","")
        if re.fullmatch(r"\d+x\d+[+-]\d+[+-]\d+",saved_geometry):
            m=re.fullmatch(r"(\d+)x(\d+)([+-]\d+)([+-]\d+)",saved_geometry)
            w=max(860,min(int(m.group(1)),screen_w)); h=max(560,min(int(m.group(2)),screen_h))
            x=max(0,min(int(m.group(3)),screen_w-w)); y=max(0,min(int(m.group(4)),screen_h-h))
            self.geometry(f"{w}x{h}+{x}+{y}")
        else:
            self.geometry(f"{min(1240,screen_w-80)}x{min(760,screen_h-100)}+30+30")
        self.theme_name = tk.StringVar(value=self.config_data.get("theme", "现代浅色"))
        self.quick_panel_visible = tk.BooleanVar(value=self.config_data.get("quick_panel_visible", True))
        self._startup_complete=False
        self._was_minimized=False
        self._restore_cover=None
        self._quick_hidden_for_restore=False
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<Unmap>",self.on_root_unmap,add="+")
        self.bind("<Map>",self.on_root_map,add="+")
        self.create_ui()
        self.refresh_ports()
        self.apply_config()
        self.poll_job=self.after(60, self.poll_rx)
        self.start_agent_api()
        self.after_idle(self.show_ready_window)

    def show_ready_window(self):
        """在首帧布局完成后显示窗口，消除启动时约 0.2 秒的黑框闪烁。"""
        self.update_idletasks()
        target_geometry=self.geometry()
        match=re.match(r"(\d+x\d+)[+-]",target_geometry)
        size=match.group(1) if match else "1200x720"
        # 透明分层窗口在部分旧显卡上仍会留下黑色子控件；改在屏幕外进行
        # 一次真实合成，让 ttk.Entry/Combobox 获得完整的首帧像素。
        self.geometry(f"{size}-20000-20000")
        self.deiconify()
        self.update_idletasks()
        self.update()
        self.force_native_redraw()
        self.withdraw()
        self.geometry(target_geometry)
        self.update_idletasks()
        self.after_idle(self.reveal_painted_window)

    def reveal_painted_window(self):
        self.deiconify()
        if self.config_data.get("window_state")=="zoomed": self.state("zoomed")
        self.force_native_redraw()
        self._startup_complete=True
        self.lift()

    def on_root_unmap(self,event):
        if event.widget is self and self._startup_complete:
            self._was_minimized=True
            # 在窗口不可见期间预先盖住全部复杂控件；恢复首帧只需绘制一个
            # 纯色 Frame，避免显卡把数百个控件的黑色中间态暴露出来。
            c=THEMES.get(self.theme_name.get(),THEMES["现代浅色"])
            if self._restore_cover is None:
                # 只覆盖快捷指令面板。左侧内容由 DWM 保留，不再出现整窗闪烁。
                self._restore_cover=tk.Frame(self.quick_panel,bg=c["bg"],borderwidth=0,highlightthickness=0)
            else:
                self._restore_cover.configure(bg=c["bg"])
            self._restore_cover.place(x=0,y=0,relwidth=1,relheight=1)
            self._restore_cover.lift()
            # 快捷指令区包含大量 Entry/Button。Windows 从最小化恢复时会先把
            # 这些子控件映射成黑色占位，再补画主题背景。不可见期间先解除
            # 映射，恢复时在遮罩下面重新布局，避免中间帧出现在屏幕上。
            panes=self.main_pane.panes()
            self._quick_hidden_for_restore=(str(self.quick_panel) in panes)
            if self._quick_hidden_for_restore:
                self.quick_canvas.itemconfigure(self.quick_window_id,state="hidden")
            self.update_idletasks()

    def on_root_map(self,event):
        if event.widget is not self or not self._startup_complete or not self._was_minimized: return
        self._was_minimized=False
        if self._quick_hidden_for_restore and self.quick_panel_visible.get():
            self.quick_canvas.itemconfigure(self.quick_window_id,state="normal")
        self._quick_hidden_for_restore=False
        if self._restore_cover is not None:
            self._restore_cover.lift()
        # 在遮罩下面完成所有快捷控件的重新映射和主题绘制。
        self.update_idletasks()
        self.force_content_redraw_fast()
        self.after(1,self.finish_restore_redraw)

    def finish_restore_redraw(self):
        if self._restore_cover is not None:
            self._restore_cover.lift()
        self.update_idletasks()
        if self._restore_cover is not None:
            self._restore_cover.place_forget()

    def force_content_redraw_fast(self):
        """同步刷新子控件并擦除黑底，不重绘边框，也不等待 DWM。"""
        try:
            hwnd=wintypes.HWND(self.winfo_id())
            flags=0x0001|0x0004|0x0080|0x0100  # INVALIDATE/ERASE/ALLCHILDREN/UPDATENOW
            ctypes.windll.user32.RedrawWindow(hwnd,None,None,flags)
            ctypes.windll.user32.UpdateWindow(hwnd)
        except Exception:
            self.update_idletasks()

    def force_native_redraw(self):
        """同步刷新根窗口及全部原生子控件，避免 DWM 显示未初始化的黑底。"""
        try:
            hwnd=wintypes.HWND(self.winfo_id())
            flags=0x0001|0x0004|0x0080|0x0100|0x0400  # INVALIDATE/ERASE/ALLCHILDREN/UPDATENOW/FRAME
            ctypes.windll.user32.RedrawWindow(hwnd,None,None,flags)
            ctypes.windll.user32.UpdateWindow(hwnd)
            try: ctypes.windll.dwmapi.DwmFlush()
            except Exception: pass
        except Exception:
            self.update_idletasks()

    def load_config(self):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except Exception: return {}

    def create_ui(self):
        style = ttk.Style(self); style.theme_use("clam")
        self.option_add("*Font",("Segoe UI Variable Text",10))
        self.option_add("*Menu.Font",("Segoe UI Variable Text",10))
        self.create_checkmark_style(style)
        self.checksum=tk.StringVar(value="None")
        self.checksum_start=tk.StringVar(value="第1字节")
        self.checksum_end=tk.StringVar(value="末尾")
        range_starts=[f"第{i}字节" for i in range(1,33)]
        range_ends=["末尾"]+[f"倒数第{i}字节" for i in range(1,33)]
        style.configure(".", font=("Segoe UI Variable Text", 10), background="#F3F6FA", foreground="#27364B")
        style.configure("TFrame", background="#F3F6FA")
        style.configure("Card.TFrame", background="#FFFFFF")
        style.configure("TLabelframe", background="#FFFFFF", bordercolor="#DCE4EF", relief="solid", borderwidth=1)
        style.configure("TLabelframe.Label", background="#FFFFFF", foreground="#172B4D", font=("Segoe UI Variable Display", 11, "bold"))
        style.configure("TLabel", background="#F3F6FA", foreground="#52647A")
        style.configure("Card.TLabel", background="#FFFFFF", foreground="#52647A")
        style.configure("TCheckbutton", background="#FFFFFF", foreground="#40536A")
        style.map("TCheckbutton", background=[("active", "#FFFFFF")])
        style.configure("TButton", padding=(10, 6), borderwidth=0, background="#E8EEF6", foreground="#334A63")
        style.map("TButton", background=[("active", "#DCE7F5"), ("pressed", "#CEDDEF")])
        style.configure("Primary.TButton", padding=(16, 7), background="#3478F6", foreground="#FFFFFF", font=("Segoe UI Variable Text", 10, "bold"))
        style.map("Primary.TButton", background=[("active", "#2367DA"), ("pressed", "#1D58BC")])
        style.configure("Danger.TButton", padding=(16, 7), background="#FCE7E7", foreground="#C73535")
        style.map("Danger.TButton", background=[("active", "#F8D2D2")])
        style.configure("TEntry", padding=5, fieldbackground="#F8FAFD", bordercolor="#D8E1EC", lightcolor="#D8E1EC", darkcolor="#D8E1EC")
        style.configure("TCombobox", padding=5, fieldbackground="#F8FAFD", bordercolor="#D8E1EC", arrowsize=14)
        style.configure("Vertical.TScrollbar", background="#DCE4EF", troughcolor="#F5F7FA", borderwidth=0, arrowsize=12)
        style.configure("Status.TLabel", background="#EAF2FF", foreground="#2865C7", padding=(10, 5))
        style.configure("Quick.TEntry",padding=(4,2),font=("Segoe UI Variable Text",9))
        style.configure("Quick.TButton",padding=(5,2),font=("Segoe UI Variable Text",9),borderwidth=0)
        style.configure("Quick.TCheckbutton",padding=0)
        menu_defs=[]
        for title in ("通讯端口", "串口设置", "显示", "发送", "快捷指令", "小工具", "帮助"):
            sub = tk.Menu(self, tearoff=False,font=("Segoe UI Variable Text",10),borderwidth=1,relief="flat")
            if title == "通讯端口":
                sub.add_command(label="刷新端口", command=self.refresh_ports)
                sub.add_command(label="新增串口标签", command=self.new_serial_session)
                sub.add_command(label="打开/关闭串口", command=self.toggle_port)
                sub.add_command(label="关闭当前标签", command=self.close_active_session)
            elif title == "串口设置":
                sub.add_command(label="串口参数...",command=self.open_serial_settings)
            elif title == "显示":
                theme_menu=tk.Menu(sub,tearoff=False)
                for group_name,theme_names in THEME_GROUPS.items():
                    group_menu=tk.Menu(theme_menu,tearoff=False)
                    for theme_name in theme_names:
                        group_menu.add_radiobutton(label=theme_name,variable=self.theme_name,value=theme_name,command=self.theme_selected)
                    theme_menu.add_cascade(label=group_name,menu=group_menu)
                sub.add_cascade(label="界面风格",menu=theme_menu)
            elif title == "快捷指令":
                sub.add_checkbutton(label="显示快捷指令",variable=self.quick_panel_visible,command=self.toggle_quick_panel)
                sub.add_separator()
                sub.add_command(label="导入 SSCOM INI", command=self.import_ini)
                sub.add_command(label="清空快捷指令", command=self.clear_quick)
            elif title == "小工具":
                sub.add_command(label="T5L 下载...",command=self.open_t5l_download)
                sub.add_separator()
                sub.add_command(label="打开原工具目录",command=self.open_t5l_tool_folder)
            elif title == "帮助":
                sub.add_command(label="使用帮助（离线网页）",command=self.open_help_page)
                sub.add_command(label="作者主页（在线）",command=self.open_online_homepage)
                sub.add_separator()
                sub.add_command(
                    label="关于",
                    command=lambda: messagebox.showinfo(
                        "关于",
                        f"串口助手 v{APP_VERSION}\n兼容 SSCOM 常用操作习惯\n\n作者微信：c402306805\n个人网页：https://cuijia12.github.io/"))
            else: sub.add_command(label=title, state="disabled")
            menu_defs.append((title,sub))
        self.menu_bar=tk.Frame(self,bg="#F2F4F7",height=42,highlightthickness=0)
        self.menu_bar.pack(fill="x"); self.menu_bar.pack_propagate(False)
        self.menu_buttons=[]
        tk.Label(self.menu_bar,text="◫",bg="#F2F4F7",fg="#7D8793",font=("Segoe UI Symbol",14)).pack(side="left",padx=(10,12))
        self.serial_mode_btn=tk.Button(self.menu_bar,text="串口助手",command=self.focus_serial_mode,
                                       relief="flat",borderwidth=0,padx=14,pady=7,cursor="hand2",
                                       font=("Segoe UI Variable Text",10,"bold"))
        self.serial_mode_btn.pack(side="left",fill="y")
        self.t5l_mode_btn=tk.Button(self.menu_bar,text="T5L 下载",command=self.open_t5l_download,
                                    relief="flat",borderwidth=0,padx=14,pady=7,cursor="hand2",
                                    font=("Segoe UI Variable Text",10))
        self.t5l_mode_btn.pack(side="left",fill="y",padx=(0,10))
        for title,sub in menu_defs:
            btn=tk.Menubutton(self.menu_bar,text=title,menu=sub,bg="#F2F4F7",fg="#66717E",activebackground="#E3E7ED",activeforeground="#26313D",
                              relief="flat",borderwidth=0,padx=11,pady=8,font=("Segoe UI Variable Text",10),cursor="hand2")
            btn.pack(side="left",fill="y")
            btn.bind("<Button-1>",lambda event,m=sub,b=btn:self.show_top_menu(event,b,m))
            btn.bind("<Return>",lambda event,m=sub,b=btn:self.show_top_menu(event,b,m))
            btn.bind("<Enter>",lambda _event,b=btn:b.configure(relief="flat",background=b.cget("activebackground")))
            btn.bind("<Leave>",lambda _event,b=btn:b.configure(background=self.menu_bar.cget("background")))
            self.menu_buttons.append(btn)
        self.port = tk.StringVar(); self.baud = tk.StringVar(value="115200")
        self.data_bits = tk.StringVar(value="8"); self.parity = tk.StringVar(value="无"); self.stop_bits = tk.StringVar(value="1")
        self.flow_control=tk.StringVar(value="无")
        self.status=tk.StringVar(value="●  串口未打开")

        body=ttk.Panedwindow(self,orient="horizontal"); body.pack(fill="both",expand=True,padx=14,pady=(8,7))
        left=ttk.Frame(body); right=ttk.Frame(body,width=340); body.add(left,weight=4); body.add(right,weight=2)
        self.main_pane=body; self.quick_panel=right
        self.session_bar=ttk.Frame(left); self.session_bar.pack(fill="x",pady=(0,5))
        self.session_tabs=ttk.Frame(self.session_bar); self.session_tabs.pack(side="left",fill="x",expand=True)
        ttk.Button(self.session_bar,text="＋ 串口",command=self.new_serial_session).pack(side="right",padx=(5,0))
        recv_box=ttk.LabelFrame(left,text="  通讯记录  ",padding=10); recv_box.pack(fill="both",expand=True)
        recv_toolbar=ttk.Frame(recv_box); recv_toolbar.pack(fill="x")
        self.hex_recv=tk.BooleanVar(); self.timestamp=tk.BooleanVar(); self.autoscroll=tk.BooleanVar(value=True)
        ttk.Checkbutton(recv_toolbar,text="HEX显示",variable=self.hex_recv,command=self.render_traffic_history).pack(side="left")
        ttk.Checkbutton(recv_toolbar,text="时间戳",variable=self.timestamp,command=self.timestamp_display_changed).pack(side="left",padx=(8,3))
        ttk.Label(recv_toolbar,text="超时").pack(side="left")
        self.timestamp_timeout=tk.StringVar(value="40")
        timeout_entry=ttk.Entry(recv_toolbar,textvariable=self.timestamp_timeout,width=5)
        timeout_entry.pack(side="left",padx=(3,2)); ttk.Label(recv_toolbar,text="ms").pack(side="left")
        timeout_entry.bind("<Return>",self.timestamp_timeout_changed)
        timeout_entry.bind("<FocusOut>",self.timestamp_timeout_changed)
        ttk.Checkbutton(recv_toolbar,text="自动滚屏",variable=self.autoscroll).pack(side="left")
        ttk.Button(recv_toolbar,text="保存日志",command=self.save_log).pack(side="right")
        ttk.Button(recv_toolbar,text="清空",command=self.clear_traffic).pack(side="right",padx=5)
        recv_content=ttk.Frame(recv_box,style="Card.TFrame"); recv_content.pack(fill="both",expand=True,pady=(8,0))
        recv_scroll=ttk.Scrollbar(recv_content,orient="vertical",style="Vertical.TScrollbar")
        self.recv=tk.Text(recv_content,wrap="word",font=("Cascadia Code",10),undo=False,bg="#F8FAFD",fg="#27364B",insertbackground="#3478F6",selectbackground="#CFE0FF",relief="flat",padx=12,pady=8,spacing1=0,spacing2=0,spacing3=1,yscrollcommand=recv_scroll.set)
        recv_scroll.configure(command=self.recv.yview); recv_scroll.pack(side="right",fill="y"); self.recv.pack(side="left",fill="both",expand=True)
        self.bind_context_menu(self.recv,readonly=True)
        self.recv.tag_configure("rx", foreground="#25364D")
        self.recv.tag_configure("tx", foreground="#16744A")
        self.recv.tag_configure("error", foreground="#D83A3A")

        send_box=ttk.LabelFrame(left,text="  数据发送  ",padding=(7,4)); send_box.pack(fill="x",pady=(5,0))
        self.send_text=tk.Text(send_box,height=2,font=("Cascadia Code",10),bg="#F8FAFD",fg="#27364B",insertbackground="#3478F6",selectbackground="#CFE0FF",relief="flat",padx=8,pady=4,spacing1=1,spacing3=1); self.send_text.pack(fill="x")
        self.bind_context_menu(self.send_text)
        self.send_text.bind("<<Modified>>",self.on_send_text_modified)
        send_tools=ttk.Frame(send_box); send_tools.pack(fill="x",pady=(2,0))
        self.hex_send=tk.BooleanVar(); self.newline=tk.BooleanVar(); self.timer_on=tk.BooleanVar(); self.interval=tk.StringVar(value="1000")
        ttk.Checkbutton(send_tools,text="HEX发送",variable=self.hex_send).pack(side="left")
        ttk.Checkbutton(send_tools,text="自动换行",variable=self.newline).pack(side="left",padx=8)
        ttk.Checkbutton(send_tools,text="定时发送",variable=self.timer_on,command=self.timer_changed).pack(side="left")
        ttk.Entry(send_tools,textvariable=self.interval,width=8).pack(side="left",padx=(4,2)); ttk.Label(send_tools,text="ms").pack(side="left")
        ttk.Button(send_tools,text="发送数据  ➜",style="Primary.TButton",command=self.send_current).pack(side="right")

        top = ttk.LabelFrame(left, text="  串口连接  ", padding=(5,3)); top.pack(fill="x",pady=(4,0))
        items = [("端口", self.port, [], 22), ("波特率", self.baud, ["1200","2400","4800","9600","19200","38400","57600","115200","230400","460800","921600"], 9)]
        for i,(label,var,vals,width) in enumerate(items):
            ttk.Label(top,text=label,style="Card.TLabel").grid(row=0,column=i*2,padx=(1,2),pady=0)
            cb=ttk.Combobox(top,textvariable=var,values=vals,width=width,state="normal" if label=="波特率" else "readonly")
            cb.grid(row=0,column=i*2+1,padx=(0,4),pady=0)
            if label=="端口":
                self.port_box=cb
                # 输入框保持紧凑；下拉列表单独加宽以显示完整设备名。
                self.tk.call("ttk::combobox::PopdownWindow",cb)
                popdown=self.tk.call("ttk::combobox::PopdownWindow",cb)
                self.tk.call(popdown+".f.l","configure","-width",48)
            cb.bind("<<ComboboxSelected>>",lambda _e,n=label:self.serial_parameter_changed(n))
            if label=="波特率":
                cb.bind("<Return>",lambda _e:self.serial_parameter_changed("波特率"))
                cb.bind("<FocusOut>",lambda _e:self.serial_parameter_changed("波特率"))
            self.serial_controls=getattr(self,"serial_controls",[]); self.serial_controls.append(cb)
        ttk.Button(top,text="刷新",command=self.refresh_ports).grid(row=0,column=4,padx=3,pady=0,sticky="ew")
        self.open_btn=ttk.Button(top,text="打开串口",style="Primary.TButton",command=self.toggle_port)
        self.open_btn.grid(row=0,column=5,padx=3,pady=0,sticky="ew")
        ttk.Label(top,textvariable=self.status,style="Status.TLabel").grid(row=0,column=6,columnspan=3,padx=3,pady=0,sticky="ew")
        checksum_row=ttk.Frame(top,style="Card.TFrame"); checksum_row.grid(row=1,column=0,columnspan=9,padx=1,pady=(1,0),sticky="w")
        ttk.Label(checksum_row,text="加校验",style="Card.TLabel").pack(side="left",padx=(0,3))
        ttk.Combobox(checksum_row,textvariable=self.checksum,values=["None","Modbus CRC16","CCITT CRC16","CRC32","ADD8","ADD16","XOR8"],width=13,state="readonly").pack(side="left",padx=(0,10))
        ttk.Label(checksum_row,text="范围",style="Card.TLabel").pack(side="left",padx=(0,3))
        ttk.Combobox(checksum_row,textvariable=self.checksum_start,values=range_starts,width=7,state="readonly").pack(side="left",padx=(0,4))
        ttk.Label(checksum_row,text="至",style="Card.TLabel").pack(side="left",padx=(0,4))
        ttk.Combobox(checksum_row,textvariable=self.checksum_end,values=range_ends,width=10,state="readonly").pack(side="left")

        quick=ttk.LabelFrame(right,text="  快捷指令  ",padding=6); quick.pack(fill="both",expand=True,padx=(8,0))
        qtools=ttk.Frame(quick); qtools.pack(fill="x")
        self.cycle_send=tk.BooleanVar()
        ttk.Checkbutton(qtools,text="循环发送",variable=self.cycle_send,command=self.cycle_changed).pack(side="left")
        ttk.Button(qtools,text="导入INI",command=self.import_ini).pack(side="left",padx=5)
        ttk.Button(qtools,text="清空",command=self.clear_quick).pack(side="left")
        page_tools=ttk.Frame(quick); page_tools.pack(fill="x",pady=(3,2))
        ttk.Label(page_tools,text="快捷页").pack(side="left")
        self.quick_page_var=tk.IntVar(value=max(1,min(10,int(self.config_data.get("quick_page",1)))))
        ttk.Button(page_tools,text="上一页",command=lambda:self.change_quick_page(-1)).pack(side="left",padx=(8,3))
        self.quick_page_box=ttk.Combobox(page_tools,textvariable=self.quick_page_var,values=list(range(1,11)),width=3,state="readonly")
        self.quick_page_box.pack(side="left",padx=3); self.quick_page_box.bind("<<ComboboxSelected>>",lambda _e:self.change_quick_page(0))
        ttk.Label(page_tools,text="/ 10 页").pack(side="left")
        ttk.Button(page_tools,text="下一页",command=lambda:self.change_quick_page(1)).pack(side="left",padx=3)
        canvas=tk.Canvas(quick,highlightthickness=0,bg="#FFFFFF"); self.quick_canvas=canvas
        scroll=ttk.Scrollbar(quick,orient="vertical",command=canvas.yview)
        self.quick_inner=ttk.Frame(canvas); self.quick_inner.bind("<Configure>",lambda e:canvas.configure(scrollregion=canvas.bbox("all")))
        window_id=canvas.create_window((0,0),window=self.quick_inner,anchor="nw")
        self.quick_window_id=window_id
        canvas.bind("<Configure>",lambda e:canvas.itemconfigure(window_id,width=e.width))
        canvas.configure(yscrollcommand=scroll.set); scroll.pack(side="right",fill="y"); canvas.pack(fill="both",expand=True)
        ttk.Label(self.quick_inner,text="HEX").grid(row=0,column=0); ttk.Label(self.quick_inner,text="字符串（双击注释）").grid(row=0,column=1); ttk.Label(self.quick_inner,text="点击发送").grid(row=0,column=2); ttk.Label(self.quick_inner,text="延时 ms").grid(row=0,column=3); ttk.Label(self.quick_inner,text="循环").grid(row=0,column=4)
        self.quick_rows=[]
        for i in range(300):
            self.quick_rows.append((tk.StringVar(value=f"指令{i+1}"),tk.StringVar(),tk.BooleanVar(value=True),tk.StringVar(value="1000"),tk.BooleanVar(value=False)))
        self.quick_page_widgets=[]
        for i in range(30):
            hex_check=ttk.Checkbutton(self.quick_inner,style="Quick.TCheckbutton")
            hex_check.grid(row=i+1,column=0,padx=1,pady=0)
            data_entry=ttk.Entry(self.quick_inner,width=26,style="Quick.TEntry")
            data_entry.grid(row=i+1,column=1,padx=1,pady=1,sticky="ew")
            self.bind_context_menu(data_entry)
            data_entry.bind("<Double-Button-1>",lambda _e,s=i:self.edit_quick_note(self.quick_page_index(s)))
            send_button=ttk.Button(self.quick_inner,width=10,style="Quick.TButton",command=lambda s=i:self.send_quick(self.quick_page_index(s)))
            send_button.grid(row=i+1,column=2,padx=1,pady=1,sticky="ns")
            delay_entry=ttk.Entry(self.quick_inner,width=6,style="Quick.TEntry")
            delay_entry.grid(row=i+1,column=3,padx=1,pady=1); self.bind_context_menu(delay_entry)
            enabled_check=ttk.Checkbutton(self.quick_inner,style="Quick.TCheckbutton")
            enabled_check.grid(row=i+1,column=4,padx=1,pady=0)
            self.quick_page_widgets.append((hex_check,data_entry,send_button,delay_entry,enabled_check))
        self.show_quick_page()
        self.quick_inner.columnconfigure(1,weight=1)
        self.bind_quick_mousewheel(canvas)
        # 串口连接位于中间、数据发送位于最下方，通讯记录使用剩余空间。
        self.session_bar.pack_forget(); recv_box.pack_forget(); send_box.pack_forget(); top.pack_forget()
        send_box.pack(side="bottom",fill="x",pady=(4,0))
        top.pack(side="bottom",fill="x",pady=(4,0))
        self.session_bar.pack(side="top",fill="x",pady=(0,5))
        recv_box.pack(side="top",fill="both",expand=True)
        bottom=ttk.Frame(self); bottom.pack(side="bottom",fill="x",padx=14,pady=(1,10))
        self.counter=tk.StringVar(value="接收: 0 字节    发送: 0 字节")
        ttk.Label(bottom,textvariable=self.counter).pack(side="left")
        ttk.Button(bottom,text="清零计数",command=self.clear_count).pack(side="left",padx=8)
        ttk.Label(bottom,text="编码").pack(side="right"); self.encoding=tk.StringVar(value="GBK")
        ttk.Combobox(bottom,textvariable=self.encoding,values=["GBK","UTF-8","ASCII"],width=8,state="readonly").pack(side="right",padx=5)
        if not self.quick_panel_visible.get(): self.main_pane.forget(self.quick_panel)
        self.apply_theme()

    def open_t5l_download(self):
        if not getattr(self, "t5l_window", None):
            self.t5l_window = DownloadWindow(
                self, WindowsSerial, list_port_details, self.config_data, self.save_config,
                shared_settings=lambda: (self.port.get(), self.baud.get()),
                acquire_serial=self.acquire_t5l_serial,
                release_serial=self.release_t5l_serial,
                sync_shared_baud=self.sync_baud_from_t5l)
        if not getattr(self, "serial_page_layout", None):
            self.serial_page_layout=[]
            for widget in self.winfo_children():
                if widget not in (self.menu_bar, self.t5l_window) and widget.winfo_manager() == "pack":
                    self.serial_page_layout.append((widget, widget.pack_info()))
        for widget, _layout in self.serial_page_layout:
            widget.pack_forget()
        self.t5l_window.refresh_ports()
        self.t5l_window.pack(fill="both", expand=True)
        self.t5l_mode_btn.configure(font=("Segoe UI Variable Text",10,"bold"))
        self.serial_mode_btn.configure(font=("Segoe UI Variable Text",10))

    def focus_serial_mode(self):
        if getattr(self, "t5l_window", None):
            self.t5l_window.pack_forget()
        for widget, layout in getattr(self, "serial_page_layout", []):
            if not widget.winfo_manager(): widget.pack(**layout)
        self.serial_mode_btn.configure(font=("Segoe UI Variable Text",10,"bold"))
        self.t5l_mode_btn.configure(font=("Segoe UI Variable Text",10))

    def sync_t5l_baud_from_serial(self, port=None, baud=None):
        """同一 COM 口时，把串口助手波特率同步到已创建的 T5L 页面。"""
        window=getattr(self,"t5l_window",None)
        if window:
            window.sync_baud_from_serial(port or self.port.get(),baud or self.baud.get())

    def sync_baud_from_t5l(self, port, baud):
        """T5L 修改同一端口波特率时，更新对应串口会话及已打开句柄。"""
        key=port_number(port)
        if key!=port_number(self.port.get()): return False
        session=self.sessions.get(key)
        self.baud.set(str(baud))
        if session:
            session["settings"]["baud"]=str(baud)
            if session["serial"].is_open:
                try:
                    actual=session["serial"].configure(baud,self.data_bits.get(),self.parity.get(),self.stop_bits.get())
                    self.show_actual_settings(actual)
                except Exception as error:
                    messagebox.showerror("波特率同步失败",str(error))
                    return False
        self.save_config()
        return True

    def acquire_t5l_serial(self,requested_port=None):
        """只把当前标签的串口互斥切换给 T5L 下载，其他串口继续工作。"""
        if self.t5l_active:
            raise RuntimeError("T5L 下载串口正在使用中")
        requested=port_number(requested_port or self.port.get())
        session=self.sessions.get(requested)
        if not session:
            label=next((label for port,label in list_port_details() if port==requested),requested)
            session=self.create_serial_session(requested,label,self.current_serial_settings())
        if session and self.active_session_key!=session["key"]: self.switch_serial_session(session["key"])
        if not session: raise RuntimeError("请先选择 T5L 下载使用的串口")
        self.t5l_restore_session=session["key"]
        self.t5l_restore_open = session["serial"].is_open
        if session["serial"].is_open:
            session["stop_event"].set(); session["serial"].close()
        self.t5l_active = True
        self.open_btn.config(state="disabled")
        session["last_status"]="T5L 下载占用中"
        self.status.set(f"●  {session['key']} 已切换到 T5L 下载模式")
        self.refresh_session_tabs()

    def release_t5l_serial(self):
        if threading.current_thread() is not threading.main_thread():
            self.after(0,self.release_t5l_serial); return
        restore_open = self.t5l_restore_open
        restore_key = self.t5l_restore_session
        self.t5l_restore_open = False
        self.t5l_restore_session = None
        self.t5l_active = False
        if restore_key in self.sessions:
            self.switch_serial_session(restore_key)
            self.sessions[restore_key]["last_status"]=""
            self.open_btn.config(state="normal", text="打开串口")
            if restore_open:
                self.status.set(f"●  正在恢复 {restore_key}")
                self.toggle_port()
            else: self.status.set(f"●  {restore_key} 的 T5L 下载串口已释放")
        else: self.update_session_ui()
        self.refresh_session_tabs()

    def open_t5l_tool_folder(self):
        if os.path.isdir(T5L_TOOL_DIR): os.startfile(T5L_TOOL_DIR)
        else: messagebox.showerror("工具目录",f"目录不存在：\n{T5L_TOOL_DIR}")

    def open_help_page(self):
        """把内置说明写入临时 HTML，并使用系统默认浏览器离线打开。"""
        try:
            path=os.path.join(tempfile.gettempdir(),f"serial_assistant_help_v{APP_VERSION}.html")
            with open(path,"w",encoding="utf-8",newline="\n") as file:
                file.write(HELP_HTML)
            if not webbrowser.open_new_tab(Path(path).as_uri()): os.startfile(path)
        except Exception as error:
            messagebox.showerror("打开帮助失败",str(error))

    def open_online_homepage(self):
        try:
            if not webbrowser.open_new_tab("https://cuijia12.github.io/"):
                raise RuntimeError("未找到可用的默认浏览器")
        except Exception as error:
            messagebox.showerror("打开作者主页失败",str(error))

    def bind_context_menu(self,widget,readonly=False):
        widget.bind("<Button-3>",lambda event,w=widget,ro=readonly:self.show_context_menu(event,w,ro),add="+")

    def show_top_menu(self,event,button,menu):
        """在自绘菜单按钮下方可靠弹出原有 Tk 菜单。"""
        try:
            menu.tk_popup(button.winfo_rootx(),button.winfo_rooty()+button.winfo_height())
        finally:
            menu.grab_release()
        return "break"

    def toggle_quick_panel(self):
        panes=self.main_pane.panes()
        shown=str(self.quick_panel) in panes
        if self.quick_panel_visible.get() and not shown:
            self.main_pane.add(self.quick_panel,weight=2)
        elif not self.quick_panel_visible.get() and shown:
            self.main_pane.forget(self.quick_panel)
        self.save_config()

    def show_context_menu(self,event,widget,readonly=False):
        menu=tk.Menu(self,tearoff=False)
        has_selection=False
        try:
            if isinstance(widget,tk.Text): has_selection=bool(widget.tag_ranges("sel"))
            else: has_selection=bool(widget.selection_present())
        except tk.TclError: pass
        if not readonly:
            menu.add_command(label="剪切",state="normal" if has_selection else "disabled",command=lambda:widget.event_generate("<<Cut>>"))
        menu.add_command(label="复制",state="normal" if has_selection else "disabled",command=lambda:widget.event_generate("<<Copy>>"))
        if not readonly:
            menu.add_command(label="粘贴",command=lambda:widget.event_generate("<<Paste>>"))
            menu.add_separator()
        menu.add_command(label="全选",command=lambda:self.select_all(widget))
        menu.tk_popup(event.x_root,event.y_root)

    def select_all(self,widget):
        if isinstance(widget,tk.Text): widget.tag_add("sel","1.0","end-1c"); widget.mark_set("insert","1.0")
        else: widget.selection_range(0,"end"); widget.icursor("end")
        widget.focus_set()

    def open_serial_settings(self):
        win=tk.Toplevel(self); win.title("串口设置"); win.resizable(False,False); win.transient(self); win.grab_set()
        panel=ttk.LabelFrame(win,text="  参数设置  ",padding=14); panel.pack(padx=14,pady=(14,8),fill="both")
        port_details=list_port_details(); current_port=port_number(self.port.get())
        current_label=next((label for port,label in port_details if port==current_port),self.port.get())
        values={"端口":tk.StringVar(value=current_label),"波特率":tk.StringVar(value=self.baud.get()),"数据位":tk.StringVar(value=self.data_bits.get()),
                "停止位":tk.StringVar(value=self.stop_bits.get()),"校验位":tk.StringVar(value=self.parity.get()),"流控制":tk.StringVar(value=self.flow_control.get())}
        choices={"端口":[label for _,label in port_details],"波特率":["1200","2400","4800","9600","19200","38400","57600","115200","230400","460800","921600"],
                 "数据位":["5","6","7","8"],"停止位":["1","1.5","2"],"校验位":["无","奇","偶","标记","空格"],"流控制":["无","RTS/CTS","XON/XOFF"]}
        for row,label in enumerate(("端口","波特率","数据位","停止位","校验位","流控制")):
            ttk.Label(panel,text=label,style="Card.TLabel").grid(row=row,column=0,padx=(0,12),pady=5,sticky="w")
            box=ttk.Combobox(panel,textvariable=values[label],values=choices[label],width=22,state="normal" if label=="波特率" else "readonly")
            box.grid(row=row,column=1,pady=5)
            if label=="端口":
                box.bind("<<ComboboxSelected>>",lambda _event:self.load_serial_dialog_profile(values))
        buttons=ttk.Frame(win); buttons.pack(fill="x",padx=14,pady=(0,14))
        ttk.Button(buttons,text="取消",command=win.destroy).pack(side="right",padx=(6,0))
        ttk.Button(buttons,text="确定",style="Primary.TButton",command=lambda:self.apply_serial_dialog(win,values)).pack(side="right")
        win.update_idletasks(); x=self.winfo_rootx()+(self.winfo_width()-win.winfo_width())//2; y=self.winfo_rooty()+(self.winfo_height()-win.winfo_height())//2
        win.geometry(f"+{max(0,x)}+{max(0,y)}")

    def load_serial_dialog_profile(self,values):
        """在设置窗口选择 COM 口时，立即显示该端口自己的已保存参数。"""
        key=port_number(values["端口"].get())
        session=self.sessions.get(key)
        if session:
            settings=session.get("settings",{})
        else:
            # 尚未创建标签的串口使用标准默认值，不复制其他 COM 口的参数。
            settings={"baud":"115200","data_bits":"8","stop_bits":"1","parity":"无","flow_control":"无"}
        for label,name in (("波特率","baud"),("数据位","data_bits"),("停止位","stop_bits"),
                           ("校验位","parity"),("流控制","flow_control")):
            values[label].set(str(settings.get(name,values[label].get())))

    def apply_serial_dialog(self,win,values):
        self.save_active_session_state()
        requested={"port":values["端口"].get(),"baud":values["波特率"].get(),
                   "data_bits":values["数据位"].get(),"stop_bits":values["停止位"].get(),
                   "parity":values["校验位"].get(),"flow_control":values["流控制"].get()}
        new_key=port_number(requested["port"])
        session=self.sessions.get(new_key)
        if not session:
            session=self.create_serial_session(new_key,requested["port"],requested)
        if not session:
            messagebox.showwarning("串口设置","请选择有效串口",parent=win); return
        # 只覆盖目标串口的线路参数，保留它自己的收发勾选、发送内容等工作区配置。
        session["settings"].update(requested)
        session["label"]=requested["port"]
        self.switch_serial_session(new_key,save_current=False)
        win.destroy()
        # 已打开时立即重新配置驱动；关闭时只保存，待下次打开应用。
        self.serial_parameter_changed("参数")
        self.save_config()

    def create_checkmark_style(self,style):
        """使用清晰的对勾复选框，替代 clam 主题默认的叉号。"""
        off=tk.PhotoImage(width=16,height=16)
        on=tk.PhotoImage(width=16,height=16)
        off.put("#FFFFFF",to=(1,1,15,15)); off.put("#9AA9BA",to=(1,1,15,2)); off.put("#9AA9BA",to=(1,14,15,15))
        off.put("#9AA9BA",to=(1,1,2,15)); off.put("#9AA9BA",to=(14,1,15,15))
        on.put("#3478F6",to=(1,1,15,15))
        # 以像素线条绘制白色 ✓，避免不同字体中符号显示不一致。
        for x,y in [(4,8),(5,9),(6,10),(7,9),(8,8),(9,7),(10,6),(11,5),(5,8),(6,9),(7,8),(8,7),(9,6),(10,5)]:
            on.put("#FFFFFF",to=(x,y,x+2,y+2))
        self._check_images=(off,on)
        try:
            style.element_create("VCheck.indicator","image",off,("selected",on),sticky="")
        except tk.TclError:
            pass
        style.layout("TCheckbutton",[("VCheck.indicator",{"side":"left","sticky":""}),
                     ("Checkbutton.padding",{"sticky":"nswe","children":[("Checkbutton.label",{"sticky":"nswe"})]})])

    def apply_theme(self):
        """即时应用五套界面配色，并保留所有当前数据和串口状态。"""
        name=self.theme_name.get()
        if name not in THEMES: name="现代浅色"; self.theme_name.set(name)
        c=THEMES[name]; style=ttk.Style(self)
        self.configure(bg=c["bg"])
        style.configure(".",background=c["bg"],foreground=c["text"])
        style.configure("TFrame",background=c["bg"])
        style.configure("Card.TFrame",background=c["card"])
        style.configure("TLabelframe",background=c["card"],bordercolor=c["border"])
        style.configure("TLabelframe.Label",background=c["card"],foreground=c["text"])
        style.configure("TLabel",background=c["bg"],foreground=c["muted"])
        style.configure("Card.TLabel",background=c["card"],foreground=c["muted"])
        style.configure("TCheckbutton",background=c["card"],foreground=c["muted"])
        style.map("TCheckbutton",background=[("active",c["card"])])
        style.configure("TButton",background=c["border"],foreground=c["text"])
        style.map("TButton",background=[("active",c["status_bg"])])
        style.configure("Primary.TButton",background=c["primary"],foreground=c["header_fg"])
        style.map("Primary.TButton",background=[("active",c["primary_hover"]), ("pressed",c["primary_hover"])])
        style.configure("TEntry",fieldbackground=c["field"],foreground=c["text"],bordercolor=c["border"],insertcolor=c["text"])
        style.configure("TCombobox",fieldbackground=c["field"],background=c["field"],foreground=c["text"],bordercolor=c["border"],arrowcolor=c["text"])
        style.map("TCombobox",fieldbackground=[("readonly",c["field"])],foreground=[("readonly",c["text"])])
        style.configure("Vertical.TScrollbar",background=c["border"],troughcolor=c["field"])
        style.configure("Status.TLabel",background=c["status_bg"],foreground=c["status_fg"])
        # 自绘菜单栏保持 Codex 风格，同时随主题协调明暗。
        menu_bg=c["card"]; menu_fg=c["muted"]; menu_active=c["status_bg"]
        self.menu_bar.configure(bg=menu_bg)
        for child in self.menu_bar.winfo_children():
            if isinstance(child,tk.Label): child.configure(bg=menu_bg,fg=menu_fg)
        for btn in self.menu_buttons:
            btn.configure(bg=menu_bg,fg=menu_fg,activebackground=menu_active,activeforeground=c["text"])
        self.recv.configure(bg=c["field"],fg=c["text"],insertbackground=c["primary"],
                            selectbackground=c["primary"],selectforeground=c["header_fg"],inactiveselectbackground=c["primary"])
        self.send_text.configure(bg=c["field"],fg=c["text"],insertbackground=c["primary"],
                                 selectbackground=c["primary"],selectforeground=c["header_fg"],inactiveselectbackground=c["primary"])
        self.recv.tag_configure("rx",foreground=c["rx"]); self.recv.tag_configure("tx",foreground=c["tx"])
        for w in self.winfo_children(): self._theme_canvas(w,c)
        self.refresh_session_tabs()

    def theme_selected(self):
        self.apply_theme(); self.save_config()

    def _theme_canvas(self,widget,c):
        if isinstance(widget,tk.Canvas): widget.configure(bg=c["card"])
        for child in widget.winfo_children(): self._theme_canvas(child,c)

    def apply_config(self):
        c=self.config_data
        for var,key in [(self.port,"port"),(self.baud,"baud"),(self.data_bits,"data_bits"),(self.parity,"parity"),(self.stop_bits,"stop_bits"),(self.flow_control,"flow_control"),(self.interval,"interval"),(self.encoding,"encoding"),(self.timestamp_timeout,"timestamp_timeout"),(self.checksum,"checksum"),(self.checksum_start,"checksum_start"),(self.checksum_end,"checksum_end")]:
            if key in c: var.set(c[key])
        for var,key in [(self.hex_recv,"hex_recv"),(self.hex_send,"hex_send"),(self.timestamp,"timestamp"),(self.newline,"newline")]: var.set(c.get(key,var.get()))
        cycle_flags_valid=c.get("quick_cycle_flags_v1",False)
        for row,saved in zip(self.quick_rows,c.get("quick",[])):
            row[0].set(saved.get("name","")); row[1].set(saved.get("data","")); row[2].set(saved.get("hex",True)); row[3].set(saved.get("delay","1000")); row[4].set(saved.get("enabled",False) if cycle_flags_valid else False)
        if self.checksum_end.get()!="末尾" and not self.checksum_end.get().startswith("倒数第"):
            self.checksum_end.set("末尾")
        if c.get("send_text"):
            self.send_text.insert("1.0",c["send_text"])
        self.send_text.edit_modified(False)
        self.refresh_ports()
        self.restore_serial_sessions()

    def on_send_text_modified(self,_event=None):
        if not self.send_text.edit_modified(): return
        self.send_text.edit_modified(False)
        if self.loading_session: return
        if self.send_save_job: self.after_cancel(self.send_save_job)
        self.send_save_job=self.after(500,self.save_config)

    def collect_config(self):
        self.save_active_session_state()
        window_state=self.state()
        # 最大化时 geometry() 不是用户最后调整的小窗口尺寸，沿用已记录值。
        window_geometry=self.geometry() if window_state=="normal" else self.config_data.get("window_geometry","")
        return {"window_geometry":window_geometry,"window_state":window_state,
                "t5l_project":self.config_data.get("t5l_project",os.path.join(T5L_TOOL_DIR,"DWIN_SET")),
                "t5l_excluded_files":self.config_data.get("t5l_excluded_files",[]),
                "t5l_quick_select":self.config_data.get("t5l_quick_select",{}),
                "t5l_download_port":(self.t5l_window.port.get() if getattr(self,"t5l_window",None) else (self.config_data.get("t5l_download_port","") or self.port.get())),
                "t5l_download_baud":(self.t5l_window.baud.get() if getattr(self,"t5l_window",None) else self.config_data.get("t5l_download_baud","115200")),
                "quick_page":self.quick_page_var.get(),
                "quick_panel_visible":self.quick_panel_visible.get(),
                "quick_cycle_flags_v1":True,
                "theme":self.theme_name.get(),"port":self.port.get(),"baud":self.baud.get(),"data_bits":self.data_bits.get(),"parity":self.parity.get(),"stop_bits":self.stop_bits.get(),"flow_control":self.flow_control.get(),
                "interval":self.interval.get(),"encoding":self.encoding.get(),"checksum":self.checksum.get(),"checksum_start":self.checksum_start.get(),"checksum_end":self.checksum_end.get(),"hex_recv":self.hex_recv.get(),"hex_send":self.hex_send.get(),"timestamp":self.timestamp.get(),"newline":self.newline.get(),
                "timestamp_timeout":self.timestamp_timeout.get(),
                "agent_api_token":self.agent_api_token,"agent_api_port":self.agent_api_port,
                "serial_sessions":[self.session_config(s) for s in self.sessions.values()],
                "active_serial_port":self.active_session_key or "",
                "send_text":self.send_text.get("1.0","end-1c"),
                "quick":[{"name":r[0].get(),"data":r[1].get(),"hex":r[2].get(),"delay":r[3].get(),"enabled":r[4].get()} for r in self.quick_rows]}

    def save_config(self):
        self.send_save_job=None
        try:
            data=self.collect_config()
            self.config_data.update(data)
            with open(CONFIG_FILE,"w",encoding="utf-8") as f: json.dump(data,f,ensure_ascii=False,indent=2)
        except OSError: pass

    def start_agent_api(self):
        self.agent_api=AgentAPIController(self.agent_api_token,self.agent_api_port)
        if self.agent_api.start():
            self.config_data["agent_api_token"]=self.agent_api_token
            self.config_data["agent_api_port"]=self.agent_api_port
            self.save_config()
            self.agent_api_job=self.after(50,self.poll_agent_api)
        else:
            self.status.set(f"Agent API 启动失败：{self.agent_api.error}")

    def poll_agent_api(self):
        if self.agent_api:
            self.agent_api.process_pending(self.handle_agent_action)
            self.agent_api_job=self.after(50,self.poll_agent_api)

    def handle_agent_action(self,action,payload):
        if action=="status": return self.agent_status()
        if action=="serial.open": return self.agent_open_serial(payload)
        if action=="serial.close": return self.agent_close_serial(payload)
        if action=="serial.send": return self.agent_send_serial(payload)
        if action=="serial.receive": return self.agent_receive_serial(payload)
        if action=="t5l.download": return self.agent_start_t5l(payload)
        if action=="t5l.stop": return self.agent_stop_t5l()
        raise ValueError(f"未知 Agent 操作：{action}")

    def agent_status(self):
        sessions=[]
        for key,session in self.sessions.items():
            sessions.append({"port":key,"label":session.get("label",key),
                             "open":bool(session["serial"].is_open),
                             "active":key==self.active_session_key,
                             "settings":dict(session.get("settings",{})),
                             "rx_bytes":session.get("rx_count",0),"tx_bytes":session.get("tx_count",0)})
        window=getattr(self,"t5l_window",None)
        t5l={"running":bool(window and window.worker and window.worker.is_alive()),
             "port":window.port.get() if window else "","baud":window.baud.get() if window else "",
             "progress":int(float(window.progress["value"])) if window else 0,
             "status":window.download_status.get() if window else "未启动"}
        return {"version":APP_VERSION,"active_port":self.active_session_key or "",
                "sessions":sessions,"t5l":t5l}

    @staticmethod
    def normalize_agent_parity(value):
        text=str(value or "无").strip().upper()
        mapping={"N":"无","NONE":"无","无":"无","O":"奇","ODD":"奇","奇":"奇",
                 "E":"偶","EVEN":"偶","偶":"偶","M":"标记","MARK":"标记","标记":"标记",
                 "S":"空格","SPACE":"空格","空格":"空格"}
        if text not in mapping: raise ValueError(f"不支持的校验位：{value}")
        return mapping[text]

    def agent_open_serial(self,payload):
        key=port_number(payload.get("port",""))
        if not re.fullmatch(r"COM\d+",key,re.I): raise ValueError("port 必须是 COM 端口，例如 COM5")
        baud=str(int(payload.get("baud",115200))); data_bits=str(payload.get("data_bits",payload.get("data-bits",8)))
        stop_bits=str(payload.get("stop_bits",payload.get("stop-bits",1))); parity=self.normalize_agent_parity(payload.get("parity","无"))
        if data_bits not in ("5","6","7","8"): raise ValueError("data_bits 必须为 5、6、7 或 8")
        if stop_bits not in ("1","1.5","2"): raise ValueError("stop_bits 必须为 1、1.5 或 2")
        label=next((label for port,label in list_port_details() if port.upper()==key.upper()),key)
        session=self.sessions.get(key) or self.create_serial_session(key,label,{"baud":baud,"data_bits":data_bits,"stop_bits":stop_bits,"parity":parity})
        if not session: raise RuntimeError("无法创建串口会话")
        session["settings"].update({"port":label,"baud":baud,"data_bits":data_bits,"stop_bits":stop_bits,"parity":parity})
        session["label"]=label; self.switch_serial_session(key)
        if session["serial"].is_open:
            actual=session["serial"].configure(baud,data_bits,parity,stop_bits)
        else:
            session["stop_event"].clear(); session["serial"].open(key,baud,data_bits,parity,stop_bits)
            actual=session["serial"].get_settings()
            threading.Thread(target=self.reader,args=(key,session),daemon=True).start()
        session["last_status"]=""; self.update_session_ui(); self.refresh_session_tabs(); self.save_config()
        return {"port":key,"open":True,"actual":actual}

    def agent_close_serial(self,payload):
        key=port_number(payload.get("port","")); session=self.sessions.get(key)
        if not session: raise ValueError(f"串口标签不存在：{key or payload.get('port','')}")
        if self.t5l_active and key==self.t5l_restore_session: raise RuntimeError("该串口正在执行 T5L 下载")
        session["stop_event"].set(); session["serial"].close(); session["last_status"]=f"●  {key} 已关闭"
        if key==self.active_session_key: self.update_session_ui()
        self.refresh_session_tabs(); self.save_config()
        return {"port":key,"open":False}

    def agent_send_serial(self,payload):
        key=port_number(payload.get("port","")); session=self.sessions.get(key)
        if not session or not session["serial"].is_open: raise RuntimeError(f"串口未打开：{key}")
        if self.t5l_active and key==self.t5l_restore_session: raise RuntimeError("该串口正在执行 T5L 下载")
        self.switch_serial_session(key)
        data=self.bytes_from_text(str(payload.get("data","")),bool(payload.get("hex",False)))
        if not data: raise ValueError("发送数据不能为空")
        checksum=str(payload.get("checksum","None"))
        if checksum and checksum!="None": data=self.append_checksum(data,checksum)
        self.append_traffic_data("发→◇",data,"tx"); sent=session["serial"].write(data)
        session["tx_count"]+=sent; self.tx_count=session["tx_count"]; self.update_counter()
        self.status.set(f"{key} 已发送 {sent} 字节")
        return {"port":key,"bytes":sent,"hex":" ".join(f"{byte:02X}" for byte in data)}

    def agent_receive_serial(self,payload):
        """返回指定串口为 Agent 保留的最新接收包，不影响 GUI 通讯记录。"""
        key=port_number(payload.get("port","")); session=self.sessions.get(key)
        if not session: raise ValueError(f"串口标签不存在：{key or payload.get('port','')}")
        try: limit=max(1,min(200,int(payload.get("limit",20))))
        except (TypeError,ValueError): raise ValueError("limit 必须是 1 到 200 的整数")
        packets=session.get("agent_rx_buffer",[])[-limit:]
        encoding=str(payload.get("encoding") or self.encoding.get() or "GBK")
        result=[]
        for packet in packets:
            data=bytes(packet["data"])
            try: decoded=data.decode(encoding,errors="replace")
            except LookupError: raise ValueError(f"不支持的字符编码：{encoding}")
            result.append({"time":packet["time"].isoformat(timespec="milliseconds"),
                           "bytes":len(data),"hex":" ".join(f"{byte:02X}" for byte in data),
                           "text":decoded})
        if bool(payload.get("clear",False)): session["agent_rx_buffer"].clear()
        return {"port":key,"count":len(result),"latest":result[-1] if result else None,
                "packets":result,"cleared":bool(payload.get("clear",False))}

    def agent_start_t5l(self,payload):
        key=port_number(payload.get("port",""))
        if not re.fullmatch(r"COM\d+",key,re.I): raise ValueError("port 必须是 COM 端口，例如 COM5")
        self.open_t5l_download(); window=self.t5l_window
        if window.worker and window.worker.is_alive(): raise RuntimeError("T5L 下载已在运行")
        label=next((label for port,label in list_port_details() if port.upper()==key.upper()),key)
        window.port.set(label); window.baud.set(str(int(payload.get("baud",115200))))
        for var in window.quick_select.values(): var.set(True)
        files=payload.get("files") or []
        folder=str(payload.get("folder") or "").strip()
        if files:
            resolved=[]
            for path in files:
                full=os.path.abspath(os.path.join(folder,path) if folder and not os.path.isabs(path) else path)
                if not os.path.isfile(full): raise FileNotFoundError(f"下载文件不存在：{full}")
                fid=file_id(full)
                if fid is None: raise ValueError(f"无法识别文件 ID：{os.path.basename(full)}")
                resolved.append((fid,full,os.path.getsize(full)))
            window.files=sorted(resolved,key=lambda item:(item[0],os.path.basename(item[1]).lower()))
            if folder: window.folder.set(os.path.abspath(folder))
            elif resolved: window.folder.set(os.path.dirname(resolved[0][1]))
            window.show_files(); window.tree.selection_set([item[1] for item in window.files])
        else:
            if not folder or not os.path.isdir(folder): raise ValueError("请提供有效的 folder 或 files")
            window.folder.set(os.path.abspath(folder)); window.scan()
            if not window.files: raise RuntimeError("目录中没有可下载文件")
            window.show_files(); window.tree.selection_set([item[1] for item in window.files])
        window.worker=None; window.start()
        if not window.worker or not window.worker.is_alive(): raise RuntimeError("T5L 下载未能启动")
        return {"started":True,"port":key,"baud":window.baud.get(),"files":[os.path.basename(item[1]) for item in window.files]}

    def agent_stop_t5l(self):
        window=getattr(self,"t5l_window",None)
        if not window or not window.worker or not window.worker.is_alive(): return {"running":False}
        window.stop_download(); return {"running":True,"stopping":True}

    def current_serial_settings(self):
        settings={"port":self.port.get(),"baud":self.baud.get(),"data_bits":self.data_bits.get(),
                  "parity":self.parity.get(),"stop_bits":self.stop_bits.get(),"flow_control":self.flow_control.get(),
                  "hex_recv":self.hex_recv.get(),"timestamp":self.timestamp.get(),
                  "timestamp_timeout":self.timestamp_timeout.get(),"autoscroll":self.autoscroll.get(),
                  "hex_send":self.hex_send.get(),"newline":self.newline.get(),
                  "timer_on":self.timer_on.get(),"interval":self.interval.get(),
                  "checksum":self.checksum.get(),"checksum_start":self.checksum_start.get(),
                  "checksum_end":self.checksum_end.get()}
        if hasattr(self,"send_text"): settings["send_text"]=self.send_text.get("1.0","end-1c")
        return settings

    def session_config(self,session):
        settings=dict(session.get("settings",{}))
        settings["port"]=session.get("label",session["key"])
        # T5L 临时占用期间句柄虽然已关闭，但应保存占用前的真实开关状态。
        settings["is_open"]=(self.t5l_restore_open
                             if self.t5l_active and session["key"]==self.t5l_restore_session
                             else session["serial"].is_open)
        return settings

    def save_active_session_state(self):
        if self.active_session_key in self.sessions:
            session=self.sessions[self.active_session_key]
            session["settings"]=self.current_serial_settings()
            session["label"]=self.port.get() or session["key"]
            session["rx_count"]=self.rx_count; session["tx_count"]=self.tx_count

    def create_serial_session(self,key,label=None,settings=None):
        key=port_number(key)
        if not re.fullmatch(r"COM\d+",key,re.IGNORECASE): return None
        if key in self.sessions: return self.sessions[key]
        c=self.config_data
        base={"port":label or key,"baud":"115200","data_bits":"8","parity":"无","stop_bits":"1","flow_control":"无",
              "hex_recv":c.get("hex_recv",False),"timestamp":c.get("timestamp",False),
              "timestamp_timeout":c.get("timestamp_timeout","40"),"autoscroll":c.get("autoscroll",True),
              "hex_send":c.get("hex_send",False),"newline":c.get("newline",False),
              "timer_on":False,"interval":c.get("interval","1000"),
              "checksum":c.get("checksum","None"),"checksum_start":c.get("checksum_start","第1字节"),
              "checksum_end":c.get("checksum_end","末尾"),"send_text":c.get("send_text","")}
        if settings: base.update({k:v for k,v in settings.items() if k in base and v not in (None,"")})
        session={"key":key,"label":label or base["port"] or key,"serial":WindowsSerial(),
                 "stop_event":threading.Event(),"settings":base,"rx_count":0,"tx_count":0,
                 "history":[],"agent_rx_buffer":[],"last_rx_at":None,"last_status":"",
                 "reconfigure_generation":0,"reconfigure_lock":threading.Lock()}
        self.sessions[key]=session
        self.refresh_session_tabs()
        return session

    def ensure_serial_session(self,value=None,settings=None):
        value=value or self.port.get(); key=port_number(value)
        session=self.sessions.get(key) or self.create_serial_session(key,value,settings)
        if session: self.switch_serial_session(key,save_current=False)
        return session

    def restore_serial_sessions(self):
        saved=self.config_data.get("serial_sessions",[])
        restore_open=[]
        available=dict(list_port_details())
        if isinstance(saved,list):
            for item in saved:
                if not isinstance(item,dict): continue
                key=port_number(item.get("port",""))
                if re.fullmatch(r"COM\d+",key,re.IGNORECASE):
                    # 保留各端口独立配置；当前电脑存在该端口时使用本机驱动名称。
                    self.create_serial_session(key,available.get(key,item.get("port",key)),item)
                    # 换电脑或设备未插入时绝不自动尝试打开，避免启动即报 WinError 2。
                    if key in available and item.get("is_open",False): restore_open.append(key)
        active=port_number(self.config_data.get("active_serial_port",""))
        if active in self.sessions and active in available: self.switch_serial_session(active)
        elif available:
            first_available=next(iter(available))
            if first_available not in self.sessions:
                self.create_serial_session(first_available,available[first_available],self.current_serial_settings())
            self.switch_serial_session(first_available)
        elif active in self.sessions: self.switch_serial_session(active)
        elif self.sessions: self.switch_serial_session(next(iter(self.sessions)))
        else: self.refresh_session_tabs(); self.update_session_ui()
        # 全部标签与参数恢复完成后，再逐一恢复上次处于打开状态的串口。
        for key in restore_open:
            if key not in self.sessions: continue
            self.switch_serial_session(key)
            if not self.sessions[key]["serial"].is_open: self.toggle_port()
        if active in self.sessions and active in available: self.switch_serial_session(active)

    def new_serial_session(self):
        self.save_active_session_state()
        details=list_port_details(); unused=[(p,l) for p,l in details if p not in self.sessions]
        selected=port_number(self.port.get())
        candidate=next(((p,l) for p,l in unused if p==selected),unused[0] if unused else (None,None))
        if not candidate[0]:
            messagebox.showinfo("新增串口","没有可新增的串口。已有串口请直接点击上方标签切换。")
            return
        self.create_serial_session(candidate[0],candidate[1],self.current_serial_settings()); self.switch_serial_session(candidate[0]); self.save_config()

    def switch_serial_session(self,key,save_current=True):
        if key not in self.sessions: return
        if save_current: self.save_active_session_state()
        # 使旧标签尚未执行的定时发送回调失效。
        self.timer_generation+=1
        session=self.sessions[key]; self.active_session_key=key
        self.serial=session["serial"]; self.stop_event=session["stop_event"]
        self.rx_count=session["rx_count"]; self.tx_count=session["tx_count"]
        self.traffic_history=session["history"]
        settings=session["settings"]
        self.loading_session=True
        self.port.set(session["label"])
        for var,name in ((self.baud,"baud"),(self.data_bits,"data_bits"),(self.parity,"parity"),
                         (self.stop_bits,"stop_bits"),(self.flow_control,"flow_control"),
                         (self.timestamp_timeout,"timestamp_timeout"),(self.interval,"interval"),
                         (self.checksum,"checksum"),(self.checksum_start,"checksum_start"),(self.checksum_end,"checksum_end")):
            var.set(settings.get(name,var.get()))
        for var,name in ((self.hex_recv,"hex_recv"),(self.timestamp,"timestamp"),(self.autoscroll,"autoscroll"),
                         (self.hex_send,"hex_send"),(self.newline,"newline"),(self.timer_on,"timer_on")):
            var.set(bool(settings.get(name,var.get())))
        self.send_text.delete("1.0","end")
        self.send_text.insert("1.0",settings.get("send_text",""))
        self.send_text.edit_modified(False)
        self.loading_session=False
        self.flush_rx_pending(); self.render_traffic_history(); self.update_counter(); self.update_session_ui(); self.refresh_session_tabs()
        self.sync_t5l_baud_from_serial(session["key"],self.baud.get())
        if self.timer_on.get(): self.timer_changed()

    def close_serial_session(self,key,ask=True):
        session=self.sessions.get(key)
        if not session: return
        if self.t5l_active and key==self.t5l_restore_session:
            messagebox.showwarning("串口正在使用","该串口正在执行 T5L 下载，请先停止下载。")
            return
        if session["serial"].is_open and ask and not messagebox.askyesno("关闭串口标签",f"{key} 正在打开，是否关闭串口并移除标签？"):
            return
        session["stop_event"].set(); session["serial"].close(); del self.sessions[key]
        if self.active_session_key==key:
            self.active_session_key=None
            if self.sessions: self.switch_serial_session(next(iter(self.sessions)),save_current=False)
            else:
                self.serial=WindowsSerial(); self.stop_event=threading.Event(); self.rx_count=self.tx_count=0
                self.traffic_history=[]; self.recv.delete("1.0","end"); self.update_counter(); self.update_session_ui()
        self.refresh_session_tabs(); self.save_config()

    def close_active_session(self):
        if self.active_session_key: self.close_serial_session(self.active_session_key)

    def refresh_session_tabs(self):
        if not hasattr(self,"session_tabs"): return
        for child in self.session_tabs.winfo_children(): child.destroy()
        c=THEMES.get(self.theme_name.get(),THEMES["现代浅色"])
        if not self.sessions:
            tk.Label(self.session_tabs,text="暂无串口标签，选择端口后点击“打开串口”",bg=c["bg"],fg=c["muted"],
                     font=("Segoe UI Variable Text",9)).pack(side="left",padx=6)
            return
        for key,session in self.sessions.items():
            active=key==self.active_session_key; bg=c["status_bg"] if active else c["card"]
            tab=tk.Frame(self.session_tabs,bg=bg,highlightthickness=1,highlightbackground=c["primary"] if active else c["border"],cursor="hand2")
            tab.pack(side="left",padx=(0,4))
            dot="#E5A000" if self.t5l_active and key==self.t5l_restore_session else ("#1FA34A" if session["serial"].is_open else "#E43D3D")
            widgets=[tk.Label(tab,text="●",bg=bg,fg=dot,font=("Segoe UI Symbol",10)),
                     tk.Label(tab,text=key,bg=bg,fg=c["text"],font=("Segoe UI Variable Text",10,"bold" if active else "normal")),
                     tk.Label(tab,text="×",bg=bg,fg=c["muted"],font=("Segoe UI Variable Text",12),padx=7)]
            for widget in widgets: widget.pack(side="left",padx=(6,0) if widget is widgets[0] else 2,pady=5)
            for widget in (tab,widgets[0],widgets[1]): widget.bind("<Button-1>",lambda _e,k=key:self.switch_serial_session(k))
            widgets[2].bind("<Button-1>",lambda _e,k=key:self.close_serial_session(k))

    def update_session_ui(self):
        session=self.sessions.get(self.active_session_key)
        if not session:
            self.open_btn.config(text="打开串口",state="normal"); self.status.set("●  串口未打开")
            return
        if self.t5l_active and self.active_session_key==self.t5l_restore_session:
            self.open_btn.config(text="T5L 使用中",state="disabled")
            self.status.set(f"●  {session['key']} 已切换到 T5L 下载模式")
            return
        if session["serial"].is_open:
            self.open_btn.config(text="关闭串口",state="normal")
            try: self.show_actual_settings(session["serial"].get_settings())
            except Exception: self.status.set(f"●  {session['key']} 已打开")
        else:
            self.open_btn.config(text="打开串口",state="normal")
            self.status.set(session.get("last_status") or f"●  {session['key']} 已关闭")

    def refresh_ports(self):
        details=list_port_details(); vals=[label for _,label in details]; self.port_box["values"]=vals
        labels=dict(details)
        for key,session in self.sessions.items():
            if key in labels:
                session["label"]=labels[key]; session["settings"]["port"]=labels[key]
        current=port_number(self.port.get())
        match=next((label for port,label in details if port==current),None)
        if match: self.port.set(match)
        elif vals: self.port.set(vals[0])
        elif not self.port.get(): self.status.set("未发现串口设备")
        if self.active_session_key in self.sessions: self.port.set(self.sessions[self.active_session_key]["label"])
        self.refresh_session_tabs()

    def toggle_port(self):
        if self.t5l_active and self.active_session_key==self.t5l_restore_session:
            messagebox.showwarning("串口正在使用", "当前串口已切换到 T5L 下载模式，请先停止下载。")
            return
        if not self.port.get(): messagebox.showwarning("提示","请选择串口"); return
        selected=port_number(self.port.get())
        session=self.sessions.get(selected)
        if not session:
            session=self.create_serial_session(selected,self.port.get(),self.current_serial_settings())
        if not session: messagebox.showwarning("提示","请选择有效串口"); return
        if self.active_session_key!=selected: self.switch_serial_session(selected,save_current=False)
        if session["serial"].is_open:
            session["stop_event"].set(); session["serial"].close(); session["last_status"]=f"●  {selected} 已关闭"
            self.update_session_ui(); self.refresh_session_tabs(); self.save_config(); return
        try:
            self.save_active_session_state(); session["stop_event"].clear()
            session["serial"].open(selected,self.baud.get(),self.data_bits.get(),self.parity.get(),self.stop_bits.get())
            actual=session["serial"].get_settings()
            expected_parity={"无":0,"奇":1,"偶":2,"标记":3,"空格":4}[self.parity.get()]
            expected_stop={"1":0,"1.5":1,"2":2}[self.stop_bits.get()]
            mismatch=(actual["baud"]!=int(self.baud.get()) or actual["data"]!=int(self.data_bits.get()) or
                      actual["parity"]!=expected_parity or actual["stop"]!=expected_stop)
            if mismatch:
                session["serial"].close()
                raise RuntimeError(f"串口驱动未接受所选参数。驱动实际值：{actual}")
            threading.Thread(target=self.reader,args=(selected,session),daemon=True).start()
            session["last_status"]=""; self.update_session_ui(); self.refresh_session_tabs(); self.save_config()
        except Exception as e:
            session["last_status"]=f"打开失败: {e}"; self.update_session_ui(); self.refresh_session_tabs(); self.save_config(); messagebox.showerror("打开失败",str(e))

    def show_actual_settings(self,actual=None):
        actual=actual or self.serial.get_settings()
        parity_short={0:"N",1:"O",2:"E",3:"M",4:"S"}.get(actual["parity"],"?")
        stop_short={0:"1",1:"1.5",2:"2"}.get(actual["stop"],"?")
        port=self.active_session_key or port_number(self.port.get())
        self.status.set(f"●  {port}  {actual['baud']} / {actual['data']}{parity_short}{stop_short}")

    def serial_parameter_changed(self,name):
        if name=="端口":
            selected=port_number(self.port.get())
            if re.fullmatch(r"COM\d+",selected,re.IGNORECASE):
                self.ensure_serial_session(self.port.get(),self.current_serial_settings()); self.save_config()
            return
        session=self.sessions.get(self.active_session_key)
        if not session: return
        session["settings"]=self.current_serial_settings()
        if name in ("波特率","参数"):
            self.sync_t5l_baud_from_serial(session["key"],self.baud.get())
        if not session["serial"].is_open: self.save_config(); return
        baud=self.baud.get(); data_bits=self.data_bits.get(); parity=self.parity.get(); stop_bits=self.stop_bits.get()
        expected={"baud":int(baud),"data":int(data_bits),
                  "parity":{"无":0,"奇":1,"偶":2,"标记":3,"空格":4}[parity],
                  "stop":{"1":0,"1.5":1,"2":2}[stop_bits]}
        session["reconfigure_generation"]+=1
        generation=session["reconfigure_generation"]
        self.status.set(f"●  {session['key']}  正在切换参数…")
        # USB 串口驱动的 SetCommState 偶尔会等待约 0.2 秒；放到后台执行，
        # 避免通讯记录和发送输入框在此期间一起停止刷新。
        def configure_worker():
            try:
                with session["reconfigure_lock"]:
                    actual=session["serial"].configure(baud,data_bits,parity,stop_bits)
                error=None
                if any(actual[k]!=v for k,v in expected.items()):
                    error=RuntimeError(f"驱动实际参数与选择不一致：{actual}")
            except Exception as exc:
                actual=None; error=exc
            self.reconfigure_queue.put((session["key"],generation,actual,error))
        threading.Thread(target=configure_worker,daemon=True).start()
        self.save_config()

    def poll_reconfigure_results(self):
        while True:
            try: key,generation,actual,error=self.reconfigure_queue.get_nowait()
            except queue.Empty: return
            session=self.sessions.get(key)
            if not session or generation!=session.get("reconfigure_generation"): continue
            if error:
                session["last_status"]=f"参数设置失败: {error}"
                if key==self.active_session_key: messagebox.showerror("参数设置失败",str(error))
            else:
                session["last_status"]=""
                if key==self.active_session_key: self.show_actual_settings(actual)
            self.update_session_ui(); self.refresh_session_tabs()

    def reader(self,key,session):
        while not session["stop_event"].is_set() and session["serial"].is_open:
            try:
                data=session["serial"].read()
                # 在读取线程中记录真实到达时间。非活动串口的数据可能在 UI
                # 队列中短暂积压，不能用稍后的界面处理时间判断分包超时。
                if data: self.rx_queue.put((key,data,time.monotonic(),datetime.now()))
            except Exception as e:
                self.rx_queue.put((key,e)); break

    def poll_rx(self):
        self.poll_reconfigure_results()
        started=time.perf_counter(); active_changed=False
        try:
            while True:
                if time.perf_counter()-started>=RX_UI_TIME_BUDGET: break
                queued=self.rx_queue.get_nowait()
                key,item=queued[0],queued[1]
                received_tick=queued[2] if len(queued)>2 else time.monotonic()
                received_at=queued[3] if len(queued)>3 else datetime.now()
                session=self.sessions.get(key)
                if not session: continue
                if isinstance(item,Exception):
                    record=(datetime.now(),"错误",str(item).encode("utf-8",errors="replace"),"error",True)
                    session["history"].append(record); session["last_status"]=f"接收错误: {item}"
                    session["serial"].close(); session["stop_event"].set()
                    if key==self.active_session_key:
                        self.insert_traffic_record(record); self.update_session_ui()
                    self.refresh_session_tabs(); continue
                session["rx_count"]+=len(item)
                now=received_tick; last=session.get("last_rx_at")
                try: packet_timeout=max(1,min(5000,int(session.get("settings",{}).get("timestamp_timeout","40"))))
                except (TypeError,ValueError): packet_timeout=40
                new_packet=last is None or (now-last)*1000>=packet_timeout
                session["last_rx_at"]=now
                record=(received_at,"收←◆",bytes(item),"rx",new_packet)
                if new_packet or not session["history"] or session["history"][-1][3]!="rx":
                    session["history"].append(record)
                else:
                    previous=session["history"][-1]
                    session["history"][-1]=(previous[0],previous[1],previous[2]+bytes(item),previous[3],True)
                agent_buffer=session.setdefault("agent_rx_buffer",[])
                if new_packet or not agent_buffer:
                    agent_buffer.append({"time":record[0],"data":bytearray(item)})
                else:
                    agent_buffer[-1]["data"].extend(item)
                if len(agent_buffer)>1000: del agent_buffer[:-1000]
                if len(session["history"])>MAX_TRAFFIC_RECORDS: del session["history"][:-MAX_TRAFFIC_RECORDS]
                if key==self.active_session_key:
                    self.traffic_history=session["history"]; self.rx_count=session["rx_count"]
                    self.insert_traffic_record(record,autoscroll=False); active_changed=True
        except queue.Empty: pass
        if active_changed:
            self.update_counter()
            if self.autoscroll.get(): self.recv.see("end")
        self.poll_job=self.after(5 if not self.rx_queue.empty() else 25,self.poll_rx)

    def bytes_from_text(self,text,is_hex):
        if is_hex:
            cleaned=re.sub(r"[\s,;:-]+","",text)
            if not cleaned: return b""
            if len(cleaned)%2 or re.search(r"[^0-9a-fA-F]",cleaned): raise ValueError("HEX 数据格式错误，请输入成对的十六进制字符")
            return bytes.fromhex(cleaned)
        data=text.encode(self.encoding.get(),errors="replace")
        if self.newline.get(): data+=b"\r\n"
        return data

    def checksum_range(self,data):
        start=int(re.search(r"\d+",self.checksum_start.get()).group())-1
        end_text=self.checksum_end.get()
        if end_text=="末尾": end=len(data)
        elif end_text.startswith("倒数"):
            # “倒数第1字节”表示包含最后一个字节。
            end=len(data)-int(re.search(r"\d+",end_text).group())+1
        else: end=int(re.search(r"\d+",end_text).group())
        if start<0 or start>=len(data): raise ValueError(f"校验起始位置超出数据长度（共 {len(data)} 字节）")
        if end<=start or end>len(data): raise ValueError(f"校验结束位置无效（共 {len(data)} 字节）")
        return data[start:end]

    def append_checksum(self,data,algorithm):
        if algorithm=="None": return data
        source=self.checksum_range(data)
        if algorithm=="Modbus CRC16":
            crc=0xFFFF
            for b in source:
                crc^=b
                for _ in range(8): crc=(crc>>1)^0xA001 if crc&1 else crc>>1
            return data+crc.to_bytes(2,"little")
        if algorithm=="CCITT CRC16":
            return data+binascii.crc_hqx(source,0xFFFF).to_bytes(2,"big")
        if algorithm=="CRC32": return data+(binascii.crc32(source)&0xFFFFFFFF).to_bytes(4,"little")
        if algorithm=="ADD8": return data+bytes([sum(source)&0xFF])
        if algorithm=="ADD16": return data+(sum(source)&0xFFFF).to_bytes(2,"little")
        if algorithm=="XOR8":
            value=0
            for b in source: value^=b
            return data+bytes([value])
        raise ValueError(f"未知校验算法：{algorithm}")

    def send_data(self,text,is_hex,apply_checksum=False):
        try:
            session=self.sessions.get(self.active_session_key)
            if not session: raise RuntimeError("请先选择并打开一个串口标签")
            if self.t5l_active and self.active_session_key==self.t5l_restore_session:
                raise RuntimeError("当前串口正在执行 T5L 下载")
            data=self.bytes_from_text(text,is_hex)
            if not data: return
            if apply_checksum: data=self.append_checksum(data,self.checksum.get())
            self.flush_rx_pending()
            self.append_traffic_data("发→◇",data,"tx")
            # Every explicit/timed/quick send is a separate traffic record.  Log
            # before touching the serial port so a click is still visible when
            # the port is closed, busy, or the driver reports a write failure.
            sent=session["serial"].write(data); session["tx_count"]+=sent; self.tx_count=session["tx_count"]
            self.update_counter(); self.status.set(f"{session['key']} 已发送 {sent} 字节")
        except Exception as e: messagebox.showerror("发送失败",str(e)); self.timer_on.set(False)

    def append_traffic(self, direction, content, tag):
        """把发送和接收按 SSCOM 风格写入同一个主窗口。"""
        stamp=datetime.now().strftime("[%H:%M:%S.%f]")[:-4]+"]"
        # 一次数据中如有换行，每行仍保留方向，便于复制和排查。
        lines=content.splitlines() or [""]
        for line in lines:
            self.recv.insert("end", f"{stamp}{direction}{line}\n", tag)
        if self.autoscroll.get(): self.recv.see("end")

    def append_traffic_data(self,direction,data,tag,show_timestamp=True):
        self.traffic_history.append((datetime.now(),direction,bytes(data),tag,show_timestamp))
        if len(self.traffic_history)>MAX_TRAFFIC_RECORDS: del self.traffic_history[:-MAX_TRAFFIC_RECORDS]
        self.insert_traffic_record(self.traffic_history[-1])

    def timestamp_timeout_ms(self):
        try: value=max(1,min(5000,int(self.timestamp_timeout.get())))
        except ValueError: value=40
        return value

    def timestamp_timeout_changed(self,_event=None):
        self.timestamp_timeout.set(str(self.timestamp_timeout_ms())); self.save_config()

    def timestamp_display_changed(self):
        self.flush_rx_pending(); self.render_traffic_history(); self.save_config()

    def queue_rx_traffic(self,data):
        new_packet=not self.rx_pending
        if new_packet: self.rx_pending_started=datetime.now()
        self.rx_pending.extend(data)
        # Display every driver read immediately.  The timeout only decides
        # whether this chunk starts a new timestamped packet.
        self.append_traffic_data("收←◆",data,"rx",new_packet)
        if self.rx_flush_job: self.after_cancel(self.rx_flush_job)
        self.rx_flush_job=self.after(self.timestamp_timeout_ms(),self.flush_rx_pending)

    def flush_rx_pending(self):
        if self.rx_flush_job:
            try: self.after_cancel(self.rx_flush_job)
            except tk.TclError: pass
            self.rx_flush_job=None
        if not self.rx_pending: return
        self.rx_pending.clear(); self.rx_pending_started=None

    def insert_traffic_record(self,record,autoscroll=True,trim=True):
        if len(record)==5: when,direction,data,tag,record_timestamp=record
        else: when,direction,data,tag=record; record_timestamp=True
        content=" ".join(f"{b:02X}" for b in data) if self.hex_recv.get() else data.decode(self.encoding.get(),errors="replace").rstrip("\r\n")
        # 关闭时间戳时使用纯数据流显示：不增加时间、方向标记或强制换行。
        # HEX 模式保留字节间空格，但不增加换行。
        if not self.timestamp.get():
            separator=""
            if self.hex_recv.get() and content:
                try:
                    separator="" if self.recv.index("end-1c")=="1.0" else " "
                except tk.TclError:
                    separator=" "
            self.recv.insert("end",f"{separator}{content}",tag)
            if autoscroll and self.autoscroll.get(): self.recv.see("end")
            if trim: self.trim_traffic_display()
            return
        show_meta=self.timestamp.get() and record_timestamp
        stamp=when.strftime("[%H:%M:%S.%f]")[:-4]+"]" if show_meta else ""
        prefix=direction if show_meta else ""
        # 同一超时包的后续驱动分片不产生新时间戳，也不另起一行。
        if not record_timestamp:
            try:
                if self.recv.get("end-2c","end-1c")=="\n": self.recv.delete("end-2c","end-1c")
            except tk.TclError:
                pass
            separator=" " if self.hex_recv.get() and content else ""
            self.recv.insert("end",f"{separator}{content}\n",tag)
            if autoscroll and self.autoscroll.get(): self.recv.see("end")
            if trim: self.trim_traffic_display()
            return
        for line in content.splitlines() or [""]:
            self.recv.insert("end",f"{stamp}{prefix}{line}\n",tag)
        if autoscroll and self.autoscroll.get(): self.recv.see("end")
        if trim: self.trim_traffic_display()

    def trim_traffic_display(self):
        """分批裁剪界面中的旧行，避免 Text 控件长期运行后持续变慢。"""
        self.display_trim_counter+=1
        if self.display_trim_counter<200: return
        self.display_trim_counter=0
        try:
            lines=int(self.recv.index("end-1c").split(".")[0])
            if lines>MAX_TRAFFIC_RECORDS+500:
                self.recv.delete("1.0",f"{lines-MAX_TRAFFIC_RECORDS}.0")
        except (tk.TclError,ValueError):
            pass

    def render_traffic_history(self):
        self.recv.delete("1.0","end")
        self.display_trim_counter=0
        for record in self.traffic_history[-VISIBLE_TRAFFIC_RECORDS:]:
            self.insert_traffic_record(record,autoscroll=False,trim=False)
        if self.autoscroll.get(): self.recv.see("end")

    def clear_traffic(self):
        if self.rx_flush_job: self.after_cancel(self.rx_flush_job); self.rx_flush_job=None
        self.rx_pending.clear(); self.rx_pending_started=None
        self.traffic_history.clear(); self.recv.delete("1.0","end")

    def send_current(self): self.send_data(self.send_text.get("1.0","end-1c"),self.hex_send.get(),True)
    def quick_page_index(self,slot): return (self.quick_page_var.get()-1)*30+slot

    def bind_quick_mousewheel(self,widget):
        widget.bind("<MouseWheel>",self.quick_mousewheel,add="+")
        widget.bind("<Button-4>",lambda _e:self.quick_canvas.yview_scroll(-1,"units"),add="+")
        widget.bind("<Button-5>",lambda _e:self.quick_canvas.yview_scroll(1,"units"),add="+")
        for child in widget.winfo_children(): self.bind_quick_mousewheel(child)

    def quick_mousewheel(self,event):
        units=-max(-6,min(6,int(event.delta/120))) if event.delta else 0
        if units: self.quick_canvas.yview_scroll(units,"units")
        return "break"

    def show_quick_page(self):
        start=(self.quick_page_var.get()-1)*30
        for slot,widgets in enumerate(self.quick_page_widgets):
            row=self.quick_rows[start+slot]
            hex_check,data_entry,send_button,delay_entry,enabled_check=widgets
            hex_check.configure(variable=row[2])
            data_entry.configure(textvariable=row[1])
            send_button.configure(textvariable=row[0])
            delay_entry.configure(textvariable=row[3])
            enabled_check.configure(variable=row[4])

    def change_quick_page(self,delta):
        self.quick_page_var.set(max(1,min(10,self.quick_page_var.get()+delta)))
        self.show_quick_page(); self.save_config()

    def send_quick(self,i): self.send_data(self.quick_rows[i][1].get(),self.quick_rows[i][2].get(),True)

    def edit_quick_note(self,i):
        row=self.quick_rows[i]
        note=simpledialog.askstring("快捷指令备注",f"请输入第 {i+1} 条指令的备注：",initialvalue=row[0].get(),parent=self)
        if note is not None:
            note=note.strip() or f"指令{i+1}"
            row[0].set(note); self.save_config()

    def clear_quick(self):
        if not messagebox.askyesno("清空快捷指令", "确定清空全部 300 条快捷指令吗？\n\n指令内容、备注、延时和循环选择都将恢复默认。", parent=self):
            return
        for i,r in enumerate(self.quick_rows):
            r[0].set(f"指令{i+1}"); r[1].set(""); r[2].set(True); r[3].set("1000"); r[4].set(False)
        self.save_config()

    def import_ini(self):
        path=filedialog.askopenfilename(title="导入 SSCOM 配置",initialdir=os.path.dirname(REFERENCE_INI),filetypes=[("INI 配置","*.ini"),("所有文件","*.*")])
        if not path: return
        try:
            raw=open(path,"r",encoding="gb18030",errors="replace").read().splitlines()
            names={}; delays={}; values={}; modes={}
            for line in raw:
                m=re.match(r"N(1\d\d)=(\d+),([^,]*),(\d+)",line)
                if m: names[int(m.group(1))-100]=m.group(3); delays[int(m.group(1))-100]=m.group(4)
                m=re.match(r"N(\d+)=(H|A),(.*)",line)
                if m: values[int(m.group(1))]=m.group(3).strip(); modes[int(m.group(1))]=m.group(2)=="H"
            count=0
            for i,r in enumerate(self.quick_rows,1):
                if i in values:
                    r[0].set(names.get(i,f"指令{i}")); r[1].set(values[i]); r[2].set(modes.get(i,True)); r[3].set(delays.get(i,"1000")); count+=1
            self.status.set(f"已从 INI 导入 {count} 条字符串")
        except Exception as e: messagebox.showerror("导入失败",str(e))

    def cycle_changed(self):
        if self.cycle_send.get(): self.cycle_index=0; self.cycle_tick()
        elif self.cycle_job: self.after_cancel(self.cycle_job); self.cycle_job=None

    def cycle_tick(self):
        if not self.cycle_send.get(): return
        active=[r for r in self.quick_rows if r[4].get() and r[1].get().strip()]
        if not active: self.cycle_send.set(False); return
        row=active[self.cycle_index % len(active)]; self.send_data(row[1].get(),row[2].get(),True); self.cycle_index+=1
        try: delay=max(10,int(row[3].get()))
        except ValueError: delay=1000
        self.cycle_job=self.after(delay,self.cycle_tick)

    def timer_changed(self):
        if self.loading_session: return
        self.save_active_session_state(); self.save_config()
        self.timer_generation+=1
        generation=self.timer_generation; key=self.active_session_key
        if self.timer_on.get():
            try: delay=max(10,int(self.interval.get()))
            except ValueError: delay=1000; self.interval.set("1000")
            self.after(delay,lambda:self.timer_tick(generation,key))

    def timer_tick(self,generation=None,key=None):
        if generation!=self.timer_generation or key!=self.active_session_key or not self.timer_on.get(): return
        self.send_current()
        try: delay=max(10,int(self.interval.get()))
        except ValueError: delay=1000; self.interval.set("1000")
        self.after(delay,lambda:self.timer_tick(generation,key))

    def save_log(self):
        path=filedialog.asksaveasfilename(defaultextension=".txt",filetypes=[("文本文件","*.txt"),("所有文件","*.*")])
        if path:
            with open(path,"w",encoding="utf-8") as f: f.write(self.recv.get("1.0","end-1c"))

    def clear_count(self):
        self.rx_count=self.tx_count=0
        if self.active_session_key in self.sessions:
            self.sessions[self.active_session_key]["rx_count"]=0; self.sessions[self.active_session_key]["tx_count"]=0
        self.update_counter()
    def update_counter(self): self.counter.set(f"接收: {self.rx_count} 字节    发送: {self.tx_count} 字节")

    def on_close(self):
        self.flush_rx_pending()
        # 必须在关闭句柄前记录状态，否则所有会话都会被错误保存为“关闭”。
        self.save_config()
        if self.agent_api_job:
            self.after_cancel(self.agent_api_job); self.agent_api_job=None
        if self.agent_api: self.agent_api.stop()
        self.timer_generation+=1; self.timer_on.set(False)
        for session in self.sessions.values():
            session["stop_event"].set(); session["serial"].close()
        self.t5l_restore_open = False
        if getattr(self, "t5l_window", None): self.t5l_window.close_window()
        if self.poll_job:
            self.after_cancel(self.poll_job); self.poll_job=None
        if self.send_save_job: self.after_cancel(self.send_save_job); self.send_save_job=None
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
