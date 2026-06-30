"""Enhanced base repository with CRUD, pagination, filtering, optimistic locking,
bulk operations, soft delete, and error translation.

Architecture:
    - Translates SQLAlchemy exceptions to repository exceptions
    - Supports domain entity mapping via mapper classes
    - Optimistic concurrency via version field
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import Result, Select, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.infrastructure.database.base import Base, SoftDeleteMixin
from backend.infrastructure.database.repositories.exceptions import (
    ConcurrentUpdateError,
    DuplicateEntityError,
    EntityNotFoundError,
    RepositoryError,
    RepositoryIntegrityError,
)

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic repository providing CRUD operations for any ORM model.

    Features:
    - Automatic soft-delete filtering (excludes archived records)
    - Pagination with limit/offset and ordering
    - Optimistic concurrency via version field
    - Bulk create/update/delete
    - Error translation: SQLAlchemy exceptions → RepositoryError subclasses

    Usage:
        class ProjectRepository(BaseRepository[Project]):
            def __init__(self, session: AsyncSession) -> None:
                super().__init__(Project, session)

    Type Parameters:
        ModelT: The SQLAlchemy ORM model class
    """

    def __init__(self, model_class: type[ModelT], session: AsyncSession) -> None:
        self.model_class = model_class
        self.session = session

    @property
    def _table_name(self) -> str:
        """Get the table name for error messages."""
        return self.model_class.__tablename__

    # ------------------------------------------------------------------
    # Query Building Helpers
    # ------------------------------------------------------------------

    def _apply_soft_delete_filter(self, stmt: Select) -> Select:
        """Add soft-delete filter if the model supports it."""
        if issubclass(self.model_class, SoftDeleteMixin):
            return stmt.where(self.model_class.is_archived == 0)  # type: ignore[attr-defined]
        return stmt

    def _has_version_field(self) -> bool:
        """Check if the model has a 'version' field for optimistic locking."""
        return hasattr(self.model_class, "version")

    # ------------------------------------------------------------------
    # Error Handling
    # ------------------------------------------------------------------

    async def _handle_integrity_error(
        self, exc: IntegrityError, entity_type: str | None = None
    ) -> None:
        """Translate SQLAlchemy IntegrityError to RepositoryError."""
        error_msg = str(exc.orig or exc).lower()
        entity = entity_type or self._table_name

        if "unique" in error_msg or "UNIQUE" in error_msg:
            # Extract constraint name if possible
            constraint = "unknown"
            if "constraint" in error_msg:
                import re
                match = re.search(r"(?:constraint|failed)\s*(?::\s*)?(\w+)", error_msg)
                if match:
                    constraint = match.group(1)
            raise DuplicateEntityError(entity, constraint) from exc

        if "foreign key" in error_msg:
            msg = f"Foreign key violation for {entity}"
            raise RepositoryIntegrityError(
                msg,
                {"entity": entity, "detail": str(exc)},
            ) from exc

        msg = f"Database integrity error for {entity}"
        raise RepositoryIntegrityError(
            msg,
            {"entity": entity, "detail": str(exc)},
        ) from exc

    async def _handle_general_error(
        self, exc: Exception, entity_type: str | None = None
    ) -> None:
        """Translate general exceptions to RepositoryError."""
        if isinstance(exc, RepositoryError):
            raise
        entity = entity_type or self._table_name
        msg = "ERR-REPO-UNEXPECTED"
        raise RepositoryError(
            msg,
            f"Unexpected error in {entity} repository: {exc}",
            {"entity": entity, "detail": str(exc)},
        ) from exc

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create(self, **kwargs: Any) -> ModelT:
        """Create a new record and flush.

        Args:
            **kwargs: Field values for the new record

        Returns:
            The created model instance

        Raises:
            DuplicateEntityError: If a unique constraint is violated
        """
        try:
            instance = self.model_class(**kwargs)
            self.session.add(instance)
            await self.session.flush()
            await self.session.refresh(instance)
            return instance
        except IntegrityError as exc:
            await self.session.rollback()
            await self._handle_integrity_error(exc)
            raise  # unreachable
        except Exception as exc:
            await self.session.rollback()
            await self._handle_general_error(exc)
            raise  # unreachable

    async def bulk_create(self, items: list[dict[str, Any]]) -> list[ModelT]:
        """Create multiple records in a single flush.

        Args:
            items: List of field-value dicts for each record

        Returns:
            List of created model instances
        """
        try:
            instances: list[ModelT] = []
            for item in items:
                instance = self.model_class(**item)
                self.session.add(instance)
                instances.append(instance)
            await self.session.flush()
            for inst in instances:
                await self.session.refresh(inst)
            return instances
        except IntegrityError as exc:
            await self.session.rollback()
            await self._handle_integrity_error(exc)
            raise
        except Exception as exc:
            await self.session.rollback()
            await self._handle_general_error(exc)
            raise

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get(self, id_: str) -> ModelT | None:
        """Get a record by primary key.

        Args:
            id_: The primary key value

        Returns:
            The model instance or None if not found
        """
        stmt = select(self.model_class).where(
            self.model_class.id == id_  # type: ignore[attr-defined]
        )
        stmt = self._apply_soft_delete_filter(stmt)
        result: Result[tuple[ModelT]] = await self.session.execute(stmt)  # type: ignore[valid-type]
        return result.unique().scalar_one_or_none()

    async def get_or_raise(self, id_: str) -> ModelT:
        """Get a record by primary key or raise EntityNotFoundError.

        Args:
            id_: The primary key value

        Returns:
            The model instance

        Raises:
            EntityNotFoundError: If the record does not exist
        """
        instance = await self.get(id_)
        if instance is None:
            raise EntityNotFoundError(self._table_name, id_)
        return instance

    async def find_by(self, **kwargs: Any) -> ModelT | None:
        """Find a single record by field values.

        Args:
            **kwargs: Field=value pairs to filter by

        Returns:
            The first matching record or None
        """
        stmt = select(self.model_class)
        stmt = self._apply_soft_delete_filter(stmt)
        for col, val in kwargs.items():
            stmt = stmt.where(getattr(self.model_class, col) == val)
        result: Result[tuple[ModelT]] = await self.session.execute(stmt)  # type: ignore[valid-type]
        return result.unique().scalar_one_or_none()

    async def find_many_by(self, **kwargs: Any) -> Sequence[ModelT]:
        """Find all records matching field values.

        Args:
            **kwargs: Field=value pairs to filter by

        Returns:
            List of matching records
        """
        stmt = select(self.model_class)
        stmt = self._apply_soft_delete_filter(stmt)
        for col, val in kwargs.items():
            stmt = stmt.where(getattr(self.model_class, col) == val)
        result: Result[tuple[ModelT]] = await self.session.execute(stmt)  # type: ignore[valid-type]
        return list(result.unique().scalars().all())

    async def exists(self, id_: str) -> bool:
        """Check if a record exists by primary key.

        Args:
            id_: The primary key value

        Returns:
            True if the record exists (and is not soft-deleted)
        """
        stmt = select(self.model_class).where(
            self.model_class.id == id_  # type: ignore[attr-defined]
        )
        stmt = self._apply_soft_delete_filter(stmt)
        result: Result[tuple[ModelT]] = await self.session.execute(stmt)  # type: ignore[valid-type]
        return result.unique().scalar_one_or_none() is not None

    async def count(
        self, filters: dict[str, Any] | None = None
    ) -> int:
        """Count records with optional filters.

        Args:
            filters: Dict of column=value equality filters

        Returns:
            Total count
        """
        stmt = select(func.count()).select_from(self.model_class)
        stmt = self._apply_soft_delete_filter(stmt)
        if filters:
            for col, val in filters.items():
                stmt = stmt.where(getattr(self.model_class, col) == val)
        result: Result[tuple[int]] = await self.session.execute(stmt)  # type: ignore[valid-type]
        return result.scalar_one()

    async def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = True,
        filters: dict[str, Any] | None = None,
    ) -> tuple[list[ModelT], int]:
        """List records with pagination, ordering, and filtering.

        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip
            order_by: Column name to order by
            descending: Sort descending if True
            filters: Dict of column=value equality filters

        Returns:
            Tuple of (records list, total count)
        """
        try:
            total = await self.count(filters)

            stmt = select(self.model_class)
            stmt = self._apply_soft_delete_filter(stmt)

            if filters:
                for col, val in filters.items():
                    stmt = stmt.where(getattr(self.model_class, col) == val)

            if order_by:
                col = getattr(self.model_class, order_by)
                stmt = stmt.order_by(col.desc() if descending else col.asc())

            stmt = stmt.offset(offset).limit(limit)
            result: Result[tuple[ModelT]] = await self.session.execute(stmt)  # type: ignore[valid-type]
            records: list[ModelT] = list(result.unique().scalars().all())

            return records, total
        except Exception as exc:
            await self._handle_general_error(exc)
            raise

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update(self, id_: str, **kwargs: Any) -> ModelT | None:
        """Update a record by primary key with partial field updates.

        Args:
            id_: The primary key value
            **kwargs: Field values to update

        Returns:
            The updated model instance or None if not found
        """
        try:
            instance = await self.get(id_)
            if instance is None:
                return None

            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)

            await self.session.flush()
            await self.session.refresh(instance)
            return instance
        except IntegrityError as exc:
            await self.session.rollback()
            await self._handle_integrity_error(exc)
            raise
        except Exception as exc:
            await self.session.rollback()
            await self._handle_general_error(exc)
            raise

    async def update_with_version(
        self, id_: str, expected_version: int, **kwargs: Any
    ) -> ModelT | None:
        """Update with optimistic concurrency check.

        Args:
            id_: The primary key value
            expected_version: The version number expected
            **kwargs: Field values to update

        Returns:
            The updated model instance or None if not found

        Raises:
            ConcurrentUpdateError: If version does not match
        """
        if not self._has_version_field():
            return await self.update(id_, **kwargs)

        instance = await self.get(id_)
        if instance is None:
            return None

        actual_version = getattr(instance, "version", 0)
        if actual_version != expected_version:
            raise ConcurrentUpdateError(
                self._table_name, id_, expected_version, actual_version,
            )

        for key, value in kwargs.items():
            if hasattr(instance, key) and key != "version":
                setattr(instance, key, value)

        # Increment version
        if hasattr(instance, "version"):
            instance.version = actual_version + 1

        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def bulk_update(
        self, ids: list[str], **kwargs: Any
    ) -> int:
        """Update multiple records by their IDs.

        Args:
            ids: List of primary key values
            **kwargs: Field values to update

        Returns:
            Number of records updated
        """
        if not ids:
            return 0
        try:
            stmt = (
                update(self.model_class)
                .where(self.model_class.id.in_(ids))  # type: ignore[attr-defined]
                .values(**kwargs)
            )
            stmt_result = await self.session.execute(stmt)
            await self.session.flush()
            return stmt_result.rowcount  # type: ignore[return-value]
        except IntegrityError as exc:
            await self.session.rollback()
            await self._handle_integrity_error(exc)
            raise
        except Exception as exc:
            await self.session.rollback()
            await self._handle_general_error(exc)
            raise

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete(self, id_: str) -> bool:
        """Hard delete a record by primary key.

        Args:
            id_: The primary key value

        Returns:
            True if a record was deleted, False if not found
        """
        instance = await self.get(id_)
        if instance is None:
            return False
        try:
            await self.session.delete(instance)
            await self.session.flush()
            return True
        except IntegrityError as exc:
            await self.session.rollback()
            raise RepositoryIntegrityError(
                "Cannot delete " + self._table_name + f" '{id_}' - referenced by other records",
            ) from exc

    async def bulk_delete(self, ids: list[str]) -> int:
        """Delete multiple records by their IDs.

        Args:
            ids: List of primary key values

        Returns:
            Number of records deleted
        """
        if not ids:
            return 0
        try:
            stmt = select(self.model_class).where(
                self.model_class.id.in_(ids)  # type: ignore[attr-defined]
            )
            del_result: Result[tuple[ModelT]] = await self.session.execute(stmt)  # type: ignore[valid-type]
            instances = list(del_result.unique().scalars().all())
            for inst in instances:
                await self.session.delete(inst)
            await self.session.flush()
            return len(instances)
        except IntegrityError as exc:
            await self.session.rollback()
            raise RepositoryIntegrityError(
                "Cannot delete " + str(len(ids)) + " records from " + self._table_name,
            ) from exc

    async def soft_delete(self, id_: str) -> bool:
        """Soft delete (archive) a record if the model supports it.

        Args:
            id_: The primary key value

        Returns:
            True if archived, False if not found
        """
        if not issubclass(self.model_class, SoftDeleteMixin):
            return await self.delete(id_)

        instance = await self.get(id_)
        if instance is None:
            return False
        try:
            instance.soft_delete()  # type: ignore[attr-defined]
            await self.session.flush()
            return True
        except Exception as exc:
            await self.session.rollback()
            await self._handle_general_error(exc)
            raise

    async def restore(self, id_: str) -> ModelT | None:
        """Restore a soft-deleted record.

        Args:
            id_: The primary key value

        Returns:
            The restored instance or None if not found
        """
        if not issubclass(self.model_class, SoftDeleteMixin):
            return None

        # Bypass soft-delete filter to find archived records
        stmt = select(self.model_class).where(
            self.model_class.id == id_  # type: ignore[attr-defined]
        )
        result: Result[tuple[ModelT]] = await self.session.execute(stmt)  # type: ignore[valid-type]
        instance = result.unique().scalar_one_or_none()

        if instance is None:
            return None
        try:
            instance.restore()  # type: ignore[attr-defined]
            await self.session.flush()
            await self.session.refresh(instance)
            return instance
        except Exception as exc:
            await self.session.rollback()
            await self._handle_general_error(exc)
            raise

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    async def raw_sql(
        self, sql: str, params: dict[str, Any] | None = None
    ) -> Result:
        """Execute raw SQL for custom queries beyond the ORM.

        Args:
            sql: Raw SQL string
            params: Optional parameters for the query

        Returns:
            SQLAlchemy Result object
        """
        result: Result[Any] = await self.session.execute(
            text(sql).bindparams(**(params or {}))
        )
        return result
