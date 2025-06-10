"""
plugin_loader.py – DigitArq
---------------------------
Descobre plugins de duas formas:

1. Pastas locais em <projeto>/plugins/<meu_plugin>/meta.json
2. Pacotes instalados via pip que declaram entry-point no grupo
   'digitarq.plugins'

Retorna lista de dicts: [{"name", "run", "module"}, ...].

Compatível com Python 3.7 + (usa API antiga de importlib.metadata).
"""

from __future__ import annotations

import importlib
import importlib.metadata as md
import json
from pathlib import Path
from types import ModuleType
from typing import Dict, List, Optional

PLUGIN_ENTRY_GROUP = "digitarq.plugins"


# ------------------------------------------------------------------
# Funções auxiliares
# ------------------------------------------------------------------
def _load_local_manifests(plugin_dir: Path) -> List[Dict]:
    """Carrega todos os plugins/*/meta.json que conseguir ler."""
    manifests: List[Dict] = []
    if not plugin_dir.exists():
        return manifests

    for meta_path in plugin_dir.glob("*/meta.json"):
        try:
            manifests.append(json.loads(meta_path.read_text(encoding="utf-8")))
        except Exception:
            # ignora JSON mal-formado
            continue
    return manifests


def _resolve_entry_points() -> List[md.EntryPoint]:
    """
    Devolve entry-points do grupo 'digitarq.plugins' para
    Python 3.9 (API antiga) e 3.10+ (API nova).
    """
    try:
        # Python 3.10+: entry_points().select(group=...)
        return list(md.entry_points().select(group=PLUGIN_ENTRY_GROUP))
    except AttributeError:
        # Python 3.9: entry_points() → dict-like
        return list(md.entry_points().get(PLUGIN_ENTRY_GROUP, []))


# ------------------------------------------------------------------
# API pública
# ------------------------------------------------------------------
def discover_plugins(plugin_dir: Optional[Path] = None) -> List[Dict]:
    """
    Descobre plugins e devolve:
        [{"name", "run", "module"}, ...]
    """
    plugins: List[Dict] = []

    # 1) Plugins instalados via pip (entry-points)
    for ep in _resolve_entry_points():
        try:
            mod: ModuleType = importlib.import_module(ep.module)
            run_callable = getattr(mod, getattr(ep, "attr", "run"))
            plugins.append({"name": ep.name, "run": run_callable, "module": mod})
        except Exception:
            # entry-point quebrado → ignora
            continue

    # 2) Plugins locais em ./plugins/
    if plugin_dir:
        for meta in _load_local_manifests(plugin_dir):
            try:
                mod = importlib.import_module(meta["module"])
                run_callable = getattr(mod, meta.get("entry", "run"))
                plugins.append({"name": meta["name"], "run": run_callable, "module": mod})
            except Exception:
                continue

    return plugins
