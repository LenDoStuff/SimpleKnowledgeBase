import tomllib
from pathlib import Path


def test_claim_file_splitter_is_not_external_dependency():
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]

    assert not any(dependency.startswith("claim-file-splitter") for dependency in dependencies)
    assert "Pillow>=9.1.0" in dependencies
    assert "pypdf>=5.0.0" in dependencies
    assert "openai>=1.80.0" in dependencies
