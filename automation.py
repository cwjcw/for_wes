"""
Automation script that iterates through a list of links on a web page, waits for
each linked view to load, and triggers a data export action. Configuration is
loaded from `automation_config.json`, enabling post-build adjustments when the
script is packaged as an executable.
"""

from __future__ import annotations

import json
import sys
import time
from contextlib import suppress
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence, Tuple

from selenium import webdriver
from selenium.common.exceptions import JavascriptException, TimeoutException, WebDriverException
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


CONFIG_FILENAME = "automation_config.json"
DEFAULT_TIMEOUT = 30
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_REQUEST_HEADERS = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}


def main() -> None:
    config = load_config()
    driver, download_dir = build_driver(config)

    try:
        run_automation(driver, download_dir, config)
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"[ERROR] Automation failed: {exc}", file=sys.stderr)
        raise
    finally:
        with suppress(Exception):
            driver.quit()


def run_automation(driver: webdriver.Chrome, download_dir: Path, config: Dict) -> None:
    start_url: str = config["start_url"]
    link_selector: str = config["link_items_selector"]
    export_button_config: Dict = config["export_button"]
    target_texts = normalize_target_texts(config.get("link_text_targets"))

    print(f"[INFO] Opening start URL: {start_url}")
    driver.get(start_url)

    wait_for_page_ready(driver, config.get("page_ready_timeout", DEFAULT_TIMEOUT))

    wait_after_link = config.get("wait_after_link_seconds", 10)
    export_timeout = config.get("export_click_timeout_seconds", DEFAULT_TIMEOUT)
    back_after_export = config.get("navigate_back_after_export", False)
    download_wait = config.get("download_wait_timeout_seconds", 60)

    visited_labels = set()
    iteration = 0

    while True:
        iteration += 1
        print(f"[DEBUG] Iteration {iteration}: scanning for remaining links.")
        link_elements = collect_link_elements(driver, link_selector)

        next_item = pick_next_link(link_elements, visited_labels, target_texts)
        if next_item is None:
            print("[INFO] No more links to process. Automation complete.")
            break

        element, label = next_item
        print(f"[INFO] Processing link: {label!r}")

        click_element(driver, element, label)
        visited_labels.add(label)

        if wait_after_link > 0:
            print(f"[DEBUG] Waiting {wait_after_link} seconds for content to load.")
            time.sleep(wait_after_link)

        trigger_export(driver, export_button_config, export_timeout, label)

        if download_wait > 0:
            wait_for_downloads(download_dir, download_wait)

        if back_after_export:
            print("[DEBUG] Navigating back to the link list view.")
            driver.back()
            wait_for_page_ready(driver, config.get("page_ready_timeout", DEFAULT_TIMEOUT))


def load_config() -> Dict:
    config_path = resolve_working_path(CONFIG_FILENAME)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found at {config_path}. "
            "Create it by copying automation_config.example.json."
        )

    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    required = ("start_url", "link_items_selector", "export_button")
    missing = [key for key in required if key not in config]
    if missing:
        raise KeyError(f"Missing configuration keys: {', '.join(missing)}")

    return config


def build_driver(config: Dict) -> Tuple[webdriver.Chrome, Path]:
    download_dir = config.get("download_directory", "downloads")
    download_dir_path = resolve_working_path(download_dir)
    download_dir_path.mkdir(parents=True, exist_ok=True)

    print(f"[DEBUG] Downloads will be saved to: {download_dir_path}")

    options = ChromeOptions()
    if config.get("headless", False):
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    user_agent = config.get("user_agent", DEFAULT_USER_AGENT)
    if user_agent:
        options.add_argument(f"--user-agent={user_agent}")
    binary_path = config.get("chrome_binary_path")
    if binary_path:
        options.binary_location = binary_path

    prefs = {
        "download.default_directory": str(download_dir_path),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }
    options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=options,
    )

    setup_request_headers(driver, config, user_agent)

    page_timeout = config.get("page_load_timeout_seconds")
    if page_timeout:
        driver.set_page_load_timeout(page_timeout)

    return driver, download_dir_path


def wait_for_page_ready(driver: webdriver.Chrome, timeout: int) -> None:
    """Wait until document.readyState becomes 'complete'."""
    def is_ready(drv: webdriver.Chrome) -> bool:
        try:
            return drv.execute_script("return document.readyState") == "complete"
        except JavascriptException:
            return False

    WebDriverWait(driver, timeout).until(is_ready)


