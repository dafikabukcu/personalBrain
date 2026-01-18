"""Main entry point for the brain application."""

import asyncio
import sys

import structlog

from brain.core.config import get_config

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)


def main():
    """Main entry point."""
    # Import CLI app and run it
    from brain.cli.app import app
    app()


if __name__ == "__main__":
    main()
