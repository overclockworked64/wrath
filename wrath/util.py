import math
import typing as t

if t.TYPE_CHECKING:
    from wrath.cli import Range
else:
    Range = t.Any


def slice_ranges(ranges: t.List[Range], batch_size: int) -> t.List[Range]:
    sliced_ranges = []

    for r in ranges:
        start, end = r
        rangelen = len(range(start, end))
        if rangelen > batch_size:
            for index in range(math.ceil(rangelen / batch_size)):
                if index == rangelen // batch_size:
                    sliced_range = (start, end + 1)  # end is inclusive
                else:
                    sliced_range = (start, start + batch_size)
                    start += batch_size
                sliced_ranges.append(sliced_range)
        else:
            sliced_ranges.append(r)
    
    return sliced_ranges