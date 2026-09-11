#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
附件下载工具
用于从CoreAlm系统下载需求相关的附件
支持两种下载方式：
1. 通过doc_id下载原始Word文档（推荐）
2. 通过URL直接下载（仅适用于可访问的文档链接）
"""

import os
import sys
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any

# 添加脚本目录到路径，以便导入single_file_downloader
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))


class AttachmentDownloader:
    """附件下载器"""

    def __init__(self, output_dir: str = "downloads"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def download_by_doc_id(self, doc_id: str, us_num: str = "") -> Optional[str]:
        """
        通过文档ID下载CoreAlm文档（推荐方式）

        Args:
            doc_id: CoreAlm文档ID
            us_num: 需求编号，用于命名文件

        Returns:
            保存的文件路径，失败返回None
        """
        try:
            # 导入single_file_downloader模块
            from single_file_downloader import SingleDownloader

            downloader = SingleDownloader()
            result = downloader.download_by_doc_id(doc_id, str(self.output_dir), us_num)

            if result.success:
                print(f"下载成功: {result.file_path}")
                return result.file_path
            else:
                print(f"下载失败: {result.error_message}")
                return None
        except Exception as e:
            print(f"通过doc_id下载失败: {str(e)}")
            return None

    def download_from_url(self, url: str, filename: str = None) -> Optional[str]:
        """
        从URL下载文件

        Args:
            url: 文件URL
            filename: 保存的文件名，默认使用URL中的文件名

        Returns:
            保存的文件路径，失败返回None
        """
        if not filename:
            # 从URL中提取文件名
            filename = url.split("/")[-1]
            # 处理查询参数
            if "?" in filename:
                filename = filename.split("?")[0]

        # 清理文件名
        filename = self._sanitize_filename(filename)
        output_path = self.output_dir / filename

        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()

            with open(output_path, "wb") as f:
                f.write(response.content)

            return str(output_path)
        except Exception as e:
            print(f"下载失败: {url}, 错误: {str(e)}")
            return None

    def download_from_doc_info(self, doc_info: List[Dict]) -> List[Dict[str, str]]:
        """
        从文档信息列表下载附件

        Args:
            doc_info: 文档信息列表，每个元素包含doc_url等字段

        Returns:
            下载结果列表，每个元素包含doc_id, doc_url, local_path
        """
        results = []

        for doc in doc_info:
            doc_id = doc.get("doc_id", "")
            doc_url = doc.get("doc_url", "")

            if not doc_url:
                continue

            # 根据doc_id生成文件名
            ext = self._get_extension_from_url(doc_url)
            filename = f"{doc_id}{ext}" if doc_id else None

            local_path = self.download_from_url(doc_url, filename)

            results.append({
                "doc_id": doc_id,
                "doc_url": doc_url,
                "local_path": local_path,
                "success": local_path is not None
            })

        return results

    def _sanitize_filename(self, filename: str) -> str:
        """
        清理文件名，移除非法字符
        """
        # 替换非法字符
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, "_")

        # 限制长度
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:200-len(ext)] + ext

        return filename

    def _get_extension_from_url(self, url: str) -> str:
        """
        从URL获取文件扩展名
        """
        # 常见文档类型
        extensions = {
            ".docx": [".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
            ".doc": [".doc", "application/msword"],
            ".pdf": [".pdf", "application/pdf"],
            ".xlsx": [".xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
            ".pptx": [".pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"],
        }

        # 从URL中提取
        url_lower = url.lower()
        for ext in extensions.keys():
            if ext in url_lower:
                return ext

        return ".docx"  # 默认


def download_attachments(requirement_id: str, doc_info: List[Dict], output_dir: str = "downloads") -> List[Dict[str, str]]:
    """
    下载需求相关附件的便捷函数

    Args:
        requirement_id: 需求ID
        doc_info: 文档信息列表
        output_dir: 输出目录

    Returns:
        下载结果列表
    """
    downloader = AttachmentDownloader(output_dir)
    return downloader.download_from_doc_info(doc_info)


def main():
    """测试入口"""
    import argparse

    parser = argparse.ArgumentParser(description="附件下载工具")
    # 方式1：通过doc_id下载（推荐）
    parser.add_argument("--doc-id", "-d", default=None, help="CoreAlm文档ID（推荐使用此参数）")
    parser.add_argument("--us-num", "-n", default="", help="需求编号，用于命名文件")
    # 方式2：通过URL下载（备用）
    parser.add_argument("--url", "-u", default=None, help="文件URL（备用方案）")
    parser.add_argument("--output", "-o", default="downloads", help="输出目录")
    parser.add_argument("--filename", "-f", default=None, help="保存的文件名")

    args = parser.parse_args()

    downloader = AttachmentDownloader(args.output)

    # 优先使用doc_id下载
    if args.doc_id:
        result = downloader.download_by_doc_id(args.doc_id, args.us_num)
    elif args.url:
        result = downloader.download_from_url(args.url, args.filename)
    else:
        print("错误：请提供 --doc-id 或 --url 参数")
        return

    if result:
        print(f"下载成功: {result}")
    else:
        print("下载失败")


if __name__ == "__main__":
    main()