def collect_link_elements(driver: webdriver.Chrome, selector: str) -> Iterable[WebElement]:
    return WebDriverWait(driver, DEFAULT_TIMEOUT).until(
        lambda drv: drv.find_elements(By.CSS_SELECTOR, selector)
    )


def pick_next_link(
    candidates: Iterable[WebElement],
    visited_labels: set,
    target_texts: Optional[Sequence[str]] = None,
) -> Optional[Tuple[WebElement, str]]:
    available: list[Tuple[WebElement, str]] = []
    for element in candidates:
        try:
            label = extract_label(element)
        except StaleElementReferenceException:
            continue

        available.append((element, label))

    if not available:
        return None

    if target_texts:
        for target in target_texts:
            if target in visited_labels:
                continue
            for element, label in available:
                if label == target:
                    return element, label
        return None

    for element, label in available:
        if label in visited_labels:
            continue
        return element, label

    return None


def extract_label(element: WebElement) -> str:
    text = element.text.strip()
    if text:
        return text

    href = element.get_attribute("href")
    if href:
        return href

    data_id = element.get_attribute("data-id")
    if data_id:
        return data_id

    tag_name = element.tag_name or "link"
    return f"{tag_name}-{id(element)}"


def click_element(driver: webdriver.Chrome, element: WebElement, label: str) -> None:
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    try:
        element.click()
    except (WebDriverException, Exception):
        print(f"[DEBUG] Falling back to JavaScript click for {label!r}.")
        driver.execute_script("arguments[0].click();", element)


def trigger_export(
    driver: webdriver.Chrome,
    locator_config: Dict,
    timeout: int,
    link_label: str,
) -> None:
    by = locator_config.get("by", "css").lower()
    value = locator_config["value"]
    locator = (map_by(by), value)

    print(f"[INFO] Waiting for export button ({by}='{value}') on {link_label!r}.")
    button = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable(locator)
    )
    button.click()
    print(f"[INFO] Export triggered for {link_label!r}.")


def wait_for_downloads(target_dir: Path, timeout: int) -> None:
    """Block until Chrome completes pending downloads (.crdownload files gone)."""
    deadline = time.time() + timeout

    while time.time() < deadline:
        if not any(target_dir.glob("*.crdownload")):
            return
        time.sleep(1)

    raise TimeoutException(
        f"Downloads did not finish within {timeout} seconds in {target_dir}."
    )


def map_by(by_value: str) -> str:
    mapping = {
        "css": By.CSS_SELECTOR,
        "css_selector": By.CSS_SELECTOR,
        "xpath": By.XPATH,
        "id": By.ID,
        "name": By.NAME,
        "class": By.CLASS_NAME,
        "class_name": By.CLASS_NAME,
        "tag": By.TAG_NAME,
        "tag_name": By.TAG_NAME,
        "link_text": By.LINK_TEXT,
        "partial_link_text": By.PARTIAL_LINK_TEXT,
    }
    if by_value not in mapping:
        raise ValueError(f"Unsupported locator type: {by_value}")
    return mapping[by_value]


def resolve_working_path(relative_path: str) -> Path:
    base = (
        Path(sys.executable).parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent
    )
    return (base / relative_path).resolve()


def setup_request_headers(driver: webdriver.Chrome, config: Dict, user_agent: Optional[str]) -> None:
    """Register standard request headers via Chrome DevTools Protocol."""
    headers = dict(DEFAULT_REQUEST_HEADERS)
    if user_agent:
        headers["User-Agent"] = user_agent

    extra_headers = config.get("request_headers")
    if isinstance(extra_headers, dict):
        headers.update({str(k): str(v) for k, v in extra_headers.items() if v is not None})

    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd("Network.setExtraHTTPHeaders", {"headers": headers})
        print("[DEBUG] Applied custom HTTP headers to browser session.")
    except WebDriverException as exc:
        print(f"[WARN] Failed to configure extra HTTP headers: {exc}")


def normalize_target_texts(raw: Optional[Sequence]) -> Optional[list[str]]:
    if not raw:
        return None
    cleaned = [str(item).strip() for item in raw if str(item).strip()]
    return cleaned or None


if __name__ == "__main__":
    main()
