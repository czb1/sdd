#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单文件下载脚本
调用后端接口实现文档下载功能

接口说明:
1. /file-download/get-flow-id - 给定docId，返回flowId
2. /file-download/poll-export-status - 利用flowId轮询是否完成导出，完成后返回下载链接
3. /file-download/get-cookie - 获取登录Cookie，用于下载文件
"""

import sys
import os
import time
import requests
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from requests.adapters import HTTPAdapter
from urllib3 import Retry
import urllib3

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# 后端服务配置 - 通过环境变量配置
BACKEND_HOST = os.getenv("BACKEND_HOST", "https://coreinsight.rnd.huawei.com/chat")


class DownloadConfig:
    """下载配置类"""
    # 后端API基础URL
    BASE_URL = BACKEND_HOST

    # API端点
    GET_FLOW_ID_URL = f"{BASE_URL}/file-download/get-flow-id"
    POLL_EXPORT_STATUS_URL = f"{BASE_URL}/file-download/poll-export-status"
    GET_COOKIE_URL = f"{BASE_URL}/file-download/get-cookie"

    # 默认参数
    DEFAULT_USERNAME = "test_name"
    MAX_DOWNLOAD_RETRIES = 60
    RETRY_INTERVAL = 5
    DOWNLOAD_TIMEOUT = 60


@dataclass
class DownloadResult:
    """下载结果数据类"""
    success: bool
    download_url: Optional[str] = None
    error_message: Optional[str] = None
    file_path: Optional[str] = None


def create_session() -> requests.Session:
    """创建一个request会话"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


