import time
from typing import Callable, Any


def wait_for(fn: Callable[[], Any], timeout_sec: float, interval_sec: float = 1.0):
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        result = fn()
        if result is not None:
            return result
        time.sleep(interval_sec)
    return None
