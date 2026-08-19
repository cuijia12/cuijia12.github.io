import os
import re
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

ACK = bytes.fromhex("5A A5 03 82 4F 4B")
RESET = bytes.fromhex("5A A5 07 82 00 04 55 AA 5A A5")
STOP_DGUS_REFRESH = bytes.fromhex("5A A5 07 82 00 FC 55 AA 5A A5")
BLOCK_SIZE = 32 * 1024
T5L51_SIZE = 64 * 1024
FRAME_DATA = 240
# 一个 32KB 缓存块共 137 帧；整块流水发送，行为更接近原厂下载工具。
PIPELINE_FRAMES = 256
WRITE_GROUP_FRAMES = PIPELINE_FRAMES


def file_id(path):
    if os.path.basename(path).lower() == "t5l51.bin": return 0xA5
    m = re.match(r"^(\d{1,2})(?:\D|$)", os.path.basename(path))
    return int(m.group(1)) if m and int(m.group(1)) <= 63 else None


def scan_files(folder):
    allowed = {".bin", ".dzk", ".hzk", ".icl", ".wae"}
    result = []
    if not os.path.isdir(folder): return result
    for name in os.listdir(folder):
        path = os.path.join(folder, name); fid = file_id(path)
        if os.path.isfile(path) and fid is not None and os.path.splitext(name)[1].lower() in allowed:
            result.append((fid, path, os.path.getsize(path)))
    return sorted(result, key=lambda x: (x[0], os.path.basename(x[1]).lower()))


