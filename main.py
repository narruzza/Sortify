from PyQt6.QtWidgets import QApplication
from Python.gui import SortifyApp
import sys

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SortifyApp()
    window.show()
    sys.exit(app.exec())