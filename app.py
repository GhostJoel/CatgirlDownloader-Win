# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 MoRan
#
# CatgirlDownloader —— Windows 移植版 (Tkinter)
# 基于 NyarchLinux/CatgirlDownloader 移植：
#   原项目 Copyright (C) 2026 SilverOS，许可证 GPL-3.0-or-later
#   https://github.com/NyarchLinux/CatgirlDownloader
# 修改日期 2026-09-20：界面与网络层由 GTK4/requests 改写为 Tkinter/urllib。

"""Catgirl Downloader —— Windows (Tkinter) 版。

依赖只有 Pillow（显示 JPG/WebP 等），网络走标准库 urllib。
功能：从 nekos.moe / waifu.im / danbooru 随机抓图，显示、保存、自动刷新。
"""

import ctypes
import io
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from preferences import Preferences
from sources import (
    BLOCK_NSFW,
    NSFW_MODES,
    SOURCES,
    DownloaderError,
    download_bytes,
)

APP_TITLE = "Catgirl Downloader"
FALLBACK_W, FALLBACK_H = 900, 700
PUMP_MS = 80  # 主线程轮询结果队列的间隔


def resource_path(name):
    """兼容源码运行与 PyInstaller 打包（_MEIPASS）两种情况的资源定位。"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def enable_dpi_awareness():
    """让高分屏下界面不发虚（失败也无所谓）。"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class App:
    def __init__(self, root):
        self.root = root
        self.prefs = Preferences()
        self.sources = {cls.id: cls(self.prefs) for cls in SOURCES}
        self._source_ids = [cls.id for cls in SOURCES]

        self.result_queue = queue.Queue()
        self._loading = False
        self._closed = False
        self._pump_id = None
        self._gen = 0            # 每次请求递增，用来丢弃过期结果
        self._auto_id = None     # after() 定时器 id
        self._auto_token = 0

        self._raw = None         # 当前图片原始字节
        self._pil = None         # 当前图片的 PIL 原图（用于缩放重绘）
        self._photo = None       # 保引用，防止被回收
        self._ext = None
        self._last_size = None
        self.current = self.prefs.get("source", "catgirl")
        if self.current not in self.sources:
            self.current = self._source_ids[0]

        self._build_ui()
        self._apply_prefs()
        self._set_window_icon()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._pump_id = self.root.after(PUMP_MS, self._pump)
        self.reload()

    # ---------- 界面 ----------
    def _build_ui(self):
        self.root.title(APP_TITLE)
        self.root.minsize(520, 420)

        bar = ttk.Frame(self.root, padding=8)
        bar.pack(side="top", fill="x")

        ttk.Label(bar, text="图源").pack(side="left")
        self._name_to_id = {self.sources[sid].name: sid for sid in self._source_ids}
        self.source_var = tk.StringVar()
        self.source_box = ttk.Combobox(
            bar, textvariable=self.source_var, state="readonly", width=10,
            values=[self.sources[sid].name for sid in self._source_ids],
        )
        self.source_box.pack(side="left", padx=(4, 12))
        self.source_box.bind("<<ComboboxSelected>>", self._on_source_changed)

        ttk.Label(bar, text="NSFW").pack(side="left")
        self.nsfw_var = tk.StringVar()
        self.nsfw_box = ttk.Combobox(
            bar, textvariable=self.nsfw_var, state="readonly", width=15, values=NSFW_MODES
        )
        self.nsfw_box.pack(side="left", padx=(4, 12))
        self.nsfw_box.bind("<<ComboboxSelected>>", self._on_nsfw_changed)

        self.refresh_btn = ttk.Button(bar, text="刷新", command=self.reload)
        self.refresh_btn.pack(side="left")
        self.save_btn = ttk.Button(bar, text="保存", command=self.save, state="disabled")
        self.save_btn.pack(side="left", padx=6)

        sep = ttk.Separator(bar, orient="vertical")
        sep.pack(side="left", fill="y", padx=6)

        self.auto_var = tk.BooleanVar()
        self.auto_chk = ttk.Checkbutton(
            bar, text="自动刷新", variable=self.auto_var, command=self._on_auto_toggle
        )
        self.auto_chk.pack(side="left")
        self.interval_var = tk.StringVar()
        self.interval_spin = ttk.Spinbox(
            bar, from_=1, to=3600, width=5, textvariable=self.interval_var,
            command=self._on_interval_changed,
        )
        self.interval_spin.pack(side="left", padx=(6, 0))
        self.interval_spin.bind("<FocusOut>", lambda _e: self._on_interval_changed())
        self.interval_spin.bind("<Return>", lambda _e: self._on_interval_changed())
        ttk.Label(bar, text="秒").pack(side="left", padx=(2, 6))

        ttk.Button(bar, text="设置", command=self.open_settings).pack(side="right")

        self.image_label = tk.Label(self.root, text="加载中…", anchor="center")
        self.image_label.pack(side="top", fill="both", expand=True)
        self.image_label.bind("<Configure>", self._on_configure)

        self.status_var = tk.StringVar(value="")
        ttk.Label(
            self.root, textvariable=self.status_var, anchor="w", relief="sunken", padding=(6, 3)
        ).pack(side="bottom", fill="x")

    def _set_window_icon(self):
        path = resource_path("icon.ico")
        if os.path.exists(path):
            try:
                self.root.iconbitmap(path)
            except Exception:
                pass

    def _apply_prefs(self):
        self.source_var.set(self.sources[self.current].name)
        nsfw = self.prefs.get("nsfw_mode", BLOCK_NSFW)
        self.nsfw_var.set(nsfw if nsfw in NSFW_MODES else BLOCK_NSFW)
        self.auto_var.set(bool(self.prefs.get("auto_reload_enabled", False)))
        self.interval_var.set(str(self._read_interval()))

    def _read_interval(self):
        try:
            return max(1, int(self.prefs.get("auto_reload_interval", 5)))
        except (TypeError, ValueError):
            return 5

    # ---------- 抓取 ----------
    def reload(self):
        self._gen += 1
        gen = self._gen
        self._loading = True
        self._cancel_auto()
        self.refresh_btn.configure(state="disabled")
        self.save_btn.configure(state="disabled")
        self.status_var.set("加载中…")
        # 在主线程读取 Tk 变量/状态，再传给后台线程（线程里碰 Tk 变量会报错）
        sid = self.current
        mode = self.nsfw_var.get() or BLOCK_NSFW
        threading.Thread(target=self._worker, args=(gen, sid, mode), daemon=True).start()

    def _worker(self, gen, sid, mode):
        try:
            src = self.sources[sid]
            url = src.get_image_url(mode)
            raw = download_bytes(url, src.request_headers())
            self.result_queue.put(("ok", gen, src, raw))
        except Exception as exc:  # noqa: BLE001 - 统一交给界面提示
            self.result_queue.put(("err", gen, exc))

    def _pump(self):
        if self._closed:
            return
        try:
            while True:
                self._handle_result(self.result_queue.get_nowait())
        except queue.Empty:
            pass
        self._pump_id = self.root.after(PUMP_MS, self._pump)

    def _handle_result(self, msg):
        kind, gen = msg[0], msg[1]
        if gen != self._gen:
            return  # 过期结果，丢弃
        if kind == "ok":
            _, _, src, raw = msg
            try:
                self._show_image(raw)
                self._raw = raw
                self.save_btn.configure(state="normal")
                self._update_status(src)
            except Exception as exc:  # noqa: BLE001
                self._raw = None
                self.status_var.set(f"无法显示图片：{exc}")
        else:
            self._raw = None
            self.status_var.set(f"加载失败：{msg[2]}")
        self._loading = False
        self.refresh_btn.configure(state="normal")
        self._schedule_auto()

    # ---------- 显示 ----------
    def _show_image(self, raw):
        pil = Image.open(io.BytesIO(raw))
        self._ext = (pil.format or "").lower() or None
        if pil.mode not in ("RGB", "RGBA"):
            pil = pil.convert("RGB")
        self._pil = pil
        self._last_size = None
        self._render()

    def _render(self):
        if self._pil is None:
            return
        w = self.image_label.winfo_width()
        h = self.image_label.winfo_height()
        if w < 50 or h < 50:
            w, h = FALLBACK_W, FALLBACK_H
        im = self._pil.copy()
        im.thumbnail((max(w - 8, 64), max(h - 8, 64)))
        self._photo = ImageTk.PhotoImage(im)
        self.image_label.configure(image=self._photo, text="")

    def _on_configure(self, event):
        if self._pil is None:
            return
        if (event.width, event.height) == self._last_size:
            return
        self._last_size = (event.width, event.height)
        self._render()

    def _update_status(self, src):
        parts = [src.name]
        artist = src.get_artist()
        link = src.get_link()
        if artist:
            parts.append(f"作者：{artist}")
        if link:
            parts.append(link)
        self.status_var.set("   |   ".join(parts))

    # ---------- 保存 ----------
    def save(self):
        if not self._raw:
            return
        src = self.sources[self.current]
        suggested = src.suggest_name(self._ext)
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="保存图片",
            initialfile=suggested,
            defaultextension=f".{self._ext}" if self._ext else "",
            filetypes=[(f"{self._ext.upper()} 图片", f"*.{self._ext}"), ("所有文件", "*.*")]
            if self._ext else [("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "wb") as f:
                f.write(self._raw)
            self.status_var.set(f"已保存：{path}")
        except OSError as exc:
            messagebox.showerror(APP_TITLE, f"保存失败：{exc}", parent=self.root)

    # ---------- 自动刷新 ----------
    def _on_auto_toggle(self):
        enabled = bool(self.auto_var.get())
        self.prefs.set("auto_reload_enabled", enabled)
        if enabled:
            self._schedule_auto()
        else:
            self._cancel_auto()

    def _schedule_auto(self):
        self._cancel_auto()
        if not self.auto_var.get() or self._loading:
            return
        secs = self._read_interval()
        self._auto_token += 1
        token = self._auto_token
        self._auto_id = self.root.after(secs * 1000, lambda: self._auto_fire(token))

    def _auto_fire(self, token):
        self._auto_id = None
        if token != self._auto_token or not self.auto_var.get():
            return
        self.reload()

    def _cancel_auto(self):
        if self._auto_id is not None:
            try:
                self.root.after_cancel(self._auto_id)
            except Exception:
                pass
            self._auto_id = None

    def _on_interval_changed(self):
        secs = self._read_spinbox_interval()
        self.interval_var.set(str(secs))
        self.prefs.set("auto_reload_interval", secs)
        if self.auto_var.get():
            self._schedule_auto()

    def _read_spinbox_interval(self):
        try:
            return max(1, int(self.interval_var.get()))
        except (TypeError, ValueError):
            return 5

    # ---------- 下拉 / 设置 ----------
    def _on_source_changed(self, _event=None):
        sid = self._name_to_id.get(self.source_var.get())
        if sid and sid != self.current:
            self.current = sid
            self.prefs.set("source", sid)
            self.reload()

    def _on_nsfw_changed(self, _event=None):
        mode = self.nsfw_var.get()
        self.prefs.set("nsfw_mode", mode)
        self.reload()

    def open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("设置")
        win.transient(self.root)
        win.resizable(False, False)

        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Danbooru 搜索标签（空格分隔，如：cat_ears solo 1girl）").grid(
            row=0, column=0, sticky="w"
        )
        tags_var = tk.StringVar(value=self.prefs.get("danbooru_tags", ""))
        entry = ttk.Entry(frm, textvariable=tags_var, width=50)
        entry.grid(row=1, column=0, sticky="we", pady=(4, 6))
        ttk.Label(
            frm, text="提示：shota / loli 会被 danbooru 拒绝，已自动过滤。",
            foreground="#888888",
        ).grid(row=2, column=0, sticky="w")

        def save_close():
            cleaned = [t for t in tags_var.get().split() if t.lower() not in ("shota", "loli")]
            self.prefs.set("danbooru_tags", " ".join(cleaned))
            win.destroy()

        btns = ttk.Frame(frm)
        btns.grid(row=3, column=0, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="取消", command=win.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(btns, text="保存", command=save_close).pack(side="right")

        entry.focus_set()
        win.grab_set()

    def _on_close(self):
        self._closed = True
        self._cancel_auto()
        if self._pump_id is not None:
            try:
                self.root.after_cancel(self._pump_id)
            except Exception:
                pass
            self._pump_id = None
        self.root.destroy()


def main():
    enable_dpi_awareness()
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
