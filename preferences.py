# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 MoRan
#
# CatgirlDownloader —— Windows 移植版 (Tkinter)
# 基于 NyarchLinux/CatgirlDownloader 移植：
#   原项目 Copyright (C) 2026 SilverOS，许可证 GPL-3.0-or-later
#   https://github.com/NyarchLinux/CatgirlDownloader
# 修改日期 2026-09-20：配置路径改用 %APPDATA%。

"""用户偏好设置：读写 %APPDATA%\\CatgirlDownloader\\config.json。"""

import json
import os

# Windows 用 %APPDATA%，其它平台退回用户主目录
_CONFIG_ROOT = os.environ.get("APPDATA") or os.path.expanduser("~")
CONFIG_DIR = os.path.join(_CONFIG_ROOT, "CatgirlDownloader")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULTS = {
    "source": "catgirl",            # 当前图源 id
    "nsfw_mode": "Block NSFW",      # Show everything / Only NSFW / Block NSFW
    "auto_reload_enabled": False,
    "auto_reload_interval": 5,      # 秒
    "danbooru_tags": "",            # danbooru 自定义搜索标签
}


class Preferences:
    """极简配置对象，缺失的键自动用默认值补齐。"""

    def __init__(self):
        self.data = dict(DEFAULTS)
        self._load_or_init()

    def _load_or_init(self):
        """读取配置；文件不存在或损坏时，立即生成一份默认配置。"""
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if not isinstance(saved, dict):
                raise ValueError("配置格式不正确")
        except (OSError, ValueError):
            # 首次运行（或文件损坏）：写出一份默认配置
            self.save()
            return
        # 合并：保留文件中的已有值（含未知键），补齐缺失的默认键
        merged = dict(saved)
        for key, default in DEFAULTS.items():
            merged.setdefault(key, default)
        self.data = merged
        if merged != saved:
            self.save()  # 补过缺键，落盘规范化

    def save(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        if self.data.get(key) != value:
            self.data[key] = value
            self.save()
