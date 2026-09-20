"""Coercion facade (SOLID split).

Single-responsibility owners live in
:mod:`src.core.database_parts.coercion_parts`:

- ``recovery`` — startup recovery, corruption detection, write guards.
- ``schema_normalize`` — schema-introspection helpers and asset-type
  migrations/normalization.
- ``value_coerce`` — row/value coercion primitives.
"""
from __future__ import annotations

from typing import Any, TYPE_CHECKING
import re

if TYPE_CHECKING:
    from src.core.database import *  # noqa: F403
    from src.core.database_parts.pool import ConnectionPool

from src.core.database_parts.coercion_parts.recovery import (
    ComplexDatabaseRecoveryMixin,
)
from src.core.database_parts.coercion_parts.schema_normalize import (
    ComplexDatabaseSchemaNormalizeMixin,
)
from src.core.database_parts.coercion_parts.value_coerce import (
    ComplexDatabaseValueCoerceMixin,
)


class ComplexDatabaseCoercionMixin(
    ComplexDatabaseRecoveryMixin,
    ComplexDatabaseSchemaNormalizeMixin,
    ComplexDatabaseValueCoerceMixin,
):
    if TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any: ...
        _pool: ConnectionPool
    _NUMERIC_RE = re.compile(r"-?\d+(?:\.\d+)?")
