# premis_logger.py
import json, uuid, datetime
from pathlib import Path
from typing import Any, Dict

_ARQ = Path("logs_premis.jsonl")  # 1 evento por linha

def _now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")

def registrar_evento(event_type: str,
                     object_id: str,
                     detail: Dict[str, Any],
                     outcome: str = "OK"):
    """
    Grava um evento PREMIS mínimo (type, dateTime, outcome) em JSON Lines.
    detail = dados específicos (ex.: parâmetros de cópia, paths etc.).
    """
    evento = {
        "eventIdentifier": str(uuid.uuid4()),
        "eventType": event_type,          # Ex.: copy, move, rename
        "eventDateTime": _now_iso(),
        "eventDetail": detail,
        "eventOutcomeInformation": outcome,
        "linkedObjectIdentifier": object_id  # Ex.: SHA-256 do arquivo
    }
    _ARQ.parent.mkdir(exist_ok=True)
    with _ARQ.open("a", encoding="utf-8") as f:
        json.dump(evento, f, ensure_ascii=False)
        f.write("\n")
