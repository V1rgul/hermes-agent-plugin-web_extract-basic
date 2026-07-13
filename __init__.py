"""Basic local web-extraction provider for Hermes."""

from .provider import BasicExtractProvider


def register(ctx) -> None:
	ctx.register_web_search_provider(BasicExtractProvider())
