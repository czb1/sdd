#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CoreAlm 需求信息获取接口
用于从CoreAlm系统获取需求相关信息
"""

import json
import requests
from typing import Dict, Optional, Any


class CoreAlmAPI:
    """CoreAlm API 客户端"""

    def __init__(self, base_url: str = "https://coreinsight.rnd.huawei.com/chat"):
        self.base_url = base_url
        self.e2e_info_endpoint = "/search/corealm/e2e_info"

    def get_e2e_info(
        self,
        e2e_id: str,
        user_id: str = "",
        doc_open: bool = True,
        desc_open: bool = True
    ) -> Dict[str, Any]:
        """
        获取需求信息

        Args:
            e2e_id: US号/Story号/IR号
            user_id: 用户工号
            doc_open: 是否打开文档
            desc_open: 是否打开描述

        Returns:
            API响应结果字典
        """
        url = f"{self.base_url}{self.e2e_info_endpoint}"

        payload = {
            "e2e_id": e2e_id,
            "user_id": user_id,
            "doc_open": doc_open,
            "desc_open": desc_open
        }

        try:
            response = requests.post(url, json=payload, timeout=30, verify=False)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "code": 500,
                "msg": f"请求失败: {str(e)}",
                "data": None
            }

    def parse_e2e_id(self, e2e_id: str) -> Dict[str, str]:
        """
        解析E2E ID，判断类型

        Args:
            e2e_id: 需求ID

        Returns:
            包含id_type和id_value的字典
        """
        e2e_id = e2e_id.strip().upper()

        if e2e_id.startswith("US"):
            return {"id_type": "us", "id_value": e2e_id}
        elif e2e_id.startswith("ST"):
            return {"id_type": "story", "id_value": e2e_id}
        elif e2e_id.startswith("IR"):
            return {"id_type": "ir", "id_value": e2e_id}
        else:
            # 尝试自动识别
            return {"id_type": "unknown", "id_value": e2e_id}

    def get_requirement_info(self, requirement_id: str, user_id: str = "") -> Dict[str, Any]:
        """
        获取需求详细信息

        Args:
            requirement_id: US号/Story号/IR号
            user_id: 用户工号

        Returns:
            需求信息字典，包含以下键:
            - e2e_id: 需求ID
            - ir_id: IR ID
            - description: 需求描述
            - attachments: 附件列表
            - doc_info: 文档信息
        """
        result = self.get_e2e_info(requirement_id, user_id)

        if result.get("code") != 200:
            return {
                "success": False,
                "error": result.get("msg", "未知错误"),
                "data": None
            }

        data = result.get("data", {})

        # 提取关键信息
        requirement_info = {
            "success": True,
            "e2e_id": data.get("e2e_id", requirement_id),
            "ir_id": data.get("ir_id", ""),
            "sr_id": data.get("sr_id", ""),
            "sr_e2e_id": data.get("sr_e2e_id", ""),
            "us_id": data.get("us_id", ""),
            "description": data.get("description", ""),
            "attachments": [],
            "doc_info": []
        }

        # 处理文档信息
        ir_doc_info = data.get("IR_doc_info", [])
        for doc in ir_doc_info:
            requirement_info["doc_info"].append({
                "doc_id": doc.get("docId", ""),
                "doc_url": doc.get("doc_url", ""),
                "doc_type":doc.get("docType", ""),
                "introduction": doc.get("introduction", "")
            })

        return requirement_info


def get_requirement_by_id(requirement_id: str, user_id: str = "") -> Dict[str, Any]:
    """
    根据需求ID获取需求信息的便捷函数

    Args:
        requirement_id: US号/Story号/IR号
        user_id: 用户工号

    Returns:
        需求信息字典
    """
    api = CoreAlmAPI()
    return api.get_requirement_info(requirement_id, user_id)


def main():
    """测试入口"""
    import argparse

    parser = argparse.ArgumentParser(description="CoreAlm需求信息获取工具")
    parser.add_argument("--id", "-i", required=True, help="需求ID (US/Story/IR)")
    parser.add_argument("--user", "-u", default="", help="用户工号")

    args = parser.parse_args()

    result = get_requirement_by_id(args.id, args.user)

    if result["success"]:
        print(f"需求信息如下：")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"错误: {result['error']}")


if __name__ == "__main__":
    main()
