import difflib
import json
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QPixmap, QTextCursor, QTextFormat, QPainter, QPainterPath
from PySide6.QtWidgets import QApplication, QButtonGroup, QHBoxLayout, QLabel, QListWidgetItem, QSplitter, QTextEdit, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, SubtitleLabel, FluentIcon, ListWidget, MessageBox, PlainTextEdit, PrimaryPushButton, PushButton, RadioButton, SegmentedWidget

from ok.gui.tasks.EditTaskTab import CodeEditor
from ok.gui.tasks.PythonHighlighter import PythonHighlighter
from ok.gui.util.app import show_info_bar
from ok.gui.widget.CustomTab import CustomTab
from src.char.CharFactory import char_dict
from src.char.CustomCharLoader import (
    has_custom_char_code,
    is_custom_char_enabled,
    load_custom_char_class,
    read_builtin_char_code,
    read_custom_or_builtin_char_code,
    remove_custom_char_code,
    save_custom_char_code,
    set_custom_char_enabled,
)

BASE_CHAR_URL = "https://raw.githubusercontent.com/ok-oldking/ok-wuthering-waves/refs/heads/master/src/char/BaseChar.py"
CONTRIBUTE_CHAR_URL = "https://github.com/ok-oldking/ok-wuthering-waves/edit/master/src/char/{class_name}.py"
CHARACTER_DISPLAY_NAMES = {
    "Douling": "Buling",
    "Xigelika": "Sigrika",
    "Linnai": "Lynae",
    "Luhesi": "Luuk Herssen",
    "Xiangliyao": "Xiangli Yao",
    "ShoreKeeper": "Shorekeeper",
    "HavocRover": "Rover: Havoc",
}

class CharacterItemWidget(QWidget):
    def __init__(self, display_name, file_name, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 12, 6)
        layout.setSpacing(10)
        
        self.avatar_label = QLabel(self)
        self.avatar_label.setFixedSize(32, 32)
        self.avatar_label.setAlignment(Qt.AlignCenter)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 0, 0, 0)
        
        self.name_label = BodyLabel(display_name, self)
        self.file_label = BodyLabel(file_name, self)
        self.file_label.setStyleSheet("color: #8c8c8c; font-size: 11px;")
        
        text_layout.addWidget(self.name_label)
        text_layout.addWidget(self.file_label)
        
        layout.addWidget(self.avatar_label)
        layout.addLayout(text_layout, 1)
        
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def set_avatar(self, pixmap):
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.avatar_label.setPixmap(scaled)
        else:
            self.avatar_label.clear()


