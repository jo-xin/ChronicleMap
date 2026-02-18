# chroniclemap/gui/__main__.py
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from .campaign_manager import CampaignManagerView
from .campaign_store import CampaignStore


def main():
    app = QApplication(sys.argv)
    # default data root in user's home for demo; override as needed
    home = Path.home() / ".chroniclemap_data"
    store = CampaignStore(home)
    w = CampaignManagerView(store)
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
