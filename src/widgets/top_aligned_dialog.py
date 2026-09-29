from PySide6.QtWidgets import QDialog


class TopAlignedDialog(QDialog):
    """宽度为主界面一半、高度贴合内容、水平居中且顶边与主界面对齐的对话框。
    供保存/设置等对话框复用，统一几何行为。"""

    def _setup_geometry(self):
        parent = self.parentWidget()
        window = parent.window() if parent else None
        if window is not None:
            # 高度取布局提示值，避免锁死在 QDialog 默认的 480px
            self.resize(int(window.width() / 2), max(self.sizeHint().height(), 120))

    def showEvent(self, event):
        super().showEvent(event)
        parent = self.parentWidget()
        window = parent.window() if parent else None
        if window is not None:
            center_x = window.geometry().center().x()
            self.move(center_x - self.width() // 2, window.frameGeometry().top())
