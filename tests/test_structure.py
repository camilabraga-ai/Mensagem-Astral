from pathlib import Path

from src.common.env import REPO_ROOT, drive_paths, ensure_dirs, load_config, resource_report


def test_repo_structure():
    for d in ["notebooks", "src/astrology", "src/data", "src/rag", "src/models",
              "src/evaluation", "data", "configs", "tests", "docs"]:
        assert (REPO_ROOT / d).is_dir(), d


def test_gitignore_protects_sensitive_files():
    text = (REPO_ROOT / ".gitignore").read_text()
    for pattern in ["*.pdf", ".env", "*.safetensors", "birth_data*.json"]:
        assert pattern in text


def test_drive_paths_created(tmp_path: Path):
    cfg = load_config()
    paths = drive_paths(tmp_path, cfg)
    ensure_dirs(paths)
    for name in cfg["drive_subdirs"]:
        assert paths[name].is_dir()


def test_resource_report_keys():
    r = resource_report()
    assert {"ram_gb", "disk_free_gb", "gpu"} <= r.keys()