class SingleDownloader:
    """单文件下载器 - 调用后端接口实现"""

    def __init__(self):
        """初始化下载器"""
        self.config = DownloadConfig()
        self.session = create_session()

    def get_flow_id(self, doc_id: str) -> Optional[str]:
        """
        获取文档处理的flow_id

        Args:
            doc_id: 文档ID

        Returns:
            flow_id字符串，失败返回None
        """
        try:
            response = self.session.post(
                self.config.GET_FLOW_ID_URL,
                json={"doc_id": doc_id},
                timeout=30,
                verify=False
            )
            response.raise_for_status()

            result = response.json()
            if result.get("code") == 200:
                data = result.get("data", {})
                flow_id = data.get("flow_id")
                return flow_id
            else:
                print(f"获取flow_id失败: {result.get('message')}")
                return None

        except requests.RequestException as e:
            print(f"请求失败: {str(e)}")
            return None

    def poll_export_status(self, doc_id: str, flow_id: str,
                          max_retries: int = None,
                          retry_interval: int = None) -> Optional[str]:
        """
        轮询获取导出状态，完成后返回下载链接

        Args:
            doc_id: 文档ID
            flow_id: 流程ID
            max_retries: 最大重试次数
            retry_interval: 重试间隔(秒)

        Returns:
            下载URL，失败返回None
        """
        max_retries = max_retries or self.config.MAX_DOWNLOAD_RETRIES
        retry_interval = retry_interval or self.config.RETRY_INTERVAL

        try:
            response = self.session.post(
                self.config.POLL_EXPORT_STATUS_URL,
                json={
                    "doc_id": doc_id,
                    "flow_id": flow_id,
                    "max_retries": max_retries,
                    "retry_interval": retry_interval
                },
                timeout=max_retries * (retry_interval + 30),
                verify=False
            )
            response.raise_for_status()

            result = response.json()
            if result.get("code") == 200:
                data = result.get("data", {})
                if data.get("completed"):
                    return data.get("download_url")
            return None

        except requests.RequestException as e:
            print(f"请求失败: {str(e)}")
            return None

    def get_cookie(self) -> Optional[dict]:
        """
        获取登录Cookie

        Returns:
            Cookie字典，失败返回None
        """
        try:
            response = self.session.post(
                self.config.GET_COOKIE_URL,
                json={},
                timeout=30,
                verify=False
            )
            response.raise_for_status()

            result = response.json()
            if result.get("code") == 200:
                data = result.get("data", {})
                cookies = data.get("cookies")
                return cookies
            else:
                print(f"获取Cookie失败: {result.get('message')}")
                return None

        except requests.RequestException as e:
            print(f"请求失败: {str(e)}")
            return None

    def download_single_file(self, download_url: str, output_dir: str, doc_name: str = None) -> bool:
        """
        实际下载文件

        Args:
            download_url: 下载URL
            output_dir: 输出目录
            doc_name: 文档名称（如果为None，将从URL提取）

        Returns:
            下载成功返回True，失败返回False
        """
        if not download_url:
            print("没有提供下载URL")
            return False

        try:
            # 创建输出目录
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            # 如果没有提供文档名称，从URL中提取
            if not doc_name:
                import urllib.parse
                parsed_url = urllib.parse.urlparse(download_url)
                path_parts = parsed_url.path.split('/')
                filename = path_parts[-1] if path_parts[-1] else "document"
                filename = filename.split('?')[0]
            else:
                filename = doc_name

            # 确保以.docx结尾
            if not filename.lower().endswith('.docx'):
                filename += '.docx'

            output_file = output_path / filename

            print(f"开始下载文件: {filename}")
            print(f"保存到: {output_file}")

            # 获取Cookie
            cookies = self.get_cookie()
            if not cookies:
                print("无法获取Cookie，下载可能失败")

            # 下载文档
            response = self.session.get(
                download_url,
                cookies=cookies,
                verify=False,
                stream=True,
                timeout=self.config.DOWNLOAD_TIMEOUT
            )
            response.raise_for_status()

            with open(output_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            return True

        except requests.RequestException as e:
            print(f"下载失败: {str(e)}")
            return False
        except Exception as e:
            print(f"保存文件失败: {str(e)}")
            return False

    def download_by_doc_id(self, doc_id: str, us_num: str, output_dir: str = "./downloads") -> DownloadResult:
        """
        通过doc_id下载文档的完整流程

        Args:
            doc_id: 文档ID
            output_dir: 输出目录
            us_num: US编号（用于命名文件）

        Returns:
            DownloadResult对象，包含下载结果信息
        """
        print(f"开始下载文档: {doc_id}")

        try:
            # 步骤1：获取flow_id
            print("步骤1: 获取flow_id...")
            flow_id = self.get_flow_id(doc_id)
            if not flow_id:
                return DownloadResult(
                    success=False,
                    error_message="获取flow_id失败"
                )

            # 步骤2：轮询获取下载URL
            print("步骤2: 轮询获取下载URL...")
            download_url = self.poll_export_status(doc_id, flow_id)
            if not download_url:
                return DownloadResult(
                    success=False,
                    error_message="获取下载URL失败"
                )

            # 步骤3：下载文件
            print("步骤3: 下载文件...")

            success = self.download_single_file(download_url, output_dir, None)

            # 构建文件路径（重命名为需求编号）
            file_path = None
            if success:
                # 查找实际下载的文件（download_single_file使用URL提取的文件名，可能不是需求编号）
                import urllib.parse
                parsed_url = urllib.parse.urlparse(download_url)
                path_parts = parsed_url.path.split('/')
                actual_filename = path_parts[-1] if path_parts[-1] else "document"
                actual_filename = actual_filename.split('?')[0]
                if not actual_filename.lower().endswith('.docx'):
                    actual_filename += '.docx'

                actual_path = Path(output_dir) / actual_filename
                target_filename = us_num + '.docx'
                target_path = Path(output_dir) / target_filename

                # 重命名文件为需求编号（如果实际文件名与目标不同）
                if actual_path.exists() and actual_filename != target_filename:
                    try:
                        actual_path.rename(target_path)
                        print(f"文件已重命名: {actual_filename} -> {target_filename}")
                    except OSError as e:
                        print(f"重命名失败: {e}，使用原始文件名: {actual_filename}")
                        target_path = actual_path
                        target_filename = actual_filename
                elif not actual_path.exists():
                    # 实际文件不存在，尝试用Glob查找
                    docx_files = list(Path(output_dir).glob("*.docx"))
                    if docx_files:
                        target_path = docx_files[0]
                        target_filename = target_path.name
                    else:
                        target_filename = actual_filename

                file_path = str(target_path)

            return DownloadResult(
                success=success,
                download_url=download_url,
                file_path=file_path,
                error_message=None if success else "文件下载失败"
            )

        except Exception as e:
            print(f"下载过程中发生错误: {str(e)}")
            return DownloadResult(
                success=False,
                error_message=str(e)
            )


def main():
    """直接运行的主函数"""
    print("=== CoreALM 文档下载工具 ===")

    # 检查命令行参数
    if len(sys.argv) != 4:
        print("用法: python single_file_downloader.py <doc_id> <output_directory> <us_num>")
        print("示例: python single_file_downloader.py \"f257d2e0-4bd7-416e-b202-74f2380b365b\" \"./downloads\" \"US12345\"")
        sys.exit(1)

    DOC_ID = sys.argv[1]
    OUTPUT_DIR = sys.argv[2]
    US_NUM = sys.argv[3]

    try:
        # 创建下载器并下载
        print("初始化下载器...")
        downloader = SingleDownloader()

        print(f"开始下载文档: {DOC_ID}")
        print(f"输出目录: {OUTPUT_DIR}")
        result = downloader.download_by_doc_id(DOC_ID, US_NUM, OUTPUT_DIR)

        # 输出结果
        if result.success:
            print(f"下载成功!")
            print(f"下载URL: {result.download_url}")
            print(f"文件路径: {result.file_path}")
        else:
            print(f"下载失败: {result.error_message}")

    except ImportError as e:
        print(f"模块导入错误: {e}")
        print("请确保已正确安装所需的依赖模块")
    except Exception as e:
        print(f"未预期错误: {e}")


if __name__ == "__main__":
    main()
