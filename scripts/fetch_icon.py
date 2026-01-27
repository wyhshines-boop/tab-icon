#!/usr/bin/env python3
"""
macosicons.com 图标爬取脚本
从 macosicons.com 搜索并下载图标的低分辨率预览图
使用标准库，无需额外依赖
"""

import urllib.request
import urllib.error
import json
import os
import ssl
from pathlib import Path

# 创建一个不验证 SSL 证书的上下文（仅用于演示目的）
# 在生产环境中建议正确配置 SSL 证书
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


def search_icon(query: str) -> dict | None:
    """
    搜索图标并返回第一个结果
    
    Args:
        query: 搜索关键词，如 'chatgpt'
        
    Returns:
        第一个搜索结果的信息，包含 lowResPngUrl 等字段
    """
    url = "https://api.macosicons.com/api/v1/search"
    
    payload = {
        "query": query,
        "searchOptions": {
            "filters": [],
            "hitsPerPage": 1,
            "sort": ["timeStamp:desc"],
            "page": 0
        },
        "apiKey": "m6CDglgxjbC14JOUlwzdl5Yjp2TCMvHJJfnT0H4L"
    }
    
    data = json.dumps(payload).encode('utf-8')
    
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Origin": "https://macosicons.com",
            "Referer": "https://macosicons.com/"
        },
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req, context=ssl_context) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            hits = result.get("hits", [])
            if hits:
                return hits[0]  # 返回第一个结果
            else:
                print(f"未找到 '{query}' 相关的图标")
                return None
                
    except urllib.error.HTTPError as e:
        print(f"HTTP 错误: {e.code} {e.reason}")
        try:
            error_body = e.read().decode('utf-8')
            print(f"错误详情: {error_body}")
        except:
            pass
        return None
    except urllib.error.URLError as e:
        print(f"搜索请求失败: {e}")
        return None


def download_icon(icon_url: str, save_path: str) -> bool:
    """
    下载图标文件
    
    Args:
        icon_url: 图标的 URL
        save_path: 保存路径
        
    Returns:
        是否下载成功
    """
    try:
        req = urllib.request.Request(
            icon_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )
        
        # 确保目录存在
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        
        with urllib.request.urlopen(req, context=ssl_context) as response:
            with open(save_path, 'wb') as f:
                f.write(response.read())
        
        print(f"图标已保存到: {save_path}")
        return True
        
    except urllib.error.URLError as e:
        print(f"下载失败: {e}")
        return False


def fetch_and_save_icon(query: str, save_dir: str = "./icons") -> str | None:
    """
    搜索并下载图标
    
    Args:
        query: 搜索关键词
        save_dir: 保存目录
        
    Returns:
        保存的文件路径，失败返回 None
    """
    print(f"正在搜索: {query}")
    
    # 搜索图标
    icon_info = search_icon(query)
    if not icon_info:
        return None
    
    # 获取低分辨率图片 URL
    low_res_url = icon_info.get("lowResPngUrl")
    if not low_res_url:
        print("未找到低分辨率图片 URL")
        return None
    
    print(f"图标名称: {icon_info.get('appName', 'Unknown')}")
    print(f"预览图 URL: {low_res_url}")
    
    # 生成保存路径
    app_name = icon_info.get("appName", query)
    # 清理文件名中的特殊字符
    safe_name = "".join(c for c in app_name if c.isalnum() or c in (' ', '-', '_')).strip()
    save_path = os.path.join(save_dir, f"{safe_name}.png")
    
    # 下载图标
    if download_icon(low_res_url, save_path):
        return save_path
    
    return None


import time
import random
import sys

# ... (Previous imports and functions remain the same)

def batch_fetch_icons(queries: list[str], save_dir: str = "./icons", delay_range: tuple[float, float] = (1.0, 3.0)):
    """
    批量搜索并下载图标，包含随机延迟以避免被反爬
    
    Args:
        queries: 搜索关键词列表
        save_dir: 保存目录
        delay_range: 随机延迟范围 (最小秒数, 最大秒数)
    """
    total = len(queries)
    print(f"开始批量下载 {total} 个图标...")
    
    success_count = 0
    for i, query in enumerate(queries, 1):
        print(f"\n[{i}/{total}] 处理: {query}")
        
        try:
            result = fetch_and_save_icon(query, save_dir)
            if result:
                success_count += 1
        except Exception as e:
            print(f"处理 {query} 时发生未知错误: {e}")
            
        # 如果不是最后一个，则进行随机延迟
        if i < total:
            delay = random.uniform(*delay_range)
            print(f"等待 {delay:.2f} 秒...")
            time.sleep(delay)
            
    print(f"\n批量处理完成! 成功: {success_count}/{total}")


# Demo 示例
if __name__ == "__main__":
    # 如果命令行有参数，则处理命令行参数
    if len(sys.argv) > 1:
        apps = sys.argv[1:]
        batch_fetch_icons(apps)
    else:
        # 默认演示列表
        demo_apps = ["bilibili", "chatgpt", "discord", "vscode"]
        print("未提供参数，运行演示列表:", demo_apps)
        batch_fetch_icons(demo_apps)

