import io
import zipfile
from pathlib import Path

from app.importers.source_factory import (
    create_chatgpt_source_from_zip,
)


def test_create_chatgpt_source_from_zip():
    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "chatgpt"
        / "conversations.json"
    )

    json_bytes = fixture_path.read_bytes()

    buffer = io.BytesIO()

    with zipfile.ZipFile(
        buffer,
        mode="w",
    ) as archive:
        archive.writestr(
            "conversations.json",
            json_bytes,
        )

    source = create_chatgpt_source_from_zip(
        buffer.getvalue()
    )

    assert len(source.conversations) == 2
    assert source.conversations[0]["title"] == "Center a div"


def test_create_chatgpt_source_rejects_invalid_zip():
    try:
        create_chatgpt_source_from_zip(
            b"not a zip file"
        )
    except ValueError as exc:
        assert str(exc) == "Invalid ZIP archive"
    else:
        raise AssertionError(
            "Expected ValueError"
        )
