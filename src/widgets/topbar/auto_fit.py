from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QComboBox, QSizePolicy


class AutoFitComboBox(QComboBox):
    """按内容自适应宽度、不吸收布局富余宽度的下拉框。

    弹窗加固（针对 Windows 上偶发的首帧透明/无文字列表）：
    点击小三角时弹窗在鼠标按下的同步调用栈里创建原生窗口，窗口尚未
    进入合成链时任何绘制都无法上屏，表现为"透明长条，再点一下才出现"。
    解法是把真正的弹出动作延后一个事件循环——按下/抬起流程完全结束、
    窗口管理器就绪后再开窗，并在开窗后同步重排与重绘。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self._popup_pending = False

    def showPopup(self):
        if self._popup_pending:
            return
        self._popup_pending = True
        QTimer.singleShot(0, self._show_popup_deferred)

    def _show_popup_deferred(self):
        self._popup_pending = False
        if not self.isEnabled():
            return
        self.ensurePolished()
        super().showPopup()
        view = self.view()
        view.doItemsLayout()
        view.repaint()
        container = view.parentWidget()
        if container is not None:
            container.repaint()

    def hidePopup(self):
        self._popup_pending = False
        super().hidePopup()
