import os
import re
import stat
from pathlib import Path
from uuid import uuid4

from app.evaluation.schemas import Dataset, EvaluationError, canonical_bytes

PRIVATE_ROOT = Path(__file__).resolve().parents[2] / ".local" / "evaluation"
MAX_DATASET_BYTES = 2 * 1024 * 1024


def check_path(path: Path, root: Path):
    path, root = path.absolute(), root.absolute()
    if ".." in path.parts or not path.is_relative_to(root) or path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise EvaluationError("UNSAFE_PATH")
    return path


def private_directory(path: Path, root: Path):
    path = check_path(path, root)
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    root.chmod(0o700)
    path.chmod(0o700)
    for parent in path.parents:
        if parent.is_relative_to(root):
            parent.chmod(0o700)
    return path


def write_private(path: Path, value, *, root: Path):
    path = check_path(path, root)
    private_directory(path.parent, root)
    raw = value if isinstance(value, bytes) else canonical_bytes(value)
    temporary = path.with_name("." + uuid4().hex + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        # Publishing a complete file must never replace an existing revision/report.
        os.link(temporary, path, follow_symlinks=False)
    except FileExistsError:
        raise EvaluationError("OUTPUT_EXISTS") from None
    finally:
        temporary.unlink(missing_ok=True)


def read_private(path: Path, root: Path):
    import json
    path = check_path(path, root)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise EvaluationError("UNSAFE_INPUT")
        raw = stream.read(MAX_DATASET_BYTES + 1)
    if len(raw) > MAX_DATASET_BYTES:
        raise EvaluationError("DATASET_BUDGET")
    return json.loads(raw)


def save_dataset(directory: Path, dataset: Dataset, *, root: Path = PRIVATE_ROOT):
    if len(canonical_bytes(dataset.model_dump(mode="json"))) > MAX_DATASET_BYTES:
        raise EvaluationError("DATASET_BUDGET")
    write_private(directory / f"revision-{dataset.revision:06d}.json", dataset.model_dump(mode="json"), root=root)


def load_dataset(directory: Path, *, revision: int | None = None, root: Path = PRIVATE_ROOT) -> Dataset:
    directory = check_path(directory, root)
    files = list(directory.glob("revision-*.json"))
    numbers = []
    for file in files:
        match = re.fullmatch(r"revision-([0-9]{6})\.json", file.name)
        if not match:
            raise EvaluationError("REVISION_CHAIN")
        numbers.append(int(match[1]))
    if not numbers or len(numbers) > 1000:
        raise EvaluationError("REVISION_CHAIN")
    target = revision if revision is not None else max(numbers)
    if target not in numbers or not 1 <= target <= 1000:
        raise EvaluationError("REVISION_CHAIN")
    previous = None
    for number in range(1, target + 1):
        current = Dataset.model_validate(read_private(directory / f"revision-{number:06d}.json", root))
        if current.revision != number or (previous and (current.parent_digest != previous.digest or
                current.set_id != previous.set_id or current.owner_id != previous.owner_id or
                current.owner_email != previous.owner_email or current.database_fingerprint != previous.database_fingerprint or
                current.material_kind != previous.material_kind)):
            raise EvaluationError("REVISION_CHAIN")
        previous = current
    return previous
