import typing as t

import click
from click_option_group import optgroup
from click_option_group import RequiredAnyOptionGroup

import trio

from wrath.core import main


Port = int
Range = t.Tuple[Port, Port]


class PortRange(click.ParamType):
    name = "range"

    def convert(
        self,
        value: t.Any,
        param: t.Optional[click.Parameter],
        ctx: t.Optional[click.Context],
    ) -> t.Optional[Range]:
        try:
            start, end = map(int, value.split("-"))
        except ValueError:
            self.fail("You need to pass a port range (e.g. 1-1024)", param, ctx)
        else:
            if not 1 <= start <= 65534:
                self.fail("Start must be in range [1, 65534]")
            if not 2 <= end <= 65535:
                self.fail("End must be in range [2, 65535]")
            if not start < end:
                self.fail("End must be greater than start.")

            return (start, end + 1)  # inclusive


@click.command()
@click.argument("target", type=str)
@click.option("--interface", "-i", type=str, required=True, help='Interface for binding the socket')
@click.option("--batch-size", "-b", type=int, default=100, help='Size of the micro batch sent before napping')
@click.option("--nap-duration", "-n", type=int, default=100, help='Nap duration time (in milliseconds)')
@click.option("--max-retries", "-R", type=int, default=5, help='Max number of retries before giving up on inspecting a port')
@optgroup.group("Port(s)/Port range(s)", cls=RequiredAnyOptionGroup)
@optgroup.option(
    "--port", "-p", "ports", type=click.IntRange(min=1, max=65535), multiple=True,
    help='Scan an individual port (e.g. -p 22)'
)
@optgroup.option(
    "--range", "-r", "ranges", type=PortRange(), multiple=True,
    help='Scan a port range (e.g. -r 1024-2048)'
)
def cli(
    target: str,
    interface: str,
    ports: list[Port],
    ranges: list[Range],
    batch_size: int,
    nap_duration: int,
    max_retries: int,
) -> None:
    trio.run(
        main, target, interface, ports, ranges, batch_size, nap_duration, max_retries
    )
