# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 MoRan
#
# CatgirlDownloader —— Windows 移植版 (Tkinter) 新增文件
# 基于 NyarchLinux/CatgirlDownloader 移植：
#   原项目 Copyright (C) 2026 SilverOS，许可证 GPL-3.0-or-later
#   https://github.com/NyarchLinux/CatgirlDownloader
# 修改日期 2026-09-20：新增图标生成脚本。

"""生成 🐱 应用图标：icon.ico（多尺寸）与 icon.png。

用 Windows 自带的 Segoe UI Emoji 彩色字体渲染，无需联网、无需额外素材。
改图标只需改 EMOJI 再重新运行本脚本。
"""

from PIL import Image, ImageDraw, ImageFont

EMOJI = "\U0001F431"  # 🐱
FONT_PATH = r"C:\Windows\Fonts\seguiemj.ttf"
SIZES = [16, 24, 32, 48, 64, 128, 256]
PAD_RATIO = 0.06  # 四周留白比例


def render_glyph(px=512):
    """把 emoji 渲染成一张大图并裁到内容边界。"""
    font = ImageFont.truetype(FONT_PATH, px)
    img = Image.new("RGBA", (px * 2, px * 2), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((px // 2, px // 2), EMOJI, font=font, embedded_color=True)
    return img.crop(img.getbbox())


def fit(glyph, size):
    """把字形等比缩放并居中放进 size×size 的透明画布。"""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    inner = max(1, int(size * (1 - 2 * PAD_RATIO)))
    g = glyph.copy()
    g.thumbnail((inner, inner), Image.LANCZOS)
    canvas.paste(g, ((size - g.width) // 2, (size - g.height) // 2), g)
    return canvas


def main():
    glyph = render_glyph()
    fit(glyph, max(SIZES)).save("icon.png")
    fit(glyph, 256).save("icon.ico", sizes=[(s, s) for s in SIZES])
    print("已生成 icon.ico / icon.png，尺寸:", SIZES)


if __name__ == "__main__":
    main()
