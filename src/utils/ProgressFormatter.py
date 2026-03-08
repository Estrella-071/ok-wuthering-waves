"""進度格式化工具：將任務流程以樹狀結構渲染為字典，供 ok 框架的 QTableWidget 直接呈現。"""
import time
from enum import Enum
from typing import List, Optional, Dict


class RunStatus(Enum):
    """節點狀態列舉。"""
    PENDING = 0
    RUNNING = 1
    DONE = 2
    FAILED = 3


class TreeNode:
    """樹狀結構中的單一節點。"""

    def __init__(self, node_id: str, text: str):
        self.id = node_id
        self.text = text
        self.status = RunStatus.PENDING
        self.children: List['TreeNode'] = []
        self.parent: Optional['TreeNode'] = None

    def add_child(self, node: 'TreeNode'):
        node.parent = self
        self.children.append(node)
        return node

    def find_node(self, node_id: str) -> Optional['TreeNode']:
        if self.id == node_id:
            return self
        for child in self.children:
            found = child.find_node(node_id)
            if found:
                return found
        return None

    def has_visible_children(self) -> bool:
        """判斷此節點下是否有任何非 PENDING 的子節點。"""
        for child in self.children:
            if child.status != RunStatus.PENDING:
                return True
            if child.has_visible_children():
                return True
        return False


class ProgressFormatter:
    """將任務進度以樹狀字典格式輸出。

    核心設計：
    - PENDING 狀態的節點不會被渲染，因此節點會「漸進式」出現
    - RUNNING 狀態的節點會帶有 Spinner 轉圈動畫
    - 所有的文字皆透過 _translate 方法處理，支援 i18n
    """

    # 使用原始字串 (raw string) 避免反斜線被轉義
    SPINNERS = ['|', '/', '-', '\\']

    def __init__(self, root_name: str):
        self.root = TreeNode("root", root_name)
        self.root.status = RunStatus.RUNNING  # root 永遠是 RUNNING 以便顯示
        self.current_running_node: Optional[TreeNode] = None
        self.spinner_index = 0
        self.last_spin_time = time.time()
        self.spin_interval = 0.2
        self._error_msg = ""
        self._on_change_callback = None

        # i18n 翻譯函式
        try:
            from ok.i18n import _
            self._translate = _
        except ImportError:
            self._translate = lambda x: x

    def set_on_change(self, callback):
        """設定當樹狀結構變動時的回呼函式 (用於即時刷新 UI)。"""
        self._on_change_callback = callback

    def _notify_change(self):
        """通知外部有東西變更，需要重繪 UI。"""
        if self._on_change_callback:
            self._on_change_callback()

    def set_error(self, msg: str):
        self._error_msg = msg
        self._notify_change()

    def update_spin(self):
        """更新 Spinner 索引。由 next_frame 定時呼叫。"""
        now = time.time()
        if now - self.last_spin_time >= self.spin_interval:
            self.spinner_index = (self.spinner_index + 1) % len(self.SPINNERS)
            self.last_spin_time = now
            return True
        return False

    def get_node(self, node_id: str) -> Optional[TreeNode]:
        return self.root.find_node(node_id)

    def add_node(self, node_id: str, text: str, parent_id: str = "root") -> TreeNode:
        """新增一個 PENDING 節點。PENDING 節點不會被渲染，直到狀態改變。"""
        # 如果 node_id 已存在，直接更新文字
        existing = self.get_node(node_id)
        if existing:
            existing.text = text
            return existing

        parent = self.get_node(parent_id)
        if not parent:
            parent = self.root
        new_node = TreeNode(node_id, text)
        parent.add_child(new_node)
        return new_node

    def set_status(self, node_id: str, status: RunStatus):
        """設定節點狀態並觸發 UI 刷新。"""
        node = self.get_node(node_id)
        if node:
            node.status = status
            if status == RunStatus.RUNNING:
                self.current_running_node = node
            self._notify_change()

    def update_text(self, node_id: str, text: str):
        """更新指定節點的顯示文字並觸發 UI 刷新。"""
        node = self.get_node(node_id)
        if node:
            node.text = text
            self._notify_change()

    def update_current_node_text(self, text: str):
        """更新當前處於 RUNNING 狀態節點的顯示文字並觸發 UI 刷新。"""
        if self.current_running_node:
            self.current_running_node.text = text
            self._notify_change()

    def _get_visible_children(self, node: TreeNode) -> List[TreeNode]:
        """取得節點下所有「可見」的子節點 (非 PENDING，或自身有可見子節點)。"""
        visible = []
        for child in node.children:
            if child.status != RunStatus.PENDING or child.has_visible_children():
                visible.append(child)
        return visible

    def build_tree_dict(self, node: TreeNode, prefix: str = "",
                        is_last: bool = True, is_root: bool = True,
                        result_dict: dict = None) -> dict:
        """遞迴建構樹狀字典。只渲染非 PENDING 的節點。"""
        if result_dict is None:
            result_dict = {}

        if not is_root:
            # 跳過 PENDING 且無可見子節點的節點
            if node.status == RunStatus.PENDING and not node.has_visible_children():
                return result_dict

            connector = "└ " if is_last else "├ "

            # 狀態文字後綴 (作為 Dict 的 Value)
            status_text = ""
            if node.status == RunStatus.DONE:
                status_text = self._translate('完成')
            elif node.status == RunStatus.FAILED:
                status_text = self._translate('失敗')
            elif node.status == RunStatus.RUNNING:
                status_text = self.SPINNERS[self.spinner_index]

            key = f"{prefix}{connector}{self._translate(node.text)}"

            # 確保 Dictionary Key 唯一性 (使用零寬空白)
            original_key = key
            counter = 1
            while key in result_dict:
                key = original_key + ("\u200b" * counter)
                counter += 1

            result_dict[key] = status_text

            # 子節點的前綴
            child_prefix = prefix + ("   " if is_last else "│  ")
        else:
            key = f"{self._translate(node.text)}"
            original_key = key
            counter = 1
            while key in result_dict:
                key = original_key + ("\u200b" * counter)
                counter += 1
            result_dict[key] = ""
            child_prefix = prefix

        # 只遍歷可見的子節點
        visible_children = self._get_visible_children(node)
        for i, child in enumerate(visible_children):
            self.build_tree_dict(child, child_prefix, i == len(visible_children) - 1, False, result_dict)

        return result_dict

    def get_formatted_dict(self) -> Dict[str, str]:
        """產生完整的樹狀字典。每次呼叫時自動推進 Spinner。"""
        self.update_spin()
        tree_dict = self.build_tree_dict(self.root)

        if self._error_msg:
            key = f"  └ [{self._translate('錯誤')}]"
            original_key = key
            counter = 1
            while key in tree_dict:
                key = original_key + ("\u200b" * counter)
                counter += 1
            tree_dict[key] = self._error_msg

        return tree_dict