class Downloader:
    def __init__(self, serial, progress, status, stop_event, frame_delay=0, baud=115200, paced=False):
        self.serial, self.progress, self.status, self.stop = serial, progress, status, stop_event
        self.frame_delay = frame_delay
        self.baud = max(1200, int(baud))
        # paced=True：用于被 T5L51 固件配成 8283 协议的 UART2/4/5 口。
        # 该口由 8051 代理逐帧解析并回 4F4B，必须逐帧等待做流控，防止
        # 8051 的小接收缓冲（如 UART2 仅 512B）被流水突发冲爆丢帧。
        self.paced = paced

    def wait_ack(self, timeout=2.0):
        end = time.monotonic() + timeout; buf = bytearray()
        while time.monotonic() < end and not self.stop.is_set():
            data = self.serial.read(256)
            if data:
                buf.extend(data)
                if ACK in buf: return True
            if len(buf) > 1024: del buf[:-64]
        return False

    def send_ack(self, frame, retries=3, delay=.02):
        for _ in range(retries):
            if self.stop.is_set(): raise RuntimeError("用户停止")
            self.serial.write(frame)
            if self.wait_ack():
                if delay: time.sleep(delay)
                return
        raise RuntimeError("屏幕无 OK 应答")

    def read_vp_word(self, vp, timeout=0.6):
        """读 1 个字 VP，返回 16 位值；无应答返回 None。"""
        frame = b"\x5A\xA5\x04\x83" + vp.to_bytes(2, "big") + b"\x01"
        try:
            self.serial.write(frame)
            if hasattr(self.serial, "flush_output"): self.serial.flush_output()
        except Exception:
            return None
        end = time.monotonic() + timeout
        buf = bytearray()
        while time.monotonic() < end and not self.stop.is_set():
            data = self.serial.read(256)
            if data:
                buf.extend(data)
                while True:
                    idx = buf.find(b"\x5A\xA5")
                    if idx < 0:
                        if len(buf) > 512: del buf[:256]
                        break
                    if idx + 9 > len(buf): break  # 帧未收齐
                    if buf[idx + 3] == 0x83:
                        return (buf[idx + 7] << 8) | buf[idx + 8]
                    del buf[:idx + 2]
        return None

    def wait_flash_ready(self, timeout=8.0):
        """轮询 VP 0x00AA 忙标志（首字节），直到 OS 完成写 flash。
        与固件 SPIFlash_Action 的等待方式一致；8283 口下代理的 4F4B
        只代表“已转发”，不代表 flash 已写完。"""
        end = time.monotonic() + timeout
        while time.monotonic() < end and not self.stop.is_set():
            val = self.read_vp_word(0x00AA)
            if val is not None and (val >> 8) == 0:
                return True
            time.sleep(.05)
        return False

    def wait_os_update_done(self, timeout=12.0):
        """等待 OS 完成 8051 flash 编程：轮询 VP 0x0006 直到命令字清零；
        若屏幕已自动复位（连续无应答超过 1s），也视为完成。"""
        end = time.monotonic() + timeout
        silent = 0.0
        while time.monotonic() < end and not self.stop.is_set():
            val = self.read_vp_word(0x0006)
            if val is None:
                silent += .1
                if silent >= 1.0: return True
            else:
                silent = 0.0
                if (val >> 8) == 0: return True
            time.sleep(.1)
        return False

    def wait_screen_online(self, timeout=6.0):
        """复位后读取 VP 0x0000，收到 0x83 返回才认为屏幕真正上线。"""
        query = bytes.fromhex("5A A5 04 83 00 00 01")
        time.sleep(.1)
        if hasattr(self.serial, "purge_input"): self.serial.purge_input()
        end = time.monotonic() + timeout
        buf = bytearray()
        while time.monotonic() < end and not self.stop.is_set():
            self.serial.write(query)
            if hasattr(self.serial, "flush_output"): self.serial.flush_output()
            read_end = min(end, time.monotonic() + .25)
            while time.monotonic() < read_end:
                data = self.serial.read(256)
                if data:
                    buf.extend(data)
                    if b"\x5A\xA5" in buf and b"\x83\x00\x00" in buf:
                        return True
                if len(buf) > 1024: del buf[:-64]
            time.sleep(.05)
        return False

    def write_cache(self, payload, cache_size, sent, total):
        data = payload.ljust(cache_size, b"\xFF")
        if self.paced:
            # 8283 口逐帧模式：8051 代理每帧回 4F4B，必须逐帧等待做流控，
            # 否则其 512 字节接收缓冲会被流水突发冲爆、丢帧后写坏 flash。
            for offset in range(0, cache_size, FRAME_DATA):
                if self.stop.is_set(): raise RuntimeError("用户停止")
                part = data[offset:offset + FRAME_DATA]
                vp = 0x8000 + offset // 2
                frame = b"\x5A\xA5" + bytes([len(part) + 3, 0x82]) + vp.to_bytes(2, "big") + part
                self.serial.write(frame)
                if hasattr(self.serial, "flush_output"): self.serial.flush_output()
                if not self.wait_ack(timeout=1.0):
                    raise RuntimeError(f"8283 逐帧模式：VP 0x{vp:04X} 数据帧无应答")
                sent += len(part)
                self.progress(sent, total)
            return sent
        batch = []
        for offset in range(0, cache_size, FRAME_DATA):
            part = data[offset:offset + FRAME_DATA]
            vp = 0x8000 + offset // 2
            frame = b"\x5A\xA5" + bytes([len(part) + 3, 0x82]) + vp.to_bytes(2, "big") + part
            batch.append((frame, len(part)))
            if len(batch) == PIPELINE_FRAMES or offset + len(part) >= cache_size:
                if self.stop.is_set(): raise RuntimeError("用户停止")
                # 数据帧不逐帧验证应答，整块流水发送；进度按协议字节数平滑估算，
                # 最终由写 flash 命令帧（0x00AA）的 OK 应答确认本块完成。
                batch_bytes = sum(length for _packet, length in batch)
                wire_bytes = sum(len(packet) for packet, _length in batch)
                progress_stop = threading.Event()
                progress_start = time.monotonic()
                def track_transmission():
                    # 串口8N1每字节10bit，按实际协议字节数平滑估算发送进度。
                    while not progress_stop.wait(.02):
                        wire_sent = (time.monotonic() - progress_start) * self.baud / 10
                        ratio = min(1.0, wire_sent / max(1, wire_bytes))
                        shown = min(batch_bytes - 1, int(batch_bytes * ratio))
                        self.progress(sent + shown, total)
                progress_thread = threading.Thread(target=track_transmission, daemon=True)
                progress_thread.start()
                try:
                    for group_start in range(0, len(batch), WRITE_GROUP_FRAMES):
                        if self.stop.is_set(): raise RuntimeError("用户停止")
                        group = batch[group_start:group_start + WRITE_GROUP_FRAMES]
                        self.serial.write(b"".join(packet for packet, _length in group))
                    if hasattr(self.serial, "flush_output"): self.serial.flush_output()
                finally:
                    progress_stop.set(); progress_thread.join(.1)
                sent += batch_bytes
                self.progress(sent, total)
                if hasattr(self.serial, "purge_input"): self.serial.purge_input()
                batch.clear()
        return sent

    def write_block(self, block_no, payload, sent, total):
        sent = self.write_cache(payload, BLOCK_SIZE, sent, total)
        flash = bytes.fromhex("5A A5 0F 82 00 AA 5A 02") + block_no.to_bytes(2, "big") + bytes.fromhex("80 00 00 14 00 00 00 00")
        self.send_ack(flash, retries=5, delay=.05)
        if self.paced:
            # 8283 口下代理对 0x00AA 帧的 4F4B 只代表“已转发”，
            # 必须再等 OS 真正写完 flash，避免下一块数据覆盖缓存。
            if not self.wait_flash_ready():
                raise RuntimeError(f"块 {block_no} 写 flash 未完成（VP 0x00AA 忙标志超时）")
        return sent

    def write_t5l51(self, path, sent, total):
        size = os.path.getsize(path)
        if size > T5L51_SIZE:
            raise RuntimeError(f"T5L51.bin 超过 64KB（当前 {size} 字节）")
        with open(path, "rb") as f: payload = f.read()
        self.status(os.path.basename(path), "缓存 8051 代码")
        sent = self.write_cache(payload, T5L51_SIZE, sent, total)
        self.status(os.path.basename(path), "写入内部 Flash")
        # VP 0x0006: D3=0x5A，D2=0xA5(8051)，D1:D0=0x8000。
        update = bytes.fromhex("5A A5 07 82 00 06 5A A5 80 00")
        self.serial.write(update)
        if hasattr(self.serial, "flush_output"): self.serial.flush_output()
        if self.paced:
            # 8283 口下代理的应答立即返回，不代表 OS 已完成 8051 编程；
            # 轮询 VP 0x0006 命令字清零后再复位，避免打断写 flash。
            self.wait_ack(timeout=1.0)
            if not self.wait_os_update_done():
                raise RuntimeError("T5L51 更新未在超时内完成")
            time.sleep(.05)
        else:
            # 普通 OS 口：0x0006 的 OK 由 OS 在编程完成后返回；超时不报错，
            # 随后显式发送系统复位命令。
            self.wait_ack(timeout=2.0)
            time.sleep(.05)
        self.serial.write(RESET)
        if hasattr(self.serial, "flush_output"): self.serial.flush_output()
        self.status(os.path.basename(path), "等待屏幕重新上线")
        if not self.wait_screen_online():
            raise RuntimeError("复位命令已发送，但未检测到屏幕重新上线")
        self.status(os.path.basename(path), "完成")
        return sent

    def stop_dgus_refresh(self):
        """下载 ICL 前停止 DGUS 刷新，避免界面读取到更新中的混合资源。"""
        self.status("", "停止 DGUS 刷新，准备下载 ICL")
        # 无数据命令帧不验证应答，发送后继续。
        self.serial.write(STOP_DGUS_REFRESH)
        if hasattr(self.serial, "flush_output"): self.serial.flush_output()

    def run(self, files):
        files = sorted(files, key=lambda item: (os.path.basename(item[1]).lower() == "t5l51.bin", item[0]))
        total = sum(T5L51_SIZE if os.path.basename(path).lower() == "t5l51.bin"
                    else (size + BLOCK_SIZE - 1) // BLOCK_SIZE * BLOCK_SIZE
                    for _, path, size in files)
        sent = 0
        self.progress(0, total)
        updated_8051 = False
        dgus_stopped = False
        for fid, path, size in files:
            if os.path.basename(path).lower() == "t5l51.bin":
                sent = self.write_t5l51(path, sent, total)
                updated_8051 = True
                continue
            if os.path.splitext(path)[1].lower() == ".icl" and not dgus_stopped:
                self.stop_dgus_refresh()
                dgus_stopped = True
            with open(path, "rb") as f:
                block_index = 0
                while True:
                    chunk = f.read(BLOCK_SIZE)
                    if not chunk: break
                    self.status(os.path.basename(path), f"写入块 {block_index + 1}")
                    sent = self.write_block(fid * 8 + block_index, chunk, sent, total)
                    block_index += 1
            self.status(os.path.basename(path), "完成")
        if not self.stop.is_set() and not updated_8051:
            self.status("", "写入完成，等待屏幕复位（50ms）")
            end = time.monotonic() + .05
            while time.monotonic() < end:
                if self.stop.is_set(): return
                time.sleep(.05)
            self.serial.write(RESET)
            if hasattr(self.serial, "flush_output"): self.serial.flush_output()
            self.status("", "等待屏幕重新上线")
            if not self.wait_screen_online():
                raise RuntimeError("复位命令已发送，但未检测到屏幕重新上线")


