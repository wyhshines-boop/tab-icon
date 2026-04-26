#!/usr/bin/env python3
"""
macosicons.com 图标批量抓取脚本

默认从 config/presets.json 读取预设站点，搜索并下载图标到 icons/，
下载成功后会同步更新 presets.json 中的 iconKey，以及 mapping.json 中
对应域名的映射。
"""

from __future__ import annotations

import argparse
import json
import random
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
PRESETS_PATH = ROOT_DIR / "config" / "presets.json"
MAPPING_PATH = ROOT_DIR / "config" / "mapping.json"
ICONS_DIR = ROOT_DIR / "icons"
SEARCH_BASE_URL = "https://beta.macosicons.com"

# 当前仓库已经存在的文件名和项目显示名并不总是一致，这里显式做一层对齐。
KNOWN_ICON_KEYS = {
    "ChatGPT": "chatgpt",
    "Discord": "Discord",
    "Spotify": "Spotify",
    "VS Code": "vscode",
    "X": "X",
    "GitHub": "github",
    "哔哩哔哩": "bilibili",
    "知乎": "zhihu",
}

QUERY_OVERRIDES = {
    "Google Drive": ["google drive"],
    "Google Maps": ["google maps"],
    "Gmail": ["gmail"],
    "YouTube": ["youtube"],
    "Squoosh": ["squoosh"],
    "iLovePDF": ["ilovepdf"],
    "Smallpdf": ["smallpdf"],
    "CloudConvert": ["cloudconvert"],
    "Convertio": ["convertio"],
    "remove.bg": ["remove bg", "remove.bg"],
    "TinyPNG": ["tinypng", "tiny png"],
    "Photopea": ["photopea"],
    "Excalidraw": ["excalidraw"],
    "Canva": ["canva"],
    "WeTransfer": ["wetransfer"],
    "Pixeldrain": ["pixeldrain"],
    "Temp Mail": ["temp mail"],
    "在线音频转换": ["audio convert", "audio converter"],
    "PDF24 Tools": ["pdf24"],
    "123Apps 视频剪辑": ["123apps", "online video cutter"],
    "Clipdrop": ["clipdrop"],
    "DocHub": ["dochub"],
    "Canva Docs": ["canva"],
    "知乎": ["zhihu"],
    "Reddit": ["reddit"],
    "Google": ["google"],
    "Notion": ["notion"],
    "Figma": ["figma"],
}


ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        f.write("\n")


def domain_from_url(url: str) -> str:
    netloc = urllib.parse.urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def sanitize_icon_key(name: str) -> str:
    cleaned = []
    for char in name.strip():
        if char.isalnum():
            cleaned.append(char.lower())
        elif char in {" ", "-", "_", "."}:
            cleaned.append("-")

    key = "".join(cleaned).strip("-")
    while "--" in key:
        key = key.replace("--", "-")
    return key


def normalize_for_match(text: str) -> str:
    return "".join(char.lower() for char in text if char.isalnum())


def build_search_queries(title: str, url: str) -> list[str]:
    queries: list[str] = []
    seen: set[str] = set()

    def add(query: str) -> None:
        q = query.strip()
        normalized = q.lower()
        if q and normalized not in seen:
            seen.add(normalized)
            queries.append(q)

    for query in QUERY_OVERRIDES.get(title, []):
        add(query)

    add(title)

    domain = domain_from_url(url)
    add(domain.split(".")[0])

    host_parts = [part for part in domain.split(".") if part not in {"com", "org", "net", "app", "co", "io"}]
    if host_parts:
        add(" ".join(host_parts))

    return queries


def search_icon(query: str, hits_per_page: int = 5) -> list[dict]:
    url = f"{SEARCH_BASE_URL}/api/search"
    payload = {
        "query": query,
        "searchOptions": {
            "filters": [],
            "hitsPerPage": hits_per_page,
            "sort": ["timeStamp:desc"],
            "page": 1,
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": SEARCH_BASE_URL,
        },
        method="POST",
    )

    with urllib.request.urlopen(req, context=ssl_context) as response:
        result = json.loads(response.read().decode("utf-8"))
    return result.get("hits", [])


def pick_best_hit(hits: list[dict], query: str, title: str) -> dict | None:
    if not hits:
        return None

    query_n = normalize_for_match(query)
    title_n = normalize_for_match(title)

    def score(hit: dict) -> tuple[int, int]:
        app_name = str(hit.get("appName", ""))
        app_name_n = normalize_for_match(app_name)
        low_res_url = str(hit.get("lowResPngUrl", ""))
        score_value = 0
        matched = False

        if app_name_n == title_n and title_n:
            score_value += 6
            matched = True
        if app_name_n == query_n and query_n:
            score_value += 5
            matched = True
        if title_n and title_n in app_name_n:
            score_value += 4
            matched = True
        if query_n and query_n in app_name_n:
            score_value += 3
            matched = True
        if low_res_url.startswith("https://s3.macosicons.com/"):
            score_value += 2
        if "parsefiles.back4app.com" in low_res_url:
            score_value -= 4
        if hit.get("lowResPngUrl"):
            score_value += 1
        if not matched:
            score_value = -999
        return (score_value, -len(app_name_n))

    ranked = sorted(hits, key=score, reverse=True)
    chosen = ranked[0]
    if score(chosen)[0] < 0 or not chosen.get("lowResPngUrl"):
        return None
    return chosen