class CharacterCodeTab(CustomTab):
    def __init__(self):
        super().__init__()
        self.current_char_cls = None
        self.current_row = -1
        self.char_by_name = {}
        self.char_label_by_cls = {}
        self.char_feature_index = self._load_char_feature_index()
        self.char_feature_images = {}
        self.char_source_pixmaps = {}
        self.show_char_feature_image = False
        self.clean_code = ""
        self.loading_editor = False
        self.suppress_selection_guard = False
        self.suppress_mode_guard = False

        splitter = QSplitter(Qt.Horizontal, self.view)
        splitter.setChildrenCollapsible(False)

        left = QWidget(splitter)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(10)
        left_layout.addWidget(SubtitleLabel(self.tr("Characters")))

        self.char_list = ListWidget(left)
        self.char_list.setMinimumWidth(220)
        self.char_list.setMaximumWidth(320)
        self.char_list.currentRowChanged.connect(self._char_selected)
        left_layout.addWidget(self.char_list, 1)

        right = QWidget(splitter)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(10)
        right_layout.addWidget(SubtitleLabel(self.tr("Character Code")))

        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(12)
        
        self.char_image_label = QLabel()
        self.char_image_label.setFixedSize(52, 52)
        self.char_image_label.setAlignment(Qt.AlignCenter)
        
        # Character info layout (Name & Badges)
        char_info_layout = QVBoxLayout()
        char_info_layout.setSpacing(4)
        char_info_layout.setContentsMargins(0, 0, 0, 0)
        
        self.char_name_label = SubtitleLabel("", self)
        
        self.badge_layout = QHBoxLayout()
        self.badge_layout.setSpacing(6)
        self.badge_layout.setContentsMargins(0, 0, 0, 0)
        
        self.attr_badge = QLabel(self)
        self.attr_badge.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8A2387, stop:1 #E94057);
                color: white;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        self.position_badge = QLabel(self)
        self.position_badge.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #11998e, stop:1 #38ef7d);
                color: white;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
                font-weight: bold;
            }
        """)
        self.badge_layout.addWidget(self.attr_badge)
        self.badge_layout.addWidget(self.position_badge)
        self.badge_layout.addStretch(1)
        
        char_info_layout.addWidget(self.char_name_label)
        char_info_layout.addLayout(self.badge_layout)
        
        # Segmented Control for mode selection
        self.segmented_widget = SegmentedWidget(self)
        self.segmented_widget.addItem("builtin", self.tr("Use built in"))
        self.segmented_widget.addItem("custom", self.tr("Use custom"))
        self.segmented_widget.currentItemChanged.connect(self._on_segment_changed)
        
        mode_layout.addWidget(self.char_image_label)
        mode_layout.addLayout(char_info_layout)
        mode_layout.addWidget(self.segmented_widget)
        mode_layout.addStretch(1)
        
        self.ask_ai_button = PushButton(FluentIcon.ROBOT, self.tr("Ask AI"))
        self.ask_ai_button.clicked.connect(self._copy_ask_ai_template)
        self.how_to_button = PushButton(FluentIcon.HELP, self.tr("How To"))
        self.how_to_button.clicked.connect(self._show_how_to)
        self.contribute_button = PushButton(FluentIcon.GITHUB, self.tr("Contribute Code"))
        self.contribute_button.clicked.connect(self._open_contribute_code)
        mode_layout.addWidget(self.ask_ai_button)
        mode_layout.addWidget(self.how_to_button)
        mode_layout.addWidget(self.contribute_button)
        right_layout.addLayout(mode_layout)

        # Splitter to hold Editor (left) and Combat API Side Panel (right)
        self.editor_splitter = QSplitter(Qt.Horizontal, right)
        self.editor_splitter.setChildrenCollapsible(True)

        self.editor = CodeEditor(self.editor_splitter)
        self.editor.setMinimumHeight(520)
        self.editor.setLineWrapMode(PlainTextEdit.NoWrap)
        font = self.editor.font()
        font.setFamily("Consolas")
        font.setPointSize(11)
        self.editor.setFont(font)
        self.highlighter = PythonHighlighter(self.editor.document())
        self.editor.textChanged.connect(self._editor_text_changed)
        self.editor_splitter.addWidget(self.editor)

        # Combat API Reference Side Panel
        self.api_panel = QWidget(self.editor_splitter)
        api_layout = QVBoxLayout(self.api_panel)
        api_layout.setContentsMargins(6, 0, 0, 0)
        api_layout.setSpacing(6)
        
        api_title = BodyLabel(self.tr("Combat API Reference"), self.api_panel)
        api_title.setStyleSheet("font-weight: bold; color: #009FAA;")
        api_layout.addWidget(api_title)
        
        self.api_list = ListWidget(self.api_panel)
        self.api_list.setMinimumWidth(180)
        self.api_list.setMaximumWidth(280)
        self.api_list.itemDoubleClicked.connect(self._insert_api_code)
        
        # Populate combat APIs reference
        apis = [
            ("click_resonance()", "self.click_resonance()", self.tr("Resonance Skill (E)")),
            ("click_liberation()", "self.click_liberation()", self.tr("Resonance Liberation (R)")),
            ("click_echo()", "self.click_echo()", self.tr("Echo (T)")),
            ("click_attack()", "self.click_attack()", self.tr("Normal Attack (LButton)")),
            ("click_heavy()", "self.click_heavy()", self.tr("Heavy Attack (Hold)")),
            ("dash()", "self.dash()", self.tr("Dash / Evade (Shift)")),
            ("jump()", "self.jump()", self.tr("Jump (Space)")),
            ("has_intro", "self.has_intro", self.tr("Intro Skill Ready")),
            ("is_current_char", "self.is_current_char", self.tr("Is Active Character")),
            ("resonance_cooldown_left()", "self.resonance_cooldown_left()", self.tr("Resonance Skill CD")),
            ("liberation_cooldown_left()", "self.liberation_cooldown_left()", self.tr("Resonance Liberation CD")),
            ("echo_cooldown_left()", "self.echo_cooldown_left()", self.tr("Echo Skill CD")),
        ]
        for name, code, desc in apis:
            item = QListWidgetItem()
            item.setText(f"{name}\n({desc})")
            item.setData(Qt.UserRole, code)
            item.setToolTip(self.tr("Double click to insert: ") + code)
            self.api_list.addItem(item)
            
        api_layout.addWidget(self.api_list)
        self.editor_splitter.addWidget(self.api_panel)
        self.editor_splitter.setStretchFactor(0, 4)
        self.editor_splitter.setStretchFactor(1, 1)
        right_layout.addWidget(self.editor_splitter, 1)

        bottom_layout = QHBoxLayout()
        self.status_label = BodyLabel("")
        self.reset_button = PushButton(FluentIcon.SYNC, self.tr("Reset"))
        self.reset_button.clicked.connect(self._reset_current)
        self.save_button = PrimaryPushButton(FluentIcon.SAVE, self.tr("Save"))
        self.save_button.clicked.connect(self._save_current)
        bottom_layout.addWidget(self.status_label, 1)
        bottom_layout.addWidget(self.reset_button)
        bottom_layout.addWidget(self.save_button)
        right_layout.addLayout(bottom_layout)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        self.add_widget(splitter, stretch=1)

        self._refresh_char_list()
        if self.char_list.count() > 0:
            self.char_list.setCurrentRow(0)

    @property
    def name(self):
        return self.tr("Character Code")

    @property
    def icon(self):
        return FluentIcon.CODE

    def _refresh_char_list(self, selected_cls=None):
        selected_name = selected_cls.__name__ if selected_cls else None
        unique_chars = []
        seen = set()
        for info in char_dict.values():
            char_cls = info.get("cls")
            if char_cls in seen:
                continue
            seen.add(char_cls)
            unique_chars.append(char_cls)
            self.char_label_by_cls[char_cls] = self._label_name(next(
                key for key, candidate in char_dict.items()
                if candidate.get("cls") is char_cls
            ))

        unique_chars.sort(key=lambda cls: (not has_custom_char_code(cls), cls.__name__.lower()))
        self.char_by_name = {char_cls.__name__: char_cls for char_cls in unique_chars}

        self.char_list.blockSignals(True)
        self.char_list.clear()
        selected_row = 0
        for row, char_cls in enumerate(unique_chars):
            label = self._display_char_name(char_cls)
            if has_custom_char_code(char_cls):
                label = f"* {label}"
            item = QListWidgetItem()
            item.setData(Qt.UserRole, char_cls.__name__)
            self.char_list.addItem(item)
            widget = CharacterItemWidget(label, f"{char_cls.__name__}.py", self.char_list)
            label_name = self.char_label_by_cls.get(char_cls)
            pixmap = self._get_char_feature_image(label_name)
            widget.set_avatar(pixmap)
            self.char_list.setItemWidget(item, widget)
            if char_cls.__name__ == selected_name:
                selected_row = row
        self.char_list.blockSignals(False)
        if self.char_list.count() > 0:
            self.char_list.setCurrentRow(selected_row)

    def _char_selected(self, row):
        if self.suppress_selection_guard:
            return
        if self._has_unsaved_changes() and not self._confirm_discard_changes():
            self.suppress_selection_guard = True
            self.char_list.setCurrentRow(self.current_row)
            self.suppress_selection_guard = False
            return
        item = self.char_list.item(row)
        if item is None:
            return
        char_name = item.data(Qt.UserRole)
        char_cls = self.char_by_name.get(char_name)
        if char_cls is None:
            return

        self.current_char_cls = char_cls
        self.current_row = row
        enabled = is_custom_char_enabled(char_cls)
        self.segmented_widget.setCurrentItem("custom" if enabled else "builtin")
        self._update_char_image()
        
        # Update character info labels & badges
        self.char_name_label.setText(self._display_char_name(char_cls))
        character_meta = {
            "Aemeath": (self.tr("Havoc"), self.tr("Main DPS")),
            "Augusta": (self.tr("Spectro"), self.tr("Support")),
            "Baizhi": (self.tr("Glacio"), self.tr("Healer")),
            "Brant": (self.tr("Electro"), self.tr("Sub DPS")),
            "Calcharo": (self.tr("Electro"), self.tr("Main DPS")),
            "Camellya": (self.tr("Havoc"), self.tr("Main DPS")),
            "Changli": (self.tr("Fusion"), self.tr("Main DPS")),
            "Chisa": (self.tr("Aero"), self.tr("Main DPS")),
            "Danjin": (self.tr("Havoc"), self.tr("Main DPS")),
            "Jianxin": (self.tr("Aero"), self.tr("Support")),
            "Jinhsi": (self.tr("Spectro"), self.tr("Main DPS")),
            "Jiyan": (self.tr("Aero"), self.tr("Main DPS")),
            "Rover": (self.tr("Spectro"), self.tr("Main DPS")),
            "HavocRover": (self.tr("Havoc"), self.tr("Main DPS")),
            "Sanhua": (self.tr("Glacio"), self.tr("Sub DPS")),
            "ShoreKeeper": (self.tr("Spectro"), self.tr("Support")),
            "Verina": (self.tr("Spectro"), self.tr("Healer")),
            "Yangyang": (self.tr("Aero"), self.tr("Sub DPS")),
            "Yinlin": (self.tr("Electro"), self.tr("Sub DPS")),
            "Zhezhi": (self.tr("Glacio"), self.tr("Sub DPS")),
        }
        meta = character_meta.get(char_cls.__name__, (self.tr("Unknown"), self.tr("Combatant")))
        self.attr_badge.setText(meta[0])
        self.position_badge.setText(meta[1])
        
        self._load_editor_code()
        self.status_label.setText(str(has_custom_char_code(char_cls) and self.tr("Custom code saved") or ""))

    def _sync_editor_state(self):
        is_builtin = self.segmented_widget.currentRouteKey() == "builtin"
        self.editor.setReadOnly(is_builtin)
        self.reset_button.setVisible(not is_builtin)
        self.save_button.setVisible(not is_builtin)

    def _on_segment_changed(self, key):
        if self.suppress_mode_guard:
            return
        if self.current_char_cls is None:
            return
        if key == "builtin" and self._has_unsaved_changes():
            if not self._confirm_discard_changes():
                self.suppress_mode_guard = True
                self.segmented_widget.setCurrentItem("custom")
                self.suppress_mode_guard = False
                self._sync_editor_state()
                return
        self._load_editor_code()

    def _insert_api_code(self, item):
        code = item.data(Qt.UserRole)
        if code:
            self.editor.insertPlainText(code)
            self.editor.setFocus()

    def _load_editor_code(self):
        if self.current_char_cls is None:
            return
        if self.segmented_widget.currentRouteKey() == "custom":
            code = read_custom_or_builtin_char_code(self.current_char_cls)
        else:
            code = read_builtin_char_code(self.current_char_cls)
        self.loading_editor = True
        self.editor.setPlainText(code)
        self.clean_code = code
        self.loading_editor = False
        self._sync_editor_state()
        self._highlight_changed_lines()

    def _editor_text_changed(self):
        if self.loading_editor:
            return
        self._highlight_changed_lines()
        self.status_label.setText(self.tr("Unsaved changes") if self._has_unsaved_changes() else "")

    def _has_unsaved_changes(self):
        return self.segmented_widget.currentRouteKey() == "custom" and self.editor.toPlainText() != self.clean_code

    def _confirm_discard_changes(self):
        box = MessageBox(
            self.tr("Unsaved Changes"),
            self.tr("Discard unsaved character code changes?"),
            self.window(),
        )
        return bool(box.exec())

    def _highlight_changed_lines(self):
        if self.current_char_cls is None or self.segmented_widget.currentRouteKey() == "builtin":
            self.editor.setExternalExtraSelections([])
            return

        builtin_lines = read_builtin_char_code(self.current_char_cls).splitlines()
        current_lines = self.editor.toPlainText().splitlines()
        changed_lines = set()
        matcher = difflib.SequenceMatcher(None, builtin_lines, current_lines)
        for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            changed_lines.update(range(j1, max(j2, j1 + 1)))

        selections = []
        highlight = QColor(255, 230, 130, 80)
        for line in sorted(changed_lines):
            block = self.editor.document().findBlockByNumber(line)
            if not block.isValid():
                continue
            selection = QTextEdit.ExtraSelection()
            selection.cursor = QTextCursor(block)
            selection.format.setBackground(highlight)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selections.append(selection)
        self.editor.setExternalExtraSelections(selections)

    def _save_current(self):
        if self.current_char_cls is None:
            return
        try:
            if self.segmented_widget.currentRouteKey() == "custom":
                code = self.editor.toPlainText()
                builtin_code = read_builtin_char_code(self.current_char_cls)
                if code == builtin_code:
                    remove_custom_char_code(self.current_char_cls)
                    reloaded = self._reload_live_char_code()
                    self._switch_to_builtin_mode(builtin_code)
                    self._refresh_char_list(self.current_char_cls)
                    message = self.tr("Custom code matches built in code. Removed custom code and switched to built in.")
                    if reloaded:
                        message = self.tr("Custom code matches built in code. Removed custom code, switched to built in, and reloaded loaded characters.")
                    show_info_bar(self.window(), message, title=self.tr("Success"))
                    return
                path = save_custom_char_code(self.current_char_cls, code, use_custom=True)
                reloaded = self._reload_live_char_code()
                self.clean_code = code
                self.status_label.setText(self.tr("Saved and reloaded"))
                message = self.tr("Custom character code saved and reloaded.")
                if reloaded:
                    message = self.tr("Custom character code saved and reloaded for loaded characters.")
                show_info_bar(self.window(), message, title=self.tr("Success"))
            else:
                set_custom_char_enabled(self.current_char_cls, False)
                path = None
                self.status_label.setText(self.tr("Using built in code"))
                show_info_bar(self.window(), self.tr("Built in character code selected."), title=self.tr("Success"))
            self._refresh_char_list(self.current_char_cls)
            if path:
                self.logger.info(f"saved custom char code {self.current_char_cls.__name__}: {path}")
        except Exception as e:
            self.logger.error(f"save custom char code failed: {e}")
            show_info_bar(self.window(), str(e), title=self.tr("Error"), error=True)

    def _reset_current(self):
        if self.current_char_cls is None:
            return
        box = MessageBox(
            self.tr("Reset Custom Code"),
            self.tr("Reset this character to built in code and remove the custom code?"),
            self.window(),
        )
        if not box.exec():
            return
        builtin_code = read_builtin_char_code(self.current_char_cls)
        remove_custom_char_code(self.current_char_cls)
        reloaded = self._reload_live_char_code()
        self._switch_to_builtin_mode(builtin_code)
        self._refresh_char_list(self.current_char_cls)
        message = self.tr("Custom code reset to built in code.")
        if reloaded:
            message = self.tr("Custom code reset to built in code and reloaded for loaded characters.")
        show_info_bar(self.window(), message, title=self.tr("Success"))

    def _switch_to_builtin_mode(self, builtin_code):
        self.suppress_mode_guard = True
        self.segmented_widget.setCurrentItem("builtin")
        self.suppress_mode_guard = False
        self.loading_editor = True
        self.editor.setPlainText(builtin_code)
        self.clean_code = builtin_code
        self.loading_editor = False
        self.status_label.setText(self.tr("Using built in code"))
        self._sync_editor_state()
        self._highlight_changed_lines()

    def _copy_ask_ai_template(self):
        if self.current_char_cls is None:
            return
        class_name = self.current_char_cls.__name__
        code = self.editor.toPlainText()
        modify_line = self.tr("Please modify the full {class_name} character automation code above.").format(
            class_name=class_name)
        class_line = self.tr("Keep the class name as {class_name}. Preserve imports that are still needed.").format(
            class_name=class_name)
        template = f"""```python
{code}
```

