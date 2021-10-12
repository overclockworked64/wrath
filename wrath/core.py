import math
import typing as t

from wrath.util import slice_ranges

if t.TYPE_CHECKING:
    from wrath.cli import Port, Range
else:
    Port = Range = t.Any


async def main(
    target: str,
    interface: str,
    batch_size: int,
    ports: t.List[Port],
    ranges: t.List[Range]
) -> None:
    # slice the ranges into smaller batches of size <batch_size>
    sliced_ranges = slice_ranges(ranges, batch_size)
    ...
