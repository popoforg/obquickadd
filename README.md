# Obsidian QuickAdd (PyQt6)

一个基于 `PyQt6` 的快速写日记小工具。

## 功能

- 启动后窗口显示在屏幕中心
- 输入内容，点击 `发送` 追加到 Obsidian 今日日记
- 成功后显示悬浮提示 `发送成功`，2 秒自动消失
- 托盘（状态栏）图标常驻：点击图标显示窗口
- 窗口显示时，点击窗口外部区域自动隐藏
- 支持快捷键显示窗口
  - macOS: `Cmd+Shift+O`
  - Windows/Linux: `Ctrl+Alt+O`

## 依赖

```bash
pip3 install PyQt6 pynput
```

说明：
- `PyQt6` 是 GUI 必需依赖
- `pynput` 用于全局快捷键（应用未激活时也可唤出窗口）
- 如果未安装 `pynput`，程序仍可运行，但快捷键只在应用激活时生效

## 前提（ObsidianCLI）

本工具的“发送”能力基于 `ObsidianCLI`。

- 你必须能在终端直接执行 `obsidian` 命令
- `obsidian` 需要支持 `daily:append content=...` 子命令

可先用下面命令自检：

```bash
which obsidian
obsidian --help
```

## 在 Obsidian 中开启 ObsidianCLI（建议流程）

1. 打开 Obsidian，进入 `设置`。
2. 进入 `关于`。
3. 在 `命令行界面` 区域，勾选 `允许从命令行与 Obsidian 交互`。
4. 回到终端再次验证：

```bash
obsidian --help
obsidian daily:append content="CLI test"
```

如果第 4 步能成功执行，说明本工具的发送功能可以正常使用。

## 运行

```bash
cd /Users/rb/Desktop/temp/obquickadd
python3 quick_add_gui.py
```

## 默认命令

程序内部固定使用：

```text
obsidian daily:append content=__CONTENT__
```

如果 `obsidian` 命令不可用或不支持 `daily:append`，发送会失败。
