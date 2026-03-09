from __future__ import annotations

import argparse
from pathlib import Path

from assistant_ops.server import build_server


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the assistant ops MCP server.")
    parser.add_argument(
        "--workspace",
        default=".",
        help="Workspace root for audit logs and downloads.",
    )
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=("stdio", "sse", "streamable-http"),
        help="MCP transport to serve.",
    )
    parser.add_argument(
        "--actor",
        default="local-operator",
        help="Actor label recorded in audit logs.",
    )
    args = parser.parse_args()

    server = build_server(Path(args.workspace).resolve(), actor=args.actor)
    server.run(args.transport)


if __name__ == "__main__":
    main()
