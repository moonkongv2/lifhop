from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from app.importers.canonical import CanonicalItem


SourceT = TypeVar("SourceT")


class Importer(ABC, Generic[SourceT]):
    @abstractmethod
    def import_data(self, source: SourceT) -> list[CanonicalItem]:
        pass
