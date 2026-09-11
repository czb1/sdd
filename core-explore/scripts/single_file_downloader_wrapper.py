#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Single File Downloader Wrapper - Skill Version

为skill提供简化的接口，通过doc_id下载Corealm系统中的Word文档。
"""

import os
import sys
from pathlib import Path
from datetime import datetime

try:
    from single_file_downloader import SingleDownloader, DownloadResult
except ImportError as e:
    print(f"❌ 导入错误: {e}")
    print("请确保single_file_downloader.py在scripts目录中")
    sys.exit(1)


class SingleFileDownloaderSkill:
    """用于单文件下载的Skill类"""
    
    def __init__(self):
        """初始化下载器"""
        self.downloader = SingleDownloader()
    
    def download_doc_by_id(self, doc_id: str, output_dir: str) -> dict:
        """
        通过doc_id下载文档
        
        Args:
            doc_id: Corealm系统中的文档ID
            output_dir: 输出目录路径
            
        Returns:
            包含下载结果信息的字典
        """
        print(f"🔄 开始下载文档: {doc_id}")
        print(f"📁 输出目录: {output_dir}")
        
        try:
            # 调用原始下载函数
            result = self.downloader.download_by_doc_id(doc_id, output_dir)
            
            # 格式化返回结果
            result_dict = {
                "success": result.success,
                "doc_id": doc_id,
                "output_dir": output_dir,
                "file_path": result.file_path,
                "download_url": result.download_url,
                "error_message": result.error_message,
                "message": "下载成功" if result.success else f"下载失败: {result.error_message}",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "note": "如需指定自定义文件名，请考虑修改 download_single_file 方法的 doc_name 参数"
            }
            
            if result.success:
                print(f"✅ 下载成功!")
                print(f"📄 文件路径: {result.file_path}")
            else:
                print(f"❌ 下载失败: {result.error_message}")
            
            return result_dict
            
        except Exception as e:
            error_msg = f"下载过程中发生异常: {str(e)}"
            print(f"❌ {error_msg}")
            
            return {
                "success": False,
                "doc_id": doc_id,
                "output_dir": output_dir,
                "file_path": None,
                "download_url": None,
                "error_message": str(e),
                "message": error_msg,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }


def validate_inputs(doc_id: str, output_dir: str) -> tuple[bool, str]:
    """
    验证输入参数
    
    Args:
        doc_id: 文档ID
        output_dir: 输出目录
        
    Returns:
        (是否有效, 错误信息)
    """
    if not doc_id:
        return False, "文档ID不能为空"
    
    if not output_dir:
        return False, "输出目录不能为空"
    
    # 验证文档ID格式（UUID格式）
    if len(doc_id) != 36 or doc_id.count('-') != 4:
        return False, "文档ID格式不正确，应包含36个字符和4个连字符"
    
    # 验证输出目录
    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        return True, ""
    except Exception as e:
        return False, f"无法创建输出目录: {str(e)}"


def main():
    """主函数 - 接收doc_id和output_dir作为参数"""
    print("=== CoreALM文档下载器 (Skill版本) ===")
    
    if len(sys.argv) != 4:
        print("用法: python single_file_downloader_wrapper.py <doc_id> <output_directory>")
        print("示例: python single_file_downloader_wrapper.py \"f257d2e0-4bd7-416e-b202-74f2380b365b\" \"./downloads\"")
        sys.exit(1)
    
    doc_id = sys.argv[1]
    output_dir = sys.argv[2]
    US_NUM = sys.argv[3]

    # 验证输入
    is_valid, error_msg = validate_inputs(doc_id, output_dir)
    if not is_valid:
        print(f"❌ 输入验证失败: {error_msg}")
        sys.exit(1)
    
    # 创建下载器并执行下载
    downloader_skill = SingleFileDownloaderSkill()
    result = downloader_skill.download_doc_by_id(doc_id, output_dir)
    
    # 返回结果（用于和其他系统集成）
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
