from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from src.utils.set_layout import set_layout
from src.widgets.button.format_selector import FormatSelector
from src.widgets.button.listen_button import ListenButton
from src.widgets.button.play_button import PlayButton
from src.widgets.button.save_button import SaveButton
from src.widgets.button.settings_button import SettingsButton
from src.widgets.button.type_selector import TypeSelector
from src.widgets.sound_indicator import SoundIndicator


class TopBar(QWidget):
    """顶部按钮栏"""

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        """组装ui"""
        layout = set_layout(QHBoxLayout(self))
        self.type_selector = TypeSelector()
        layout.addWidget(self.type_selector)
        self.format_selector = FormatSelector()
        layout.addWidget(self.format_selector)
        self.sound_indicator = SoundIndicator()
        layout.addWidget(self.sound_indicator)
        self.play_button = PlayButton()
        layout.addWidget(self.play_button)
        self.listen_button = ListenButton()
        layout.addWidget(self.listen_button)
        self.probability_label = QLabel()
        self.probability_label.setMinimumWidth(48)
        layout.addWidget(self.probability_label)
        layout.addStretch(1)
        self.save_button = SaveButton()
        layout.addWidget(self.save_button)
        self.settings_button = SettingsButton()
        layout.addWidget(self.settings_button)
