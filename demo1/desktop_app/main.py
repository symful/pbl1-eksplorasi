import sys
import os

# Ensure we can import from project root
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, ".."))
sys.path.insert(0, _PROJECT_ROOT)

from PyQt5.QtWidgets import QApplication
import qdarktheme

from desktop_app.ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    
    # Setup professional dark theme using qdarktheme
    app.setStyleSheet(qdarktheme.load_stylesheet("dark"))
    
    # Initialize and show main window
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
