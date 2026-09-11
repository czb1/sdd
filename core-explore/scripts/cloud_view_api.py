#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
云见知识检索接口
用于从云见知识库检索相关业务知识
"""

import json
import requests
from typing import Dict, List, Optional, Any


class CloudViewAPI:
    """云见知识检索 API 客户端"""

    def __init__(self, base_url: str = "https://coreinsight.rnd.huawei.com"):
        self.base_url = base_url
        self.retrieve_endpoint = "/chat/search/knowledge/retrieve"

    def search_knowledge(
        self,
        query: str,
        user_id: str = "",
        sources: List[str] = None,
        dept_code: str = "",
        product_name: str = "",
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        检索知识

        Args:
            query: 查询问题
            user_id: 用户工号
            sources: 知识来源列表，如 ["设计文档", "产品文档", "部门知识"]
            dept_code: 部门编码
            product_name: 产品名称
            top_k: 返回结果数量

        Returns:
            API响应结果字典
        """
        url = f"{self.base_url}{self.retrieve_endpoint}"

        if sources is None:
            sources = ["设计文档", "产品文档", "部门知识"]

        payload = {
            "query": query,
            "user_id": user_id,
            "sources": sources,
            "dept_code": dept_code,
            "product_name": product_name,
            "custom_filter": {},
            "top_k": top_k
        }

        try:
            response = requests.post(url, json=payload, timeout=30, verify=False)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {
                "code": 500,
                "msg": f"请求失败: {str(e)}",
                "data": []
            }

    def parse_search_result(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        解析检索结果

        Args:
            result: API响应结果

        Returns:
            解析后的知识条目列表
        """
        if result.get("code") != 200:
            return []

        data = result.get("data", [])
        parsed_results = []

        for item in data:
            org_data = item.get("orgData", {})
            parsed_results.append({
                "title": org_data.get("title", ""),
                "text": org_data.get("text", ""),
                "abstract": org_data.get("abstract", ""),
                "filename": org_data.get("filename", ""),
                "uri": org_data.get("uri", ""),
                "similarity": item.get("similarity", ""),
                "source": org_data.get("from", "")
            })

        return parsed_results

    def search_and_parse(
        self,
        query: str,
        user_id: str = "",
        sources: List[str] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        检索并解析结果

        Args:
            query: 查询问题
            user_id: 用户工号
            sources: 知识来源列表
            top_k: 返回结果数量

        Returns:
            知识条目列表
        """
        result = self.search_knowledge(query, user_id, sources, top_k=top_k)
        return self.parse_search_result(result)


def search_knowledge(
    query: str,
    user_id: str = "",
    sources: List[str] = None,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    检索知识的便捷函数

    Args:
        query: 查询问题
        user_id: 用户工号
        sources: 知识来源列表
        top_k: 返回结果数量

    Returns:
        知识条目列表
    """
    api = CloudViewAPI()
    return api.search_and_parse(query, user_id, sources, top_k)


def extract_keywords_from_text(text: str, max_keywords: int = 5) -> List[str]:
    """
    从文本中提取关键词

    Args:
        text: 输入文本
        max_keywords: 最大关键词数量

    Returns:
        关键词列表
    """
    import re

    # 移除标点符号
    text = re.sub(r'[^\w\s]', ' ', text)

    # 简单的分词
    words = text.split()

    # 过滤停用词和短词
    stopwords = {'的', '是', '在', '和', '了', '与', '或', '等', '为', '以', '及', '该', '这', '那', '有', '无'}
    keywords = [w for w in words if len(w) >= 2 and w not in stopwords]

    # 统计词频
    word_freq = {}
    for word in keywords:
        word_freq[word] = word_freq.get(word, 0) + 1

    # 按词频排序
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)

    return [word for word, _ in sorted_words[:max_keywords]]


def identify_difficult_terms(text: str) -> List[str]:
    """
    识别文本中可能难以理解的术语

    Args:
        text: 输入文本

    Returns:
        术语列表（需要进一步查询的）
    """
    # 技术术语模式
    patterns = [
        r'\b[A-Z]{2,}\b',  # 英文缩写如 PCF, NWDAF
        r'\b\w+(?:ID|Code)\b',  # 包含ID/Code的词
        r'\b\w+系数\b',
        r'\b\w+策略\b',
        r'\b\w+模型\b',
        r'\b\w+引擎\b',
    ]

    import re
    terms = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        terms.extend(matches)

    # 去重
    return list(set(terms))


def main():
    """测试入口"""
    import argparse

    parser = argparse.ArgumentParser(description="云见知识检索工具")
    parser.add_argument("--query", "-q", required=True, help="查询问题")
    parser.add_argument("--user", "-u", default="", help="用户工号")
    parser.add_argument("--topk", "-k", type=int, default=5, help="返回结果数量")

    args = parser.parse_args()

    results = search_knowledge(args.query, args.user, top_k=args.topk)

    print(f"找到 {len(results)} 条相关知识:\n")

    for i, result in enumerate(results, 1):
        print(f"{i}. {result['title']}")
        print(f"   相似度: {result['similarity']}")
        print(f"   来源: {result['source']}")
        print(f"   摘要: {result['abstract']}")
        print()


if __name__ == "__main__":
    main()
