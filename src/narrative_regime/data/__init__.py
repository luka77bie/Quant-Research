"""Market-data acquisition, validation, and provenance."""

from narrative_regime.data.downloader import DownloadManager
from narrative_regime.data.models import FetchRequest, FetchResult

__all__ = ["DownloadManager", "FetchRequest", "FetchResult"]

