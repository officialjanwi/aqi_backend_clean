from typing import Dict, Any

_latest: Dict[str, Any] = {}

def set_latest(data: Dict[str, Any]):
    global _latest
    _latest = data

def get_latest() -> Dict[str, Any]:
    return _latest