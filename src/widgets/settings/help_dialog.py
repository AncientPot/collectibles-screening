from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from src.utils.set_layout import set_layout

# 参数说明表：(标题, 说明) —— 界面按块渲染，每块一个标题加一段说明
PARAMETERS: list[tuple[str, str]] = [
    ("最长监听时长（秒）",
     "单次监听录音的上限，到时自动结束并触发比对。"),
    ("播放音量（倍）",
     "基准音频的播放放大倍率，1.0 为不做处理播放原始音频。基准录音本身很轻，听不清可调大。"),
    ("学习数据权重（0-1）",
     "保存的学习数据参与比对的强度：\n"
     "0 = 不使用学习数据\n"
     "0.5 = 默认微调力度\n"
     "1.0 = 学习数据与保底模板平权\n"
     "三层权重中保底模板始终主导，原始基准次之。"),
    ("学习音频上限",
     "每个类别最多保留的学习音频数量，超出上限时自动删除最旧的。下拉选择类别后在输入框修改对应数量。"),
    ("监听 / 置顶快捷键",
     "点录制后按下新键立即生效，按 Esc 取消录制。录制期间原有热键暂时挂起，不会误触发。"),
    ("重建保底模板",
     "更换音频设备或驱动后使用。点击后依次播放 10 个基准音并环回采集（约 20 秒，期间请保持安静），完成后立即生效。"),
]

_BODY_COLOR = QColor("#555555")


class HelpDialog(QDialog):
    """参数说明对话框：按参数分块展示"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("参数说明")
        self._setup_ui()

    def _setup_ui(self):
        """组装ui"""
        layout = set_layout(QVBoxLayout(self), 16, 16, 16, 16, 4)
        for index, (title, text) in enumerate(PARAMETERS):
            if index:
                layout.addSpacing(10)
            title_label = QLabel(title)
            body_label = QLabel(text)
            body_label.setWordWrap(True)
            palette = body_label.palette()
            palette.setColor(QPalette.ColorRole.WindowText, _BODY_COLOR)
            body_label.setPalette(palette)
            body_label.setContentsMargins(8, 0, 0, 0)
            layout.addWidget(title_label)
            layout.addWidget(body_label)
        layout.addSpacing(12)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
