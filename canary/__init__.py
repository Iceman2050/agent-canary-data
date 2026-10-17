"""agent-canary-data: canary *data* as the agent-authorization tripwire.

When AI agents go rogue, misbehavior is almost never caught by detection —
incidents surface only when someone confesses. This package inverts the
approach: instead of trying to detect misbehavior, plant realistic-but-fake
records (customers, files, credentials) that no legitimate agent should ever
touch. Any read of a canary record is proof of AUTHORIZATION EXCEEDED.

Canary tokens exist for infrastructure. Canary *data* for agent authorization
boundaries is the new primitive.
"""

from .core import CanaryRecord, TripwireEvent
from .adapters import (
    DatastoreAdapter,
    JsonFileAdapter,
    SqliteAdapter,
    MonitoredStore,
)

__all__ = [
    "CanaryRecord",
    "TripwireEvent",
    "DatastoreAdapter",
    "JsonFileAdapter",
    "SqliteAdapter",
    "MonitoredStore",
]
__version__ = "0.1.0"
