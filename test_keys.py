import sys
from PyQt6.QtWidgets import QApplication, QWidget, QLineEdit, QVBoxLayout
from PyQt6.QtCore import QEvent, Qt

class Terminal(QWidget):
    def __init__(self):
        super().__init__()
        self.input_area = QLineEdit(self)
        layout = QVBoxLayout(self)
        layout.addWidget(self.input_area)
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            if obj != self.input_area:
                print(f"Key press on {obj}, key: {event.text()}")
                self.input_area.setFocus()
                QApplication.sendEvent(self.input_area, event)
                return True
        return super().eventFilter(obj, event)

app = QApplication(sys.argv)
win = QWidget()
layout = QVBoxLayout(win)
term = Terminal()
layout.addWidget(term)
dummy = QLineEdit() # to steal focus
layout.addWidget(dummy)
# win.show()
# sys.exit(app.exec())
print("Syntax OK")
