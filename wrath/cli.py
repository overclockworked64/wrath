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
            self.fail("You need to pass a port range (e.g. 0-1024)", param, ctx)
        else:
            if not 0 <= start <= 65534:
                self.fail("Start must be in range [0, 65534]")
            if not 1 <= end <= 65535:
                self.fail("End must be in range [1, 65535]")
            if not start < end:
                self.fail("End must be in greater than start [1, 65535]")

            return (start, end)


@click.command()
@click.argument("target", type=str)
@click.option("--interface", "-i", type=str, required=True)
@optgroup.group("Port(s) [ranges]", cls=RequiredAnyOptionGroup)
@optgroup.option(
    "--port", "-p", "ports", type=click.IntRange(min=0, max=65535), multiple=True
)
@optgroup.option("--range", "-r", "ranges", type=PortRange(), multiple=True)
def cli(
    target: str,
    interface: str,
    ports: t.List[Port],
    ranges: t.List[Range],
) -> None:
    trio.run(main, target, interface, ports, ranges)
