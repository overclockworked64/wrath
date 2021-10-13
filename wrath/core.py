import contextlib
import itertools
import typing as t

import more_itertools
import trio
import tractor
from async_generator import aclosing


if t.TYPE_CHECKING:
    from wrath.cli import Port, Range
else:
    Port = Range = t.Any


async def receiver(
    sliced_ranges: t.List[Range],
    streams: t.List[tractor.MsgStream],
    workers: int = 4,
) -> t.AsyncGenerator[t.Dict[int, bool], None]:
    status = {
        port: False for sliced_range in sliced_ranges
        for port in range(*sliced_range)
    }

    yield status

    busy_workers = list(range(workers))

    await trio.sleep(1)

    while True:
        if not busy_workers:
            break
        for worker in reversed(busy_workers):
            try:
                if streams[worker].receive_nowait():
                    busy_workers.remove(worker)
            except trio.WouldBlock:
                continue


@tractor.context
async def batchworker(ctx: tractor.Context) -> None:
    await ctx.started()
    async with ctx.open_stream() as stream:
        async for batch in stream:
            for port in batch:
                ...
            await stream.send(True)


@contextlib.asynccontextmanager
async def open_actor_cluster(workers: int = 4) -> t.AsyncGenerator[t.List[tractor.Portal], None]:
    portals = []
    async with tractor.open_nursery() as tn:
        async with trio.open_nursery() as n:
            async def _start_actor(idx: int) -> None:
                portals.append(
                    await tn.start_actor(
                        f'batchworker {idx}',
                        enable_modules=[__name__]
                    )
                )
            
            for idx in range(workers):
                n.start_soon(_start_actor, idx)
    
        yield portals

        await tn.cancel()


@contextlib.asynccontextmanager
async def open_streams_from_portals(
    portals: t.List[tractor.Portal],
    all_done: trio.Event,
    workers: int = 4
) -> t.AsyncGenerator[t.List[tractor.Portal], None]:
    streams = []
    all_streams_opened = trio.Event()
    async with trio.open_nursery() as nursery:
        async def _open_stream(p: tractor.Portal) -> None:
            async with (
                p.open_context(batchworker) as (ctx, _),
                ctx.open_stream() as stream,
            ):
                streams.append(stream)
                if len(streams) == workers:
                    all_streams_opened.set()
                await all_done.wait()
                
        for p in portals:
            nursery.start_soon(_open_stream, p)

        await all_streams_opened.wait()

        yield streams


async def main(
    target: str,
    interface: str,
    batch_size: int,
    ports: t.List[Port],
    ranges: t.List[Range],
    workers: int = 4,
) -> None:
    all_done = trio.Event()
    async with (
        open_actor_cluster() as portals,
        open_streams_from_portals(portals, all_done) as streams,
    ):
        async with aclosing(receiver(ranges, streams)) as areceiver:  
            async for update in areceiver:
                ports = [*update]
                for (batch, stream) in zip(
                    more_itertools.sliced(ports, batch_size),
                    itertools.cycle(streams)
                ):  
                    await stream.send(batch)

        all_done.set()
