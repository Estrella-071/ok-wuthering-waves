import difflib
import json
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QPixmap, QTextCursor, QTextFormat, QPainter, QPainterPath
from PySide6.QtWidgets import QApplication, QButtonGroup, QHBoxLayout, QLabel, QListWidgetItem, QSplitter, QTextEdit, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, SubtitleLabel, FluentIcon, ListWidget, MessageBox, PlainTextEdit, PrimaryPushButton, PushButton, RadioButton, SegmentedWidget

from ok.gui.tasks.EditTaskTab import CodeEditor
from ok.gui.tasks.PythonHighlighter import PythonHighlighter

class DummyRadio:
    def __init__(self, tab, mode):
        self.tab = tab
        self.mode = mode

    def isChecked(self):
        return self.tab.mode_segmented.currentRouteKey() == self.mode

    def setChecked(self, checked):
        if checked:
            old_guard = self.tab.suppress_mode_guard
            self.tab.suppress_mode_guard = True
            self.tab.mode_segmented.setCurrentItem(self.mode)
            self.tab.suppress_mode_guard = old_guard
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
        layout.setContentsMargins(12, 8, 12, 8)
        
        self.name_label = BodyLabel(display_name, self)
        self.file_label = BodyLabel(file_name, self)
        self.file_label.setStyleSheet("color: #8c8c8c; font-size: 12px;")
        
        layout.addWidget(self.name_label)
        layout.addStretch()
        layout.addWidget(self.file_label)
        
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)


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

        # Single compact row layout integrating title, avatar, switcher and buttons
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        self.char_image_label = QLabel()
        self.char_image_label.setFixedSize(32, 32)
        self.char_image_label.setAlignment(Qt.AlignCenter)
        self.char_image_label.setScaledContents(True)
        # Apply premium circular avatar border style
        self.char_image_label.setStyleSheet("border-radius: 16px; border: 1px solid rgba(0, 0, 0, 15);")
        
        title_label = SubtitleLabel(self.tr("Character Code"))
        
        self.mode_segmented = SegmentedWidget(right)
        self.mode_segmented.addItem("builtin", self.tr("Use built in"), self._mode_changed)
        self.mode_segmented.addItem("custom", self.tr("Use custom"), self._mode_changed)
        
        self.builtin_radio = DummyRadio(self, "builtin")
        self.custom_radio = DummyRadio(self, "custom")

        self.ask_ai_button = PushButton(FluentIcon.ROBOT, self.tr("Ask AI"))
        self.ask_ai_button.clicked.connect(self._copy_ask_ai_template)
        self.how_to_button = PushButton(FluentIcon.HELP, self.tr("How To"))
        self.how_to_button.clicked.connect(self._show_how_to)
        self.contribute_button = PushButton(FluentIcon.GITHUB, self.tr("Contribute Code"))
        self.contribute_button.clicked.connect(self._open_contribute_code)

        header_layout.addWidget(self.char_image_label)
        header_layout.addWidget(title_label)
        header_layout.addWidget(self.mode_segmented)
        header_layout.addStretch(1)
        header_layout.addWidget(self.ask_ai_button)
        header_layout.addWidget(self.how_to_button)
        header_layout.addWidget(self.contribute_button)
        
        right_layout.addLayout(header_layout)

        self.editor = CodeEditor(right)
        self.editor.setMinimumHeight(520)
        self.editor.setLineWrapMode(PlainTextEdit.NoWrap)
        font = self.editor.font()
        font.setFamily("Consolas")
        font.setPointSize(11)
        self.editor.setFont(font)
        self.highlighter = PythonHighlighter(self.editor.document())
        self.editor.textChanged.connect(self._editor_text_changed)
        right_layout.addWidget(self.editor, 1)

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
        self.custom_radio.setChecked(enabled)
        self.builtin_radio.setChecked(not enabled)
        self._update_char_image()
        self._load_editor_code()
        self.status_label.setText(str(has_custom_char_code(char_cls) and self.tr("Custom code saved") or ""))

    def _sync_editor_state(self):
        self.editor.setReadOnly(self.builtin_radio.isChecked())
        self.reset_button.setVisible(self.custom_radio.isChecked())
        self.save_button.setVisible(self.custom_radio.isChecked())

    def _mode_changed(self):
        if self.suppress_mode_guard:
            return
        if self.current_char_cls is None:
            return
        if self.builtin_radio.isChecked() and self._has_unsaved_changes():
            if not self._confirm_discard_changes():
                self.suppress_mode_guard = True
                self.custom_radio.setChecked(True)
                self.suppress_mode_guard = False
                self._sync_editor_state()
                return
        self._load_editor_code()

    def _load_editor_code(self):
        if self.current_char_cls is None:
            return
        if self.custom_radio.isChecked():
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
        return self.custom_radio.isChecked() and self.editor.toPlainText() != self.clean_code

    def _confirm_discard_changes(self):
        box = MessageBox(
            self.tr("Unsaved Changes"),
            self.tr("Discard unsaved character code changes?"),
            self.window(),
        )
        return bool(box.exec())

    def _highlight_changed_lines(self):
        if self.current_char_cls is None or self.builtin_radio.isChecked():
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
            if self.custom_radio.isChecked():
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
        self.builtin_radio.setChecked(True)
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
