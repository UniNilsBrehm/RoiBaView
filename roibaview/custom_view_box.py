from PyQt6.QtWidgets import QMenu


class CustomViewBoxMenu(QMenu):
    def __init__(self, viewbox, parent=None):
        super().__init__(parent)
        self.viewbox = viewbox
        self.setTitle("Custom ViewBox Menu")

        self.addAction("Action 1", self.action1_triggered)
        self.addAction("Action 2", self.action2_triggered)

    def action1_triggered(self):
        print("Action 1 triggered")

    def action2_triggered(self):
        print("Action 2 triggered")
