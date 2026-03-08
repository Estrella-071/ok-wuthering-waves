import time
from enum import Enum
from typing import List, Optional

class RunStatus(Enum):
    PENDING = 0
    RUNNING = 1
    DONE = 2
    FAILED = 3

class TreeNode:
    def __init__(self, id: str, text: str):
        self.id = id
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

class ProgressFormatter:
    def __init__(self, root_name: str):
        self.root = TreeNode("root", root_name)
        self.current_running_node: Optional[TreeNode] = None
        self.spinners = ['|', '/', '-', '\\']
        self.spinner_index = 0
        self.last_spin_time = time.time()
        self.spin_interval = 0.2
        self._error_msg = ""
        
        # 為了支援 i18n，我們定義一個內部的翻譯佔位符，如果專案有全域 _() 函式可替換
        try:
            from ok.i18n import _ # 假設 ok 框架有 i18n
            self._translate = _
        except ImportError:
            self._translate = lambda x: x

    def set_error(self, msg: str):
        self._error_msg = msg

    def update_spin(self):
        now = time.time()
        if now - self.last_spin_time >= self.spin_interval:
            self.spinner_index = (self.spinner_index + 1) % len(self.spinners)
            self.last_spin_time = now
            return True # 標示需要重繪
        return False

    def get_node(self, node_id: str) -> Optional[TreeNode]:
        return self.root.find_node(node_id)

    def add_node(self, node_id: str, text: str, parent_id: str = "root") -> TreeNode:
        parent = self.get_node(parent_id)
        if not parent:
            parent = self.root
        new_node = TreeNode(node_id, text)
        parent.add_child(new_node)
        return new_node

    def set_status(self, node_id: str, status: RunStatus):
        node = self.get_node(node_id)
        if node:
            node.status = status
            if status == RunStatus.RUNNING:
                self.current_running_node = node

    def update_text(self, node_id: str, text: str):
        node = self.get_node(node_id)
        if node:
            node.text = text

    def build_tree_string(self, node: TreeNode, prefix: str = "", is_last: bool = True, is_root: bool = True) -> str:
        res = ""
        if not is_root:
            connector = "└ " if is_last else "├ "
            
            # 狀態文字後綴
            status_text = ""
            if node.status == RunStatus.DONE:
                status_text = f" ({self._translate('完成')})"
            elif node.status == RunStatus.FAILED:
                status_text = f" ({self._translate('失敗')})"
            elif node.status == RunStatus.RUNNING:
                status_text = f" ( {self.spinners[self.spinner_index]} )"
                
            res += f"{prefix}{connector}{self._translate(node.text)}{status_text}\n"
            
            # 子節點的前綴
            child_prefix = prefix + ("   " if is_last else "│  ")
        else:
            res += f"{self._translate(node.text)}\n"
            child_prefix = prefix
            
        for i, child in enumerate(node.children):
            res += self.build_tree_string(child, child_prefix, i == len(node.children) - 1, False)
            
        return res

    def get_formatted_string(self) -> str:
        # 使用 HTML 標籤來防換行與設定等寬字體，這在 Qt 支援 RichText 時有效
        # 自動捲動部分通常由外部 UI 元件 (如 ScrollArea) 處理，或者是表格的自動排版
        # 但我們可以用 nowrap 讓排版不被破壞
        tree_str = self.build_tree_string(self.root)
        
        if self._error_msg:
            tree_str += f"\n  └ [{self._translate('錯誤')}] {self._error_msg}"
            
        # 使用 <pre> 標籤以保持空格和換行，並強制不換行
        html_str = f'<pre style="font-family: monospace; white-space: pre; margin: 0;">{tree_str}</pre>'
        return html_str
