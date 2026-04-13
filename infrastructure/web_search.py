"""
infrastructure/web_search.py
Web検索ツールと権限管理

Step 3: agents.yaml の search_permissions リストベースに変更。
"""
from langchain_community.tools import DuckDuckGoSearchRun

search_tool = DuckDuckGoSearchRun()


def check_search_permission(permissions, trigger_type):
    """search_permissions リストに基づく検索権限チェック。

    Args:
        permissions: エージェントの search_permissions リスト
                     例: ["noon"], ["user", "morning"], ["*"]
        trigger_type: 現在のトリガー種別（"user", "morning", "noon", "night"）

    Returns:
        bool: 検索が許可されているかどうか
    """
    if not permissions:
        return False
    if "*" in permissions:
        return True
    return trigger_type in permissions
