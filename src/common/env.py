"""Utilitários de ambiente: funcionam no Colab e localmente."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def in_colab() -> bool:
    return "google.colab" in sys.modules


def load_config(path: Path | None = None) -> dict:
    path = path or REPO_ROOT / "configs" / "project.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def drive_paths(drive_mount: Path, config: dict | None = None) -> dict[str, Path]:
    """Mapeia nome -> pasta no Drive (ex.: /content/drive/MyDrive/MensagemAstral/books)."""
    config = config or load_config()
    root = Path(drive_mount) / config["drive_root"]
    paths = {"root": root}
    paths.update({name: root / name for name in config["drive_subdirs"]})
    return paths


def ensure_dirs(paths: dict[str, Path]) -> None:
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)


def resource_report(disk_path: str = "/") -> dict:
    """RAM, disco e GPU disponíveis (para escolher o LLM nas etapas seguintes)."""
    info: dict = {}
    try:
        import os
        info["ram_gb"] = round(
            os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3, 1
        )
    except (ValueError, OSError, AttributeError):
        info["ram_gb"] = None
    info["disk_free_gb"] = round(shutil.disk_usage(disk_path).free / 1024**3, 1)
    try:
        import torch
        if torch.cuda.is_available():
            p = torch.cuda.get_device_properties(0)
            info["gpu"] = p.name
            info["gpu_mem_gb"] = round(p.total_memory / 1024**3, 1)
        else:
            info["gpu"] = None
    except ImportError:
        info["gpu"] = "torch não instalado"
    return info