class DownloadWindow(ttk.Frame):
    def __init__(self, master, serial_factory, port_details, config, save_config,
                 shared_settings=None, acquire_serial=None, release_serial=None,
                 sync_shared_baud=None):
        super().__init__(master)
        self.master_app = master
        self.serial_factory, self.port_details = serial_factory, port_details
        self.shared_settings = shared_settings
        self.acquire_serial = acquire_serial
        self.release_serial = release_serial
        self.sync_shared_baud = sync_shared_baud
        self.serial_acquired = False
        self.config_data, self.save_callback = config, save_config
        self.stop_event = threading.Event(); self.worker = None; self.serial = None
        self.excluded_files = {os.path.normcase(path) for path in config.get("t5l_excluded_files", [])}
        self.folder = tk.StringVar(value=config.get("t5l_project", ""))
        saved_port = config.get("t5l_download_port", "")
        self.port = tk.StringVar(value=saved_port)
        self.baud = tk.StringVar(value=str(config.get("t5l_download_baud", "115200")))
        quick_saved = config.get("t5l_quick_select", {})
        self.quick_select = {
            "13": tk.BooleanVar(value=quick_saved.get("13", True)),
            "14": tk.BooleanVar(value=quick_saved.get("14", True)),
            "22": tk.BooleanVar(value=quick_saved.get("22", True)),
            "t5l51": tk.BooleanVar(value=quick_saved.get("t5l51", True)),
        }
        self.download_status = tk.StringVar(value="T5L 在线下载")
        self.make_ui(); self.refresh_ports(sync_shared=not bool(saved_port)); self.scan()
        # 首次打开下载页也立即落盘，确保自动匹配后的有效端口可在重启后恢复。
        self.remember_download_settings()

    def make_ui(self):
        ttk.Label(self, textvariable=self.download_status, font=("Segoe UI Variable Display", 13, "bold")).pack(fill="x", padx=12, pady=(10, 0))
        top = ttk.Frame(self); top.pack(fill="x", padx=12, pady=12)
        ttk.Label(top, text="DWIN_SET").pack(side="left")
        self.folder_entry = ttk.Entry(top, textvariable=self.folder)
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=8)
        self.folder_entry.bind("<Return>", lambda _event: self.scan())
        self.folder_entry.bind("<FocusOut>", lambda _event: self.remember_folder())
        ttk.Button(top, text="选择目录", command=self.choose).pack(side="left")
        ttk.Button(top, text="选择文件", command=self.choose_files).pack(side="left", padx=(6, 0))
        ttk.Button(top, text="刷新文件", command=self.scan).pack(side="left", padx=(6, 0))
        ttk.Button(top, text="移出列表", command=self.delete_selected).pack(side="left", padx=(6, 0))
        quick = ttk.Frame(self); quick.pack(fill="x", padx=12, pady=(0, 8))
        ttk.Label(quick, text="快速选择").pack(side="left", padx=(0, 12))
        for key, label in (("13", "13文件"), ("14", "14文件"), ("22", "22文件"), ("t5l51", "T5L51.bin")):
            ttk.Checkbutton(quick, text=label, variable=self.quick_select[key],
                            command=lambda selected_key=key:self.quick_selection_changed(selected_key)).pack(side="left", padx=(0, 28))
        self.tree = ttk.Treeview(self, columns=("id", "size", "status"), show="tree headings", selectmode="extended")
        self.tree.heading("#0", text="文件名"); self.tree.heading("id", text="文件ID"); self.tree.heading("size", text="大小"); self.tree.heading("status", text="状态")
        self.tree.column("#0", width=380); self.tree.column("id", width=70, anchor="center"); self.tree.column("size", width=100, anchor="e"); self.tree.column("status", width=120)
        self.tree.pack(fill="both", expand=True, padx=12)
        self.tree.bind("<Delete>", lambda _event: self.delete_selected())
        self.tree.bind("<<TreeviewSelect>>", self.enforce_quick_selection, add="+")
        self.tree.bind("<Button-3>", self.show_file_context_menu)
        self.tree.bind("<ButtonPress-1>", self.begin_file_drag_selection, add="+")
        self.tree.bind("<B1-Motion>", self.update_file_drag_selection, add="+")
        self.tree.bind("<ButtonRelease-1>", self.end_file_drag_selection, add="+")
        self.tree.bind("<Control-a>", self.select_all_files)
        self.file_drag_anchor = None
        self.file_drag_active = False
        ttk.Label(self, text="提示：选中文件可只下载选中项；未选中时下载全部。屏幕内核须支持 0x00AA 外部 Flash 更新协议。").pack(fill="x", padx=12, pady=(6, 0))
        controls = ttk.LabelFrame(self, text=" 下载设置 ", padding=10); controls.pack(fill="x", padx=12, pady=10)
        ttk.Label(controls, text="共用串口").pack(side="left"); self.port_box = ttk.Combobox(controls, textvariable=self.port, state="readonly", width=30); self.port_box.pack(side="left", padx=6)
        self.port_box.bind("<<ComboboxSelected>>", self.shared_port_selected)
        ttk.Button(controls, text="刷新", command=self.refresh_ports).pack(side="left")
        ttk.Label(controls, text="波特率").pack(side="left", padx=(12, 3)); self.baud_box = ttk.Combobox(controls, textvariable=self.baud, values=["9600", "115200", "921600"], width=10, state="readonly"); self.baud_box.pack(side="left")
        self.baud_box.bind("<<ComboboxSelected>>", self.shared_baud_selected)
        self.paced_var = tk.BooleanVar(value=bool(self.config_data.get("t5l_paced_8283", False)))
        ttk.Checkbutton(controls, text="8283逐帧模式", variable=self.paced_var,
                        command=self.remember_download_settings).pack(side="left", padx=(12, 0))
        self.start_btn = ttk.Button(controls, text="开始下载", command=self.start); self.start_btn.pack(side="right")
        ttk.Button(controls, text="停止", command=self.stop_download).pack(side="right", padx=6)
        progress_row = ttk.Frame(self); progress_row.pack(fill="x", padx=12, pady=(0, 12))
        self.progress = ttk.Progressbar(progress_row, maximum=100); self.progress.pack(side="left", fill="x", expand=True)
        self.progress_text = tk.StringVar(value="0%")
        self.last_progress = -1
        ttk.Label(progress_row, textvariable=self.progress_text, width=5, anchor="e").pack(side="right", padx=(8, 0))

    def choose(self):
        p = filedialog.askdirectory(title="选择 DWIN_SET 目录", initialdir=self.folder.get() or None)
        if p:
            self.folder.set(p)
            # 主动选择目录表示重新载入该工程的全部可下载文件。
            for _fid, path, _size in scan_files(p):
                self.excluded_files.discard(os.path.normcase(path))
            for var in self.quick_select.values(): var.set(True)
            self.config_data["t5l_excluded_files"] = sorted(self.excluded_files)
            self.config_data["t5l_quick_select"] = {key: True for key in self.quick_select}
            self.remember_folder(); self.save_callback(); self.scan()
    def choose_files(self):
        paths = filedialog.askopenfilenames(
            title="选择 T5L 下载文件",
            initialdir=self.folder.get() if os.path.isdir(self.folder.get()) else None,
            filetypes=[("T5L 文件", "*.bin *.dzk *.hzk *.icl *.wae"), ("所有文件", "*.*")],
            parent=self)
        if not paths:
            return
        existing = {os.path.normcase(item[1]) for item in self.files}
        invalid = []
        for path in paths:
            fid = file_id(path)
            if fid is None:
                invalid.append(os.path.basename(path))
                continue
            key = os.path.normcase(path)
            if key in self.excluded_files:
                self.excluded_files.discard(key)
                self.remember_list_state()
            if key not in existing:
                self.files.append((fid, path, os.path.getsize(path)))
                existing.add(key)
        self.files.sort(key=lambda item: (item[0], os.path.basename(item[1]).lower()))
        self.show_files()
        if invalid:
            messagebox.showwarning("无法添加部分文件", "文件名必须以 0～63 的文件 ID 开头，或命名为 T5L51.bin：\n\n" + "\n".join(invalid), parent=self)
    def refresh_ports(self,sync_shared=False):
        vals = [label for _, label in self.port_details()]; self.port_box["values"] = vals
        shared_port, shared_baud = self.shared_settings() if self.shared_settings else (self.port.get(), self.baud.get())
        # 首次创建时继承串口助手当前选择；之后刷新或再次进入页面时，
        # T5L 保持自己的下拉选择，不跟随串口助手标签切换。
        wanted = shared_port if sync_shared or not self.port.get() else self.port.get()
        wanted_no = re.match(r"\s*(COM\d+)", wanted, re.I)
        match = next((label for label in vals if wanted_no and label.upper().startswith(wanted_no.group(1).upper())), None)
        if match: self.port.set(match)
        elif vals and self.port.get() not in vals: self.port.set(vals[0])
        if sync_shared and shared_baud: self.baud.set(str(shared_baud))
        self.sync_baud_if_same_port(prefer_shared=True)

    @staticmethod
    def port_number(value):
        match = re.match(r"\s*(COM\d+)", value or "", re.I)
        return match.group(1).upper() if match else ""

    def sync_baud_if_same_port(self, prefer_shared=False):
        """仅当两边选中同一个 COM 口时同步波特率。"""
        if not self.shared_settings:
            return False
        shared_port, shared_baud = self.shared_settings()
        if self.port_number(self.port.get()) != self.port_number(shared_port):
            return False
        if prefer_shared and shared_baud:
            self.baud.set(str(shared_baud))
        elif self.sync_shared_baud:
            self.sync_shared_baud(self.port_number(self.port.get()), self.baud.get())
        return True

    def shared_port_selected(self, _event=None):
        # T5L 端口仍独立选择；恰好选到串口助手当前端口时才继承其波特率。
        self.sync_baud_if_same_port(prefer_shared=True)
        self.remember_download_settings()

    def shared_baud_selected(self, _event=None):
        # 用户在 T5L 侧修改同一端口的波特率时，反向更新串口助手。
        self.sync_baud_if_same_port(prefer_shared=False)
        self.remember_download_settings()

    def remember_download_settings(self):
        """立即保存 T5L 独立串口和波特率，供下次启动恢复。"""
        self.config_data["t5l_download_port"] = self.port.get()
        self.config_data["t5l_download_baud"] = self.baud.get()
        self.config_data["t5l_paced_8283"] = bool(self.paced_var.get()) if hasattr(self, "paced_var") else False
        self.save_callback()

    def sync_baud_from_serial(self, port, baud):
        """串口助手侧变更时，只更新选择了同一端口的 T5L 波特率。"""
        if self.port_number(self.port.get()) == self.port_number(port):
            if self.baud.get() != str(baud):
                self.baud.set(str(baud))
                self.remember_download_settings()
            return True
        return False
    def scan(self):
        self.remember_folder()
        scanned = scan_files(self.folder.get())
        # 快速选择必须反映当前目录实际存在的文件。切换到不包含对应
        # 文件的目录时立即取消勾选，避免空列表仍显示为已选择。
        available_keys = {self.file_quick_key(fid, path) for fid, path, _size in scanned}
        quick_changed = False
        for key, var in self.quick_select.items():
            if key not in available_keys and var.get():
                var.set(False)
                quick_changed = True
        if quick_changed:
            self.config_data["t5l_quick_select"] = {
                key: var.get() for key, var in self.quick_select.items()
            }
        # 快速选择控制的文件不使用永久排除；兼容清理旧配置中的特殊文件记录。
        for fid, path, _size in scanned:
            key = self.file_quick_key(fid, path)
            if key: self.excluded_files.discard(os.path.normcase(path))
        self.files = [item for item in scanned if os.path.normcase(item[1]) not in self.excluded_files]
        self.config_data["t5l_excluded_files"] = sorted(self.excluded_files)
        if quick_changed:
            self.save_callback()
        self.show_files()
    def remember_folder(self):
        path = self.folder.get().strip()
        if os.path.isdir(path) and self.config_data.get("t5l_project") != path:
            self.config_data["t5l_project"] = path
            self.save_callback()
    def show_files(self):
        selected = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children())
        for fid, path, size in self.files:
            if not self.file_quick_enabled(fid, path): continue
            shown_id = "8051" if os.path.basename(path).lower() == "t5l51.bin" else fid
            self.tree.insert("", "end", iid=path, text=os.path.basename(path), values=(shown_id, f"{size/1024:.1f} KB", "等待"))
            if path in selected: self.tree.selection_add(path)
    def file_quick_enabled(self, fid, path):
        key = self.file_quick_key(fid, path)
        return self.quick_select[key].get() if key else True
    def file_quick_key(self, fid, path):
        if os.path.basename(path).lower() == "t5l51.bin": return "t5l51"
        if fid in (13, 14, 22): return str(fid)
        return None
    def quick_selection_changed(self, selected_key=None):
        # 用户勾选快捷项时，先确认当前目录确实包含对应文件。
        # 缺失时立即恢复为未勾选，避免界面看似已选但列表没有任何变化。
        scanned = scan_files(self.folder.get())
        available_keys = {self.file_quick_key(fid, path) for fid, path, _size in scanned}
        if (selected_key and self.quick_select[selected_key].get()
                and selected_key not in available_keys):
            self.quick_select[selected_key].set(False)
            labels = {"13":"13号文件", "14":"14号文件", "22":"22号文件", "t5l51":"T5L51.bin"}
            folder = self.folder.get().strip() or "（尚未选择目录）"
            messagebox.showwarning(
                "快捷文件不存在",
                f"当前选择的目录中没有找到 {labels[selected_key]}。\n\n目录：{folder}\n\n请更换目录或使用“选择文件”手动添加。",
                parent=self)
        self.config_data["t5l_quick_select"] = {key: var.get() for key, var in self.quick_select.items()}
        # 特殊文件重新勾选时，从当前目录恢复到列表，并取消旧版留下的排除记录。
        known = {os.path.normcase(item[1]) for item in self.files}
        exclusions_changed = False
        for item in scanned:
            fid, path, _size = item; key = self.file_quick_key(fid, path)
            if key and self.quick_select[key].get():
                normalized = os.path.normcase(path)
                if normalized in self.excluded_files:
                    self.excluded_files.discard(normalized); exclusions_changed = True
                if normalized not in known:
                    self.files.append(item); known.add(normalized)
        self.files.sort(key=lambda item: (item[0], os.path.basename(item[1]).lower()))
        if exclusions_changed:
            self.config_data["t5l_excluded_files"] = sorted(self.excluded_files)
        self.save_callback(); self.show_files()
    def enforce_quick_selection(self, _event=None):
        """手动选中特殊文件时，自动勾选对应的快速选择项。"""
        changed = False
        for fid, path, _size in self.files:
            key = self.file_quick_key(fid, path)
            if path in self.tree.selection() and key and not self.quick_select[key].get():
                self.quick_select[key].set(True)
                self.tree.set(path, "status", "等待")
                changed = True
        if changed:
            self.config_data["t5l_quick_select"] = {key: var.get() for key, var in self.quick_select.items()}
            self.save_callback()
    def delete_selected(self):
        selected = list(self.tree.selection())
        if not selected:
            messagebox.showwarning("移出列表", "请先选择不需要下载的文件", parent=self)
            return
        ordinary_selected = set()
        quick_changed = False
        for fid, path, _size in self.files:
            if path not in selected: continue
            key = self.file_quick_key(fid, path)
            if key:
                self.quick_select[key].set(False)
                self.excluded_files.discard(os.path.normcase(path))
                quick_changed = True
            else:
                ordinary_selected.add(path)
                self.excluded_files.add(os.path.normcase(path))
        self.files = [item for item in self.files if item[1] not in ordinary_selected]
        if quick_changed:
            self.config_data["t5l_quick_select"] = {key: var.get() for key, var in self.quick_select.items()}
        self.remember_list_state()
        self.show_files()
    def show_file_context_menu(self, event):
        row = self.tree.identify_row(event.y)
        if row and row not in self.tree.selection(): self.tree.selection_set(row)
        menu = tk.Menu(self, tearoff=False)
        menu.add_command(label="下载选中文件", command=self.start,
                         state="normal" if self.tree.selection() else "disabled")
        menu.add_command(label="移出列表", command=self.delete_selected,
                         state="normal" if self.tree.selection() else "disabled")
        menu.add_separator()
        menu.add_command(label="全选", command=lambda:self.tree.selection_set(self.tree.get_children()))
        menu.add_command(label="取消选择", command=lambda:self.tree.selection_remove(self.tree.selection()))
        try: menu.tk_popup(event.x_root, event.y_root)
        finally: menu.grab_release()
        return "break"
    def select_all_files(self, _event=None):
        self.tree.selection_set(self.tree.get_children())
        return "break"
    def begin_file_drag_selection(self, event):
        """按住左键拖过多行时，连续选中范围内的文件。"""
        row = self.tree.identify_row(event.y)
        if not row:
            self.file_drag_anchor = None; self.file_drag_active = False
            return None
        previous_anchor = self.file_drag_anchor
        self.file_drag_active = True
        if (event.state & 0x0001) and previous_anchor:
            children = list(self.tree.get_children())
            if previous_anchor in children and row in children:
                first, last = children.index(previous_anchor), children.index(row)
                start, end = sorted((first, last))
                self.tree.selection_set(children[start:end + 1]); self.tree.focus(row)
                return "break"
        self.file_drag_anchor = row
        # Ctrl 点击继续使用 Treeview 原生的增减选择。
        if not (event.state & 0x0004):
            self.tree.selection_set(row); self.tree.focus(row)
            return "break"
        return None
    def update_file_drag_selection(self, event):
        if not self.file_drag_active or not self.file_drag_anchor: return None
        row = self.tree.identify_row(event.y)
        children = list(self.tree.get_children())
        if not row or row not in children or self.file_drag_anchor not in children: return "break"
        first, last = children.index(self.file_drag_anchor), children.index(row)
        start, end = sorted((first, last))
        self.tree.selection_set(children[start:end + 1])
        self.tree.focus(row); self.tree.see(row)
        return "break"
    def end_file_drag_selection(self, _event=None):
        self.file_drag_active = False
        return None
    def remember_list_state(self):
        self.config_data["t5l_excluded_files"] = sorted(self.excluded_files)
        self.save_callback()
    def status(self, path_or_name, text):
        def update():
            if not path_or_name:
                self.download_status.set(text)
                return
            for iid in self.tree.get_children():
                if os.path.basename(iid) == os.path.basename(path_or_name): self.tree.set(iid, "status", text)
        self.after(0, update)
    def set_progress(self, done, total):
        percent = min(100, int(done * 100 / max(1, total)))
        if percent == self.last_progress: return
        self.last_progress = percent
        self.after(0, lambda p=percent: (self.progress.configure(value=p), self.progress_text.set(f"{p}%")))
    def start(self):
        if not self.files: messagebox.showwarning("T5L 下载", "目录中没有带数字文件ID的可下载文件"); return
        selected = set(self.tree.selection())
        download_files = [item for item in self.files
                          if self.file_quick_enabled(*item[:2]) and
                          (item[1] in selected if selected else True)]
        if not download_files:
            messagebox.showwarning("T5L 下载", "没有选中需要下载的文件"); return
        m = re.match(r"(COM\d+)", self.port.get())
        if not m: messagebox.showwarning("T5L 下载", "请选择独立下载串口"); return
        try:
            if self.acquire_serial:
                self.acquire_serial(m.group(1)); self.serial_acquired = True
            self.serial = self.serial_factory(); self.serial.open(m.group(1), int(self.baud.get()), 8, "无", "1")
            if hasattr(self.serial, "set_read_timeout"): self.serial.set_read_timeout(1)
        except Exception as e:
            self.release_shared_serial()
            messagebox.showerror("打开下载串口失败", str(e)); return
        self.stop_event.clear(); self.start_btn.configure(state="disabled")
        self.last_progress = -1
        self.config_data["t5l_project"] = self.folder.get(); self.save_callback()
        def work():
            try:
                frame_delay = 0
                Downloader(self.serial, self.set_progress, self.status, self.stop_event,
                           frame_delay, int(self.baud.get()),
                           bool(self.config_data.get("t5l_paced_8283", False))).run(download_files)
                if not self.stop_event.is_set():
                    self.after(0, lambda: messagebox.showinfo("T5L 下载", "下载完成，屏幕已复位"))
            except Exception as e:
                # ICL 下载前可能已停止 DGUS 刷新；失败时尽力复位，避免屏幕保持停止状态。
                try:
                    if self.serial and self.serial.is_open:
                        self.serial.write(RESET)
                        if hasattr(self.serial, "flush_output"): self.serial.flush_output()
                except Exception:
                    pass
                self.after(0, lambda err=str(e): messagebox.showerror("T5L 下载失败", err))
            finally:
                if self.serial: self.serial.close()
                self.release_shared_serial()
                self.after(0, lambda: self.start_btn.configure(state="normal"))
        self.worker = threading.Thread(target=work, daemon=True); self.worker.start()
    def stop_download(self): self.stop_event.set()
    def release_shared_serial(self):
        if self.serial_acquired:
            self.serial_acquired = False
            if self.release_serial:
                def release():
                    try: self.release_serial()
                    except tk.TclError: pass
                if threading.current_thread() is threading.main_thread(): release()
                else: self.master_app.after(0, release)
    def close_window(self):
        self.stop_event.set()
        if self.serial:
            try: self.serial.close()
            except Exception: pass
        self.release_shared_serial()
