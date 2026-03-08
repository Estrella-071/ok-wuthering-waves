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

    def build_tree_dict(self, node: TreeNode, prefix: str = "", is_last: bool = True, is_root: bool = True, result_dict: dict = None) -> dict:
        if result_dict is None:
            result_dict = {}
            
        if not is_root:
            connector = "└ " if is_last else "├ "
            
            # 狀態文字後綴 (作為 Dict 的 Value)
            status_text = ""
            if node.status == RunStatus.DONE:
                status_text = f"({self._translate('完成')})"
            elif node.status == RunStatus.FAILED:
                status_text = f"({self._translate('失敗')})"
            elif node.status == RunStatus.RUNNING:
                status_text = f"({self.spinners[self.spinner_index]})"
                
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
            
        for i, child in enumerate(node.children):
            self.build_tree_dict(child, child_prefix, i == len(node.children) - 1, False, result_dict)
            
        return result_dict

    def get_formatted_dict(self) -> dict:
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
