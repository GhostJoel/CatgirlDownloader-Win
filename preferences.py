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
        self.load()

    def load(self):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                for key, default in DEFAULTS.items():
                    self.data[key] = saved.get(key, default)
        except (OSError, ValueError):
            # 文件不存在或损坏：保持默认值即可
            pass

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
