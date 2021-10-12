import functools
import typing as t

import click
import click_option_group
import trio

from wrath.core import main


class PortRange(click.ParamType):
    name = "range"

    def convert(
        self,
        value: t.Any,
        param: t.Optional[click.Parameter],
        ctx: t.Optional[click.Context],
    ) -> t.Any:
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
@click.argument("target")
@click.option("--interface", "-i", type=str, required=True)
@click_option_group.optgroup.group(
    "Port(s) [ranges]", cls=click_option_group.RequiredAnyOptionGroup
)
@click_option_group.optgroup.option(
    "--port", "-p",type=click.IntRange(min=0, max=65535), multiple=True
)
@click_option_group.optgroup.option(
    "--range", "-r", "range_", type=PortRange(), multiple=True
)
def cli(**kwargs: t.Any) -> None:
    trio.run(functools.partial(main, **kwargs))
