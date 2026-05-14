"""Broker-layer exceptions.

These intentionally raise (unlike scanner tools, which return error dicts —
see CLAUDE.md Critical Rule #1). Order placement needs structured failures
the API layer can map to HTTP status codes; silent dicts would hide a fill.
"""


class BrokerError(Exception):
    """Base class for all broker-layer failures."""


class BrokerRejected(BrokerError):
    """The broker received the request and refused it.

    Examples: insufficient buying power, symbol halted, account flagged.
    The request shape was valid — the trade is just not allowed. Map to
    HTTP 422 at the API layer.
    """


class BrokerUnreachable(BrokerError):
    """The broker API is unreachable or returned a transient failure.

    Examples: 5xx from Alpaca, network timeout, DNS failure. Map to
    HTTP 503 at the API layer with header X-Broker-Status: unreachable.
    The frontend shows a "broker down" banner instead of a blank UI.
    """
