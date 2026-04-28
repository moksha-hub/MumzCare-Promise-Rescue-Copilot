from __future__ import annotations

import json
import sys
from typing import Annotated

import typer

from evals.run_evals import run_evals
from mumzcare.engine import analyze_case

app = typer.Typer(help="MumzCare Promise Rescue Copilot")


def write_json(data: object) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    sys.stdout.buffer.write(text.encode("utf-8"))


@app.command()
def analyze(
    message: Annotated[str, typer.Option("--message", "-m", help="Customer support message")],
    order_id: Annotated[str | None, typer.Option("--order-id", "-o", help="Optional order ID")] = None,
) -> None:
    """Analyze one customer support message."""
    packet = analyze_case(message=message, order_id=order_id)
    write_json(packet.model_dump(mode="json"))


@app.command()
def eval() -> None:
    """Run golden evals."""
    result = run_evals()
    write_json(result)


if __name__ == "__main__":
    app()
