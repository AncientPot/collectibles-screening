from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget

from src.utils.set_layout import set_layout
from src.widgets.topbar.format_selector import FormatSelector
from src.widgets.topbar.listen_button import ListenButton
from src.widgets.topbar.play_button import PlayButton
from src.widgets.topbar.save_button import SaveButton
from src.widgets.topbar.settings_button import SettingsButton
from src.widgets.topbar.type_selector import TypeSelector
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
        self.unify_combo_widths()

    def unify_combo_widths(self):
        """三个下拉框统一为相同宽度（取各自内容所需的最大值）。
        声音类别在启动后才填充，填充完需再调用一次；OnFirstShow 策略的
        sizeHint 首次读取即缓存、增删项不失效，须临时切 AdjustToContents
        强制按当前内容重算。"""
        combos = [
            self.type_selector.combo_box,
            self.format_selector.combo_box,
            self.sound_indicator.category_combo_box,
        ]
        for combo in combos:
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        uniform_width = max(combo.sizeHint().width() for combo in combos)
        for combo in combos:
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
            combo.setFixedWidth(uniform_width)
