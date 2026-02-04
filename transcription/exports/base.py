# transcriptions/exports/base.py

from abc import ABC, abstractmethod

class BaseExporter(ABC):

    @abstractmethod
    def export(self, segments, options):
        """
        segments: list of structured segment dicts
        options: export options dict
        returns: bytes
        """
        pass
