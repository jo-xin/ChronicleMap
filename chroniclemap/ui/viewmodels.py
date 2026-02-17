# chroniclemap/ui/viewmodels.py
from __future__ import annotations

from typing import List

from PySide6.QtCore import QObject, Signal, Slot

from chroniclemap.core.models import Campaign


class AppViewModel(QObject):
    """
    Global app-level viewmodel. Emits when campaigns list updates or campaign opened.
    """

    campaigns_changed = Signal(list)  # list of campaign names
    campaign_opened = Signal(object)  # Campaign instance

    def __init__(self, storage_service):
        super().__init__()
        self.storage = storage_service
        self._campaigns_cache: List[str] = []

    @Slot()
    def refresh_campaigns(self):
        names = list(self.storage.list_campaigns())
        self._campaigns_cache = names
        self.campaigns_changed.emit(names)

    @Slot(str)
    def create_campaign(self, name: str):
        camp = self.storage.create_campaign(name)
        self.refresh_campaigns()
        self.open_campaign(camp)

    @Slot(str)
    def delete_campaign(self, name: str):
        self.storage.delete_campaign(name)
        self.refresh_campaigns()

    @Slot(str)
    def open_campaign_by_name(self, name: str):
        camp = self.storage.load_campaign(name)
        self.open_campaign(camp)

    def open_campaign(self, campaign: Campaign):
        self.campaign_opened.emit(campaign)


class CampaignViewModel(QObject):
    """
    Minimal campaign-scoped viewmodel placeholder. UI binds to this when a campaign is opened.
    """

    snapshots_changed = Signal()
    rulers_changed = Signal()
    metadata_changed = Signal()

    def __init__(self, campaign: Campaign, storage_service):
        super().__init__()
        self.campaign = campaign
        self.storage = storage_service

    def reload(self):
        # reload from disk
        self.campaign = self.storage.load_campaign(self.campaign.path)
        self.snapshots_changed.emit()
        self.rulers_changed.emit()
        self.metadata_changed.emit()
