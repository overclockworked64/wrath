import itertools
import math
import typing as t
from multiprocessing import cpu_count

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
from wrath.net import Flags

if t.TYPE_CHECKING:
    from wrath.cli import Port, Range
else:
    Port = Range = t.Any


async def receiver(
    ranges: list[Range],
    streams: tuple[tractor.MsgStream],
    interface: str,
    target: str,
    max_retries: int,
    workers: int = cpu_count(),
) -> t.AsyncGenerator[
    dict[int, dict[str, t.Union[int, bool]]], None
]:
    recv_sock = create_recv_sock(target)
    await recv_sock.bind((interface, 0x0800))

    status = {
        port: {'sent': 0, 'recv': False}
        for r in ranges for port in range(*r)
    }

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
                    sent_batch = streams[worker].receive_nowait()
                    for port in sent_batch:
                        try:
                            if status[port]['sent'] < max_retries:
                                status[port]['sent'] += 1
                            else:
                                print(f'{port}: filtered')
                                del status[port]
                        except KeyError:
                            # the port has already been inspected
                            continue
                    busy_workers.remove(worker)
                except trio.WouldBlock:
                    continue
            # If all of the workers are done sending, yield control
            # to the parent so that more ports can be dispatched.
            if not busy_workers:
                busy_workers = list(range(workers))
                yield {
                    k: v for k, v in status.items()
                    if not v['recv'] and v['sent'] < max_retries
                }
        else:
            src, flags = unpack(response)
            if status[src]['recv']:
                # Upon receiving a SYN/ACK or RST/ACK, sometimes the kernel fails
                # to send RST back for some reason which leads to retransmission
                # of the packet. By choosing to discard the packet and continue,
                # we prevent reporting duplicate packets.
                continue

            match flags:
                case Flags.SYNACK:
                    print(f"{src}: open")
                    status[src]['recv'] = True
                case Flags.RSTACK:
                    print(f"{src}: closed")
                    status[src]['recv'] = True
                case _: 
                    pass

@tractor.context
async def batchworker(
    ctx: tractor.Context,
    interface: str,
    target: str,
    batch_size: int,
    nap_duration: int,
) -> None:
    await ctx.started()
    ipv4_datagram = build_ipv4_datagram(interface, target)
    send_sock = create_send_sock()
    async with ctx.open_stream() as stream:
        async for batch in stream:
            # Slice the batch into microbatches for rate-limiting
            for microbatch in more_itertools.sliced(batch, batch_size):
                for port in microbatch:
                    tcp_segment = build_tcp_segment(interface, target, port)
                    await send_sock.sendto(ipv4_datagram + tcp_segment, (target, port))
                await trio.sleep(1 / nap_duration)
            # Let the receiver know that the worker is done sending.
            await stream.send(batch)
    send_sock.close()


async def main(
    target: str,
    interface: str,
    ports: list[Port],
    ranges: list[Range],
    batch_size: int,
    nap_duration: int,
    max_retries: int,
    workers: int = cpu_count(),
) -> None:
    async with (
        open_actor_cluster(modules=[__name__]) as portals,
        gather_contexts([
            p.open_context(
                batchworker,
                interface=interface,
                target=target,
                batch_size=batch_size,
                nap_duration=nap_duration,
            )
            for p in portals.values()
        ]) as contexts,
        gather_contexts([ctx[0].open_stream() for ctx in contexts]) as streams,
        aclosing(receiver(ranges, streams, interface, target, max_retries)) as areceiver,
    ):
        async for update in areceiver:
            ports = [*update]
            if not ports:
                break
            for (batch, stream) in zip(
                more_itertools.sliced(ports, math.ceil(len(ports) / workers)),
                itertools.cycle(streams)
            ):
                await stream.send(batch)
