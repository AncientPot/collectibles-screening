
def set_layout(layout, left=0, top=0, right=0, bottom=0, spacing=0):
    """设置布局的边距和间距"""
    layout.setContentsMargins(left, top, right, bottom)
    layout.setSpacing(spacing)
    return layout