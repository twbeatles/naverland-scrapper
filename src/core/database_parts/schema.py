from __future__ import annotations

from src.core.database_parts.schema_parts.cleanup import ComplexDatabaseSchemaCleanupMixin
from src.core.database_parts.schema_parts.indexes import ComplexDatabaseSchemaIndexMixin
from src.core.database_parts.schema_parts.migrations import ComplexDatabaseSchemaMigrationMixin
from src.core.database_parts.schema_parts.tables import ComplexDatabaseSchemaTableMixin


class ComplexDatabaseSchemaMixin(
    ComplexDatabaseSchemaTableMixin,
    ComplexDatabaseSchemaMigrationMixin,
    ComplexDatabaseSchemaIndexMixin,
    ComplexDatabaseSchemaCleanupMixin,
):
    pass