{self.tr("I want to implement:")}

{modify_line}

{self.tr("Return only the complete modified Python code for the whole file, not a patch and not an explanation.")}
{class_line}

{self.tr("Use this BaseChar reference while reasoning about helper methods, task APIs, state, switching, cooldowns, and combat flow:")}
{BASE_CHAR_URL}
"""
        QApplication.clipboard().setText(template)
        show_info_bar(
            self.window(),
            self.tr("Ask AI template copied. Paste it into an AI chatbot."),
            title=self.tr("Copied"),
        )

    def _show_how_to(self):
        message = self.tr(
            "Choose Use custom to edit a character's Python code. Use built-in mode to read and select the original code.\n\n"
            "Ask AI copies a prompt to the clipboard with the full current code at the top. Paste it into an AI chatbot, "
            "describe the change after 'I want to implement:', and ask it to return the full modified code.\n\n"
            "Paste the returned code back into this editor, review the highlighted changed lines, then click Save to apply changes."
        )
        box = MessageBox(self.tr("How To Modify Character Code"), message, self.window())
        box.cancelButton.hide()
        box.exec()

    def _open_contribute_code(self):
        if self.current_char_cls is None:
            return
        url = CONTRIBUTE_CHAR_URL.format(class_name=self.current_char_cls.__name__)
        QDesktopServices.openUrl(QUrl(url))

    def _reload_live_char_code(self):
        if self.executor is None or self.current_char_cls is None:
            return 0
        new_cls = load_custom_char_class(self.current_char_cls)
        reloaded = 0
        tasks = list(getattr(self.executor, "onetime_tasks", [])) + list(getattr(self.executor, "trigger_tasks", []))
        for task in tasks:
            chars = getattr(task, "chars", None)
            if not chars:
                continue
            for index, char in enumerate(chars):
                if char is None:
                    continue
                if not isinstance(char, self.current_char_cls):
                    continue
                if type(char) is new_cls:
                    continue
                replacement = new_cls(
                    task,
                    char.index,
                    char_name=char.char_name,
                    confidence=char.confidence,
                    ring_index=char.ring_index,
                    char_type=char.char_type,
                    buff_time=char.buff_time,
                )
                replacement.is_current_char = char.is_current_char
                replacement.has_intro = char.has_intro
                replacement.has_sub_dps_intro = char.has_sub_dps_intro
                replacement.last_switch_time = char.last_switch_time
                replacement.last_switch_in_time = char.last_switch_in_time
                replacement.last_res = char.last_res
                replacement.last_echo = char.last_echo
                replacement.last_liberation = char.last_liberation
                replacement.last_buff_time = char.last_buff_time
                chars[index] = replacement
                reloaded += 1
        return reloaded

    def _update_char_image(self):
        self.char_image_label.clear()
        if not self.show_char_feature_image:
            return
        label_name = self.char_label_by_cls.get(self.current_char_cls)
        pixmap = self._get_char_feature_image(label_name)
        if pixmap is not None and not pixmap.isNull():
            self.char_image_label.setPixmap(pixmap)

    def _load_char_feature_index(self):
        feature_index = {}
        coco_path = Path("assets") / "coco_annotations.json"
        if not coco_path.exists():
            return feature_index
        try:
            data = json.loads(coco_path.read_text(encoding="utf-8"))
            image_by_id = {image["id"]: image["file_name"] for image in data.get("images", [])}
            category_by_id = {category["id"]: category["name"] for category in data.get("categories", [])}
            for annotation in data.get("annotations", []):
                category_name = category_by_id.get(annotation.get("category_id"))
                if not category_name:
                    continue
                image_name = image_by_id.get(annotation.get("image_id"))
                if not image_name:
                    continue
                bbox = annotation.get("bbox", [])
                if len(bbox) != 4:
                    continue
                feature_index[category_name] = (coco_path.parent / image_name, tuple(round(value) for value in bbox))
        except Exception as e:
            self.logger.error(f"load char feature image index failed: {e}")
        return feature_index

    def _clip_to_rounded_rect(self, pixmap, label_name):
        scaled = pixmap.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        out = QPixmap(48, 48)
        out.fill(Qt.transparent)
        p = QPainter(out)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        path = QPainterPath()
        path.addRoundedRect(0, 0, 48, 48, 14, 14)
        p.setClipPath(path)
        p.drawPixmap((48 - scaled.width()) // 2, (48 - scaled.height()) // 2, scaled)
        p.end()
        self.char_feature_images[label_name] = out
        return out

    def _get_char_feature_image(self, label_name):
        if not label_name:
            return None
        if label_name in self.char_feature_images:
            return self.char_feature_images[label_name]
        icon_path = Path("assets") / "char_icons" / f"{label_name}.webp"
        if icon_path.exists() and not (pixmap := QPixmap(str(icon_path))).isNull():
            return self._clip_to_rounded_rect(pixmap, label_name)
        if image_info := self.char_feature_index.get(label_name):
            image_path, bbox = image_info
            pixmap = self.char_source_pixmaps.get(image_path) or QPixmap(str(image_path))
            self.char_source_pixmaps[image_path] = pixmap
            cropped = pixmap.copy(*bbox)
            if not cropped.isNull():
                return self._clip_to_rounded_rect(cropped, label_name)
        return None

    def _label_name(self, label):
        if isinstance(label, tuple):
            label = label[0]
        return getattr(label, "value", label)

    def _display_char_name(self, char_cls):
        display_name = CHARACTER_DISPLAY_NAMES.get(char_cls.__name__, char_cls.__name__)
        return self.tr(display_name)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.show_char_feature_image:
            self.show_char_feature_image = True
            self._update_char_image()

    def hideEvent(self, event):
        if self._has_unsaved_changes():
            self._confirm_discard_changes()
        super().hideEvent(event)
