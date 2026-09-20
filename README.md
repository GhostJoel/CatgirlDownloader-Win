# Catgirl Downloader（Windows / Tkinter 版）

把 [NyarchLinux/CatgirlDownloader](https://github.com/NyarchLinux/CatgirlDownloader) 的功能
搬到 Windows 上：从 **nekos.moe / waifu.im / danbooru** 随机抓一张图，显示、保存、可定时自动刷新。

> 本项目是原项目的**非官方 Windows 移植版**，同样采用 **GPL-3.0** 许可，详见文末「许可证与致谢」。

- **界面**：Tkinter（Python 标准库自带，无需安装）
- **图片显示**：Pillow
- **网络**：标准库 `urllib`（不依赖 requests）
- **配置**：`%APPDATA%\CatgirlDownloader\config.json`
- **打包后**：约 18 MB 单文件 exe，Win10/11 免安装运行

## 运行

```powershell
python -m pip install -r requirements.txt
python app.py
```

## 功能

- 顶部选择**图源**（Catgirl / Waifu / Danbooru）与 **NSFW 模式**（Block / Only / Show everything）
- **刷新**：换一张；**保存**：把当前图片存到磁盘（默认文件名按图源自动生成）
- **自动刷新**：勾选后按设定秒数自动换图
- **设置**：Danbooru 自定义搜索标签（`shota` / `loli` 会被自动过滤）
- **关于**：显示版本、版权与 GPL 许可声明（满足 GPL 的「适当法律声明」要求）
- 状态栏显示图源、作者与出处链接

## 打包成 exe

双击 `build.bat`，或手动执行：

```powershell
python -m pip install pillow pyinstaller
python make_icon.py
python -m PyInstaller --onefile --windowed --icon "icon.ico" --add-data "icon.ico;." --name CatgirlDownloader app.py
```

产物在 `dist\CatgirlDownloader.exe`。

## 文件说明

| 文件 | 作用 |
|---|---|
| `app.py` | 界面与主流程（后台线程抓取，主线程刷新 UI） |
| `sources.py` | 三个图源的抓取逻辑 |
| `preferences.py` | 配置读写 |
| `make_icon.py` | 用系统 emoji 字体现渲染出 🐱 图标（`icon.ico` / `icon.png`） |
| `icon.ico` | 应用图标（已嵌入 exe，运行时窗口标题栏也用它） |
| `requirements.txt` | 运行时依赖（仅 Pillow） |
| `build.bat` | 打包脚本（会自动生成图标并嵌入） |

## 备注

- Tkinter 原生只能解码 PNG/GIF，JPG/WebP 靠 Pillow，所以 Pillow 不可省。
- danbooru 未登录时随机查询有较严格的频率限制，偶发失败会重试最多 5 次。
- 首次运行会自动生成配置文件。

## 许可证与致谢

- 本项目是 [NyarchLinux/CatgirlDownloader](https://github.com/NyarchLinux/CatgirlDownloader) 的**非官方 Windows 移植版**。
- 原项目及本项目均采用 **GNU GPL-3.0-or-later** 许可证，全文见 [LICENSE](LICENSE)。
- 版权：原项目 Copyright (C) 2026 SilverOS；移植部分 Copyright (C) 2026 MoRan。
- 依据 GPL-3.0，你可自由使用、修改、再分发本程序，但必须保留版权与许可声明，并以相同许可证发布衍生作品（含分发的 exe，需同时提供源码）。

## 免责声明

- 本程序仅从 nekos.moe / waifu.im / danbooru 等第三方站点抓取图片，图片版权归原作者及相应站点所有。
- 请遵守各图源的使用条款；请勿将下载的图片用于侵权用途或再分发。
