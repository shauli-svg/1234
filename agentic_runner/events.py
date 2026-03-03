import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass
class Event:
    ts: float
    kind: str
    data: Dict[str, Any]


class EventLog:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, kind: str, **data: Any) -> None:
        event = Event(ts=time.time(), kind=kind, data=data)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
