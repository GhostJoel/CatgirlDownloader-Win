# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 MoRan
#
# CatgirlDownloader —— Windows 移植版 (Tkinter)
# 基于 NyarchLinux/CatgirlDownloader 移植：
#   原项目 Copyright (C) 2026 SilverOS，许可证 GPL-3.0-or-later
#   https://github.com/NyarchLinux/CatgirlDownloader
# 修改日期 2026-09-20：移植 catgirl/waifu/danbooru 三个 API 类，网络改用 urllib。

"""三个图源的抓取逻辑。

只用标准库 urllib 发请求（除 Pillow 外不引入第三方网络库），
移植自 NyarchLinux/CatgirlDownloader 的 catgirl / waifu / danbooru 三个 API 类。
"""

import json
import time
import urllib.parse
import urllib.request

# ---- NSFW 模式（字符串即显示名，和原版保持一致） ----
SHOW_EVERYTHING = "Show everything"
ONLY_NSFW = "Only NSFW"
BLOCK_NSFW = "Block NSFW"
NSFW_MODES = [SHOW_EVERYTHING, ONLY_NSFW, BLOCK_NSFW]

TIMEOUT = 20
USER_AGENT = "CatgirlDownloader-Win/1.0 (+https://github.com/NyarchLinux/CatgirlDownloader)"
_HEADERS = {"User-Agent": USER_AGENT}

# danbooru 会拒绝这两个标签，抓取/保存时都过滤掉
FORBIDDEN_TAGS = {"shota", "loli"}


class DownloaderError(Exception):
    """抓取或解析失败时抛出，界面据此提示用户。"""


def _http_get(url, headers=None, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers=dict(headers or {}))
    if not req.has_header("User-agent"):
        req.add_header("User-Agent", USER_AGENT)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _get_json(url, headers=None, timeout=TIMEOUT):
    raw = _http_get(url, headers, timeout)
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise DownloaderError(f"返回数据无法解析：{exc}") from exc


def download_bytes(url, headers=None, timeout=TIMEOUT):
    """下载图片原始字节。"""
    if not url:
        raise DownloaderError("图片地址为空")
    return _http_get(url, headers, timeout)


def _ext_suffix(ext):
    return f".{ext}" if ext else ""


class BaseSource:
    id = ""
    name = ""
    description = ""

    def __init__(self, prefs):
        self.prefs = prefs
        self.info = None  # 最近一次抓取的原始 JSON，用于作者/出处/命名

    def request_headers(self):
        return dict(_HEADERS)

    def get_image_url(self, nsfw_mode):
        raise NotImplementedError

    def get_artist(self):
        return None

    def get_link(self):
        return None

    def suggest_name(self, ext):
        return f"{self.id}_{int(time.time())}{_ext_suffix(ext)}"


class CatgirlSource(BaseSource):
    """nekos.moe"""

    id = "catgirl"
    name = "Catgirl"
    description = "nekos.moe"
    ENDPOINT = "https://nekos.moe/api/v1/random/image"

    def get_image_url(self, nsfw_mode):
        params = {}
        if nsfw_mode == ONLY_NSFW:
            params["nsfw"] = "true"
        elif nsfw_mode == BLOCK_NSFW:
            params["nsfw"] = "false"
        url = self.ENDPOINT
        if params:
            url += "?" + urllib.parse.urlencode(params)

        data = _get_json(url, timeout=10)
        self.info = data
        images = data.get("images") or []
        if not images:
            raise DownloaderError("nekos.moe 未返回图片")
        return "https://nekos.moe/image/" + images[0]["id"]

    def get_artist(self):
        try:
            return self.info["images"][0].get("artist")
        except (KeyError, IndexError, TypeError):
            return None

    def get_link(self):
        try:
            return "https://nekos.moe/post/" + self.info["images"][0]["id"]
        except (KeyError, IndexError, TypeError):
            return None

    def suggest_name(self, ext):
        try:
            image_id = self.info["images"][0]["id"]
        except (KeyError, IndexError, TypeError):
            image_id = str(int(time.time()))
        return f"nekos.moe_{image_id}{_ext_suffix(ext)}"


