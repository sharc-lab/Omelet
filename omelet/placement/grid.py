from __future__ import annotations

import math
from typing import List, Tuple


def mesh_grid(n: int) -> List[Tuple[int, int]]:
    rows = math.isqrt(n)
    while rows * rows < n:
        rows += 1
    cols = rows
    return [divmod(i, cols) for i in range(n)]
