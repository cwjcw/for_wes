# for_wes

用于批量打开网页链接并触发数据导出的自动化脚本。

## 环境准备
- 安装 Python 3.10 或更高版本。
- 建议使用虚拟环境（例如 `python -m venv .venv && source .venv/bin/activate`）。
- 安装依赖：`pip install -r requirements.txt`。
- 需要在本机安装 Chrome 浏览器；脚本会在运行时下载匹配版本的 `chromedriver`。

## 配置
运行前请根据目标网页编辑根目录中的 `automation_config.json`。关键字段说明：
- `start_url`：登录后需要访问的入口页面。
- `link_items_selector`：左侧列表中链接元素的 CSS 选择器。
- `export_button`：导出按钮的定位方式，支持 `css`、`xpath`、`id` 等。
- `wait_after_link_seconds`：点击链接后等待内容加载的秒数（默认 10 秒）。
- `navigate_back_after_export`：如果导出会跳转到其它页面，设置为 `true` 会在导出后回退。
- `download_directory`：下载文件保存目录（默认 `./downloads`），可在打包后继续修改。

如需重新生成配置，可复制 `automation_config.example.json` 并修改。

## 运行脚本
```
python automation.py
```
脚本会依次点击未处理的链接，等待内容加载，找到导出按钮并点击，直至全部链接处理完毕。

## 生成免安装 EXE
1. 确保依赖已安装并且 `automation_config.json` 就绪。
2. 执行：
   ```
   pyinstaller --onefile --name link_exporter automation.py
   ```
3. 生成的可执行文件位于 `dist/link_exporter.exe`。将 `automation_config.json` 放在同一目录下，该文件可以在打包后继续修改，程序运行时会读取最新内容。

如需自定义下载目录或其它参数，只需编辑配置文件并重新运行 exe，无需重新打包。