class WaifuSource(BaseSource):
    """waifu.im"""

    id = "waifu"
    name = "Waifu"
    description = "waifu.im"
    ENDPOINT = "https://api.waifu.im/images"

    def get_image_url(self, nsfw_mode):
        if nsfw_mode == ONLY_NSFW:
            isnsfw = "True"
        elif nsfw_mode == BLOCK_NSFW:
            isnsfw = "False"
        else:
            isnsfw = "All"

        url = self.ENDPOINT + "?" + urllib.parse.urlencode({"IsNsfw": isnsfw})
        data = _get_json(url, timeout=10)
        self.info = data
        items = data.get("items") or []
        if not items:
            raise DownloaderError("waifu.im 未返回图片")
        return items[0]["url"]

    def get_artist(self):
        try:
            artists = self.info["items"][0].get("artists") or []
            return artists[0].get("name") if artists else None
        except (KeyError, IndexError, TypeError):
            return None

    def get_link(self):
        try:
            return self.info["items"][0].get("source")
        except (KeyError, IndexError, TypeError):
            return None

    def suggest_name(self, ext):
        try:
            image_id = self.info["items"][0].get("id", "unknown")
        except (KeyError, IndexError, TypeError):
            image_id = str(int(time.time()))
        return f"waifu.im_{image_id}{_ext_suffix(ext)}"


class DanbooruSource(BaseSource):
    """danbooru.donmai.us，支持自定义标签。"""

    id = "danbooru"
    name = "Danbooru"
    description = "danbooru.donmai.us（可自定义标签）"
    ENDPOINT = "https://danbooru.donmai.us"
    MAX_RETRIES = 5

    def get_tags(self):
        raw = self.prefs.get("danbooru_tags", "") or ""
        return " ".join(t for t in raw.split() if t.lower() not in FORBIDDEN_TAGS)

    def _query_tags(self, nsfw_mode):
        if nsfw_mode == BLOCK_NSFW:
            rating = "rating:general"
        elif nsfw_mode == ONLY_NSFW:
            rating = "rating:explicit"
        else:
            rating = ""
        return " ".join(t for t in (self.get_tags(), rating) if t)

    def get_image_url(self, nsfw_mode):
        query = self._query_tags(nsfw_mode)
        last_err = None
        for _ in range(self.MAX_RETRIES):
            params = {"limit": 1, "random": "true"}
            if query:
                params["tags"] = query
            url = self.ENDPOINT + "/posts.json?" + urllib.parse.urlencode(params)
            try:
                data = _get_json(url, timeout=10)
            except DownloaderError as exc:
                last_err = exc
                continue
            if not isinstance(data, list) or not data:
                continue
            post = data[0]
            post_tags = {t.lower() for t in (post.get("tag_string") or "").split()}
            if post_tags & FORBIDDEN_TAGS:
                continue
            file_url = post.get("file_url")
            if not file_url:
                continue
            self.info = post
            return file_url
        detail = f"：{last_err}" if last_err else ""
        raise DownloaderError(f"danbooru 未找到合适的结果{detail}")

    def get_artist(self):
        try:
            artists = (self.info.get("tag_string_artist") or "").split()
            return artists[0] if artists else None
        except (AttributeError, TypeError):
            return None

    def get_link(self):
        try:
            post_id = self.info.get("id")
            return f"{self.ENDPOINT}/posts/{post_id}" if post_id else None
        except (AttributeError, TypeError):
            return None

    def suggest_name(self, ext):
        try:
            post_id = str(self.info.get("id") or int(time.time()))
        except (AttributeError, TypeError):
            post_id = str(int(time.time()))
        return f"danbooru_{post_id}{_ext_suffix(ext)}"


SOURCES = [CatgirlSource, WaifuSource, DanbooruSource]
