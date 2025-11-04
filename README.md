# for_wes

本项目提供一个基于 Selenium 的自动化脚本，实现以下流程：
1. 打开目标网页的入口页；
2. 扫描页面左侧的链接列表；
3. 逐个点击每个链接，等待页面加载；
4. 定位并点击页面中的“导出数据”按钮；
5. 等待下载完成后继续处理下一个链接；
6. 全部链接处理完毕后退出。

脚本支持通过 JSON 配置调整参数，并可打包成免安装的 Windows 可执行文件。

## 环境准备
- 安装 Python 3.10 或更新版本；
- 建议创建虚拟环境：`python -m venv .venv`，随后激活虚拟环境 Linux使用`source .venv/bin/activate`（Windows 使用 `.venv\Scripts\activate`）；
- 安装依赖：`pip install -r requirements.txt`；
- 确保本机安装了 Chrome 浏览器，脚本会自动下载匹配版本的 `chromedriver`。

## 配置文件
首次使用请复制根目录下的 `automation_config.example.json` 为 `automation_config.json`，然后按实际情况修改：
- `start_url`：自动化开始访问的页面地址（通常为登录后的入口页）；
- `link_items_selector`：左侧链接列表的 CSS 选择器，脚本会依据该选择器收集所有链接。使用步骤：  
  1. 打开目标网页并按 `F12` 调出开发者工具；  
  2. 使用“选择元素”工具点击任意一个左侧目录链接；  
  3. 观察其 `class`、`id` 或父容器结构，写出能覆盖所有目标链接的 CSS 选择器（示例：`#sidebar a.menu-link`、`.nav-tree li > a`）；  
  4. 在浏览器控制台执行 `document.querySelectorAll('选择器')`，确认返回数量与实际链接一致；  
  5. 将该选择器字符串填入配置文件。没有可视化列表可供勾选，需要手动写选择器。
- `link_text_targets`：可选数组，按顺序列出需要点击的链接文本；如果提供，脚本只会按照这些文本顺序寻找并点击对应链接（文本需与页面显示完全一致）。示例：
  ```json
  "link_text_targets": [
    "五月报表",
    "六月报表",
    "年度汇总"
  ]
  ```
  若留空，脚本默认对 `link_items_selector` 匹配到的所有链接按扫描顺序依次处理。
- `export_button.by` / `export_button.value`：导出按钮的定位方式与值，可选 `css`、`xpath`、`id`、`name` 等；同样在开发者工具中检查导出按钮标签，复制稳定的选择器或 XPath，尽量使用固定的 `id`、`data-*` 属性等不易变的特征。
- `wait_after_link_seconds`：点击链接后等待内容加载的时间，默认 10 秒，可根据页面速度调整；
- `download_directory`：导出文件保存目录，默认是脚本目录下的 `downloads` 文件夹；
- `navigate_back_after_export`：某些站点导出后会跳转到其他页面，设为 `true` 时会尝试自动返回上一页；
- `user_agent`：自定义浏览器 UA，脚本默认使用最新 Chrome 的 user agent；
- `chrome_binary_path`：如使用便携版 Chromium，可在此填写其可执行文件路径（例如 `C:\\tools\\chromium\\chrome.exe`），否则留空；
- `request_headers`：额外的 HTTP 请求头（例如 `Accept-Language`、`Cache-Control`），会与脚本内置的标准请求头合并后一起发送；
- 其他字段（如 `headless`、`page_ready_timeout`、`download_wait_timeout_seconds` 等）用于控制无头模式、页面加载超时与下载等待时间。

> 提示：开发阶段建议使用非无头模式，方便观察执行过程；上线后可在配置里把 `headless` 设为 `true`。

## 运行自动化
1. 打开终端并进入项目根目录；
2. （可选）先登录目标网站，以便脚本启动后保持登录状态；
3. 执行 `python automation.py`；
4. 若页面需要验证码或二次认证，可在脚本打开的浏览器窗口中手动完成，然后继续等待脚本运行；
5. 脚本会依照 `link_text_targets`（若配置）或页面扫描顺序处理链接，期间会在终端打印进度信息；
6. 全部链接完成后，浏览器自动关闭，程序退出。

导出的文件默认保存在 `downloads` 文件夹，建议定期清理旧数据以便区分最新导出结果。脚本会通过 Chrome DevTools 协议注入标准请求头，以减少被反爬机制识别的风险；如需特殊头部可在配置中追加。

### 无法安装 Chrome 的替代方案（Chromium 便携版）
- 访问 Google 官方维护的 Chromium 自动构建站点：`https://download-chromium.appspot.com/`。
- 选择 `Win` 平台下载最新构建的 ZIP 包，并解压到如 `C:\tools\chromium\`。
- 在 `automation_config.json` 的 `chrome_binary_path` 中填写解压后的 `chrome.exe` 路径（例如 `C:\\tools\\chromium\\chrome.exe`）；脚本会自动读取并设置到 Selenium 的 `binary_location`。
- 若需要无头模式，可同时在配置文件中将 `headless` 设为 `true`。

## 打包为免安装 EXE
1. 确认脚本已在当前环境下运行正常；
2. 在项目根目录执行：
   ```bash
   pyinstaller --onefile --name link_exporter automation.py
   ```
3. 打包完成后，可执行文件位于 `dist/link_exporter.exe`；
4. 将 `automation_config.json` 与 `link_exporter.exe` 放在同一目录。日后若需要调整参数，只需修改配置文件，无需重新打包。

## 常见问题
- **启动即报错或浏览器无法打开**：请确认 Chrome 已安装且版本较新；必要时手动删除 `~/.wdm` 下的驱动缓存，让程序重新下载。
- **无法定位链接或按钮**：检查 CSS/XPath 是否正确，可在浏览器按 `F12` 使用开发者工具验证选择器。
- **下载超时**：调高 `download_wait_timeout_seconds`，或确认网络/站点是否正常；必要时延长 `wait_after_link_seconds`。
- **需要自动登录**：当前脚本未内置登录逻辑，如需自动登录，可在 `automation.py` 中自定义扩展（例如使用表单填写、Cookies 等方式）。

如需扩展功能或遇到其他问题，欢迎在此脚本基础上继续开发。使用过程中请遵守目标网站的使用条款和数据导出政策。
