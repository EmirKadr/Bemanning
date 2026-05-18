"""Shared warehouse/WMS tools used by Bemanning.

This package owns the long-term runtime for the Bearbeta, Dela and Harleda
views.  The public API is intentionally small: routers call `engine` for
shared helpers and `flows` for the flow registry/handlers.
"""

