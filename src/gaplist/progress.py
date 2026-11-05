"""Tell the user what is happening while a step runs.

In the notebook, ``say`` prints a time-stamped line straight away, and
``bar`` shows a progress bar (a graphical one in JupyterLab, a text one
elsewhere). Both can be switched off, which the tests do.
"""

from __future__ import annotations

import time
from contextlib import nullcontext

from tqdm.auto import tqdm

ENABLED = True


def say(message: str) -> None:
    if ENABLED:
        print(f"{time.strftime('%H:%M:%S')}  {message}", flush=True)


def bar(total: int | None, description: str, unit: str = "it"):
    """A progress bar; use as ``with bar(...) as b: b.update(n)``.

    unit "B" shows sizes in KB, MB and GB.
    """
    if not ENABLED:
        return nullcontext(_Silent())
    return tqdm(
        total=total,
        desc=description,
        unit=unit,
        unit_scale=True,
        unit_divisor=1024 if unit == "B" else 1000,
        mininterval=0.5,
    )


class _Silent:
    def update(self, n: int = 1) -> None:
        pass