def download_icon(icon_url: str, save_path: Path) -> bool:
    parsed = urllib.parse.urlsplit(icon_url)
    normalized_url = urllib.parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            urllib.parse.quote(parsed.path),
            parsed.query,
            parsed.fragment,
        )
    )
    save_path.parent.mkdir(parents=True, exist_ok=True)
    last_error = None

    for attempt in range(3):
        req = urllib.request.Request(
            normalized_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": SEARCH_BASE_URL,
            },
        )
        try:
            with urllib.request.urlopen(req, context=ssl_context) as response:
                save_path.write_bytes(response.read())
            return True
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < 2:
                time.sleep(0.5)

    if last_error:
        raise last_error
    return False


def resolve_existing_icon_key(preset: dict) -> str | None:
    return KNOWN_ICON_KEYS.get(preset.get("title", "")) or preset.get("iconKey")


def collect_targets(presets: list[dict], include_existing: bool) -> list[dict]:
    targets = []
    for preset in presets:
        if include_existing or not resolve_existing_icon_key(preset):
            targets.append(preset)
    return targets


def update_mapping(mapping: dict, preset: dict, icon_key: str) -> None:
    parsed = urllib.parse.urlparse(preset["url"])
    host = parsed.netloc.lower()
    bare_host = host[4:] if host.startswith("www.") else host

    # mapping.json 只按域名映射，像 Canva / Canva Docs 这种同域不同路径的条目
    # 需要优先保留更通用的主站图标，避免后续被子页面覆盖。
    if bare_host == "canva.com" and preset["title"] == "Canva Docs":
        return

    mapping[host] = icon_key
    mapping[bare_host] = icon_key
    mapping[f"www.{bare_host}"] = icon_key


def process_preset(
    preset: dict,
    mapping: dict,
    delay_range: tuple[float, float],
    overwrite: bool,
) -> bool:
    title = preset["title"]
    queries = build_search_queries(title, preset["url"])
    target_icon_key = resolve_existing_icon_key(preset) or sanitize_icon_key(title)
    target_path = ICONS_DIR / f"{target_icon_key}.png"

    if target_path.exists() and not overwrite:
        preset["iconKey"] = target_icon_key
        update_mapping(mapping, preset, target_icon_key)
        print(f"[skip] {title}: 已存在 {target_path.name}")
        return True

    print(f"[search] {title}")
    print(f"         queries: {', '.join(queries)}")

    chosen_hit = None
    chosen_query = None
    for query in queries:
        try:
            hits = search_icon(query)
        except urllib.error.HTTPError as exc:
            print(f"[error] {title}: 搜索失败 HTTP {exc.code} {exc.reason}")
            continue
        except urllib.error.URLError as exc:
            print(f"[error] {title}: 搜索失败 {exc}")
            continue

        chosen_hit = pick_best_hit(hits, query, title)
        if chosen_hit:
            chosen_query = query
            break

        delay = random.uniform(*delay_range)
        time.sleep(delay)

    if not chosen_hit:
        print(f"[miss] {title}: 未找到合适图标")
        return False

    icon_url = chosen_hit["lowResPngUrl"]
    app_name = chosen_hit.get("appName", "Unknown")
    print(f"[hit]  {title}: {app_name} <- {chosen_query}")

    try:
        download_icon(icon_url, target_path)
    except urllib.error.URLError as exc:
        print(f"[error] {title}: 下载失败 {exc}")
        return False

    preset["iconKey"] = target_icon_key
    update_mapping(mapping, preset, target_icon_key)
    print(f"[save] {target_path.relative_to(ROOT_DIR)}")
    return True


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量抓取 presets.json 对应网站图标")
    parser.add_argument(
        "--titles",
        nargs="+",
        help="只处理指定标题的预设项，例如 --titles Squoosh TinyPNG",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="包含已有 iconKey 的条目一起处理",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="即使目标文件已存在也重新下载",
    )
    parser.add_argument(
        "--min-delay",
        type=float,
        default=0.8,
        help="两次搜索之间的最小延迟，默认 0.8 秒",
    )
    parser.add_argument(
        "--max-delay",
        type=float,
        default=1.8,
        help="两次搜索之间的最大延迟，默认 1.8 秒",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印将要处理的目标，不下载不写文件",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    presets = load_json(PRESETS_PATH)
    mapping = load_json(MAPPING_PATH)

    targets = collect_targets(presets, include_existing=args.all)
    if args.titles:
        wanted = set(args.titles)
        targets = [preset for preset in targets if preset["title"] in wanted]

    if not targets:
        print("没有需要处理的目标。")
        return 0

    print(f"准备处理 {len(targets)} 个站点")
    for preset in targets:
        existing_key = resolve_existing_icon_key(preset)
        status = existing_key or "missing"
        print(f"- {preset['title']} [{status}]")

    if args.dry_run:
        return 0

    success = 0
    delay_range = (args.min_delay, args.max_delay)
    for index, preset in enumerate(targets, start=1):
        print(f"\n[{index}/{len(targets)}] {preset['title']}")
        if process_preset(
            preset,
            mapping,
            delay_range=delay_range,
            overwrite=args.overwrite,
        ):
            success += 1
        if index < len(targets):
            time.sleep(random.uniform(*delay_range))

    save_json(PRESETS_PATH, presets)
    save_json(MAPPING_PATH, mapping)

    print(f"\n完成: {success}/{len(targets)} 成功")
    return 0 if success == len(targets) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
