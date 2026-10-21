"""Settings discovery must not depend on a worker's working directory."""
import os
from pathlib import Path
import subprocess
import sys

from app.config import Settings


def test_repository_dotenv_is_loaded_from_another_directory(tmp_path):
    project = tmp_path / "project"
    app = project / "app"
    app.mkdir(parents=True)
    config = app / "config.py"
    config.write_text((Path(__file__).resolve().parents[1] / "app/config.py").read_text())
    (project / ".env").write_text(
        "DATABASE_URL=postgresql+psycopg://synthetic/project_test\n"
        "JWT_SECRET_KEY=synthetic-project-secret\nAWS_REGION=ap-northeast-2\n"
    )
    working = tmp_path / "elsewhere"
    working.mkdir()
    (working / ".env").write_text(
        "DATABASE_URL=postgresql+psycopg://synthetic/wrong_test\n"
        "JWT_SECRET_KEY=synthetic-wrong-secret\nAWS_REGION=wrong-region\n"
    )
    env = {k: v for k, v in os.environ.items() if k.lower() not in Settings.model_fields}
    probe = (
        "import runpy, sys; settings = runpy.run_path(sys.argv[1])['settings']; "
        "assert settings.database_url == 'postgresql+psycopg://synthetic/project_test'; "
        "assert settings.jwt_secret_key == 'synthetic-project-secret'; "
        "assert settings.aws_region == 'ap-northeast-2'"
    )
    result = subprocess.run([sys.executable, "-c", probe, str(config)],
        cwd=working, env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    # Explicit process settings still take precedence over the repository file.
    env["AWS_REGION"] = "synthetic-runtime-region"
    result = subprocess.run([sys.executable, "-c",
        "import runpy, sys; assert runpy.run_path(sys.argv[1])['settings'].aws_region == 'synthetic-runtime-region'",
        str(config)], cwd=working, env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
