import pytest

from app.importers.base import Importer


def test_importer_cannot_be_instantiated():
    with pytest.raises(TypeError):
        Importer()


def test_incomplete_importer_cannot_be_instantiated():
    class IncompleteImporter(Importer):
        pass

    with pytest.raises(TypeError):
        IncompleteImporter()


def test_complete_importer_can_be_instantiated():
    class StringImporter(Importer[str]):
        def import_data(self, source: str):
            return []

    importer = StringImporter()

    assert importer.import_data("hello") == []
