import contextlib
import itertools
import typing as t

import more_itertools
import trio
import tractor
from tractor import open_actor_cluster
from tractor.trionics import gather_contexts
from async_generator import aclosing

from wrath.net import build_ipv4_datagram
from wrath.net import build_tcp_segment
from wrath.net import create_send_sock
from wrath.net import create_recv_sock
from wrath.net import unpack
from wrath.net import SYNACK, RSTACK

if t.TYPE_CHECKING:
    from wrath.cli import Port, Range
else:
    Port = Range = t.Any


async def receiver(
    ranges: list[Range],
    streams: list[tractor.MsgStream],
    interface: str,
    target: str,
    workers: int = 4,
) -> t.AsyncGenerator[dict[int, bool], None]:
    status = {
        port: False for r in ranges for port in range(*r)
    }

    recv_sock = create_recv_sock(target)
    await recv_sock.bind((interface, 0x0800))

    # trigger the machinery
    yield status

    while not recv_sock.is_readable():
        await trio.sleep(0.1)

    busy_workers = list(range(workers))

    while True:
        with trio.move_on_after(0.01) as cancel_scope:
            response = await recv_sock.recv(1024 * 16)
        if cancel_scope.cancelled_caught:
            for worker in busy_workers[:]:
                try:
                    if streams[worker].receive_nowait():
                        busy_workers.remove(worker)
                except trio.WouldBlock:
                    continue
            if not busy_workers:
                busy_workers = list(range(workers))
                yield {k: v for k, v in status.items() if not v}
        else:
            src, flags = unpack(response)
            if status[src]:
                # Upon receiving a SYN/ACK or RST/ACK, sometimes the kernel fails
                # to send RST back for some reason which leads to retransmission
                # of the packet. By choosing to discard the packet and continue,
                # we prevent reporting duplicate packets.
                continue
            if flags == SYNACK:
                print(f"{src}: open")
                status[src] = True
            elif flags == RSTACK:
                # print(f"{src}: closed")
                status[src] = True


@tractor.context
async def batchworker(ctx: tractor.Context, interface: str, target: str) -> None:
    await ctx.started()
    ipv4_datagram = build_ipv4_datagram(interface, target)
    send_sock = create_send_sock()
    async with ctx.open_stream() as stream:
        async for batch in stream:
            for port in batch:
                tcp_segment = build_tcp_segment(interface, target, port)
                await send_sock.sendto(ipv4_datagram + tcp_segment, (target, port))
            # Let the receiver know that the worker is done sending.
            await stream.send(True)
    send_sock.close()


async def main(
    target: str,
    interface: str,
    ports: list[Port],
    ranges: list[Range],
    workers: int = 4,
) -> None:
    async with (
        open_actor_cluster(modules=[__name__]) as portals,
        gather_contexts([
            p.open_context(batchworker, interface=interface, target=target)
            for p in portals.values()
        ]) as contexts,
        gather_contexts([ctx[0].open_stream() for ctx in contexts]) as streams,
        aclosing(receiver(ranges, streams, interface, target)) as areceiver,
    ):
        async for update in areceiver:
            ports = [*update]
            if not ports:
                break
            for (batch, stream) in zip(
                more_itertools.sliced(ports, len(ports) // workers),
                itertools.cycle(streams)
            ):
                await stream.send(batch)
