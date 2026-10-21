"""esquema inicial

Revision ID: 0001
Revises:
Create Date: 2026-10-21 19:35:06.814011

Revisada à mão: o autogenerate duplicava as CHECK dos enums (uma com e outra sem a
convenção de nomes). Aqui cada enum é VARCHAR(20) + uma única CHECK nomeada
`ck_<tabela>_<enum>`, igual ao que os modelos declaram.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENUMS: dict[str, tuple[str, ...]] = {
    "location_kind": ("warehouse", "street"),
    "user_role": ("operador", "tecnico", "especialista", "supervisor", "admin"),
    "sleeper_status": ("in_stock", "withdrawn", "in_track", "quarantine", "discarded"),
    "sync_status": ("completed", "partial", "failed"),
    "conservation_state": ("good", "fair", "poor"),
    "moisture_level": ("dry", "moist", "wet"),
    "inspection_result": ("approved", "rejected"),
    "movement_kind": ("entry", "withdrawal", "transfer"),
    "occurrence_kind": ("damage", "loss", "misplaced", "other"),
}


def _enum_check(table: str, column: str, enum_name: str) -> sa.CheckConstraint:
    values = ", ".join(f"'{v}'" for v in ENUMS[enum_name])
    return sa.CheckConstraint(f"{column} IN ({values})", name=op.f(f"ck_{table}_{enum_name}"))


def _base_columns() -> list[sa.Column[object]]:
    """id + created_at/updated_at (mixins)."""
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def _fk(
    table: str, column: str, target: str, ondelete: str = "RESTRICT"
) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], [f"{target}.id"], name=op.f(f"fk_{table}_{column}_{target}"), ondelete=ondelete
    )


def _index(table: str, *columns: str) -> None:
    op.create_index(op.f(f"ix_{table}_{columns[0]}"), table, list(columns))


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        *_base_columns(),
        _enum_check("locations", "kind", "location_kind"),
        _fk("locations", "parent_id", "locations"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_locations")),
        sa.UniqueConstraint(
            "parent_id",
            "name",
            name=op.f("uq_locations_parent_id_name"),
            postgresql_nulls_not_distinct=True,
        ),
    )
    _index("locations", "parent_id")

    op.create_table(
        "users",
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("registration", sa.String(40), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        *_base_columns(),
        _enum_check("users", "role", "user_role"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("registration", name=op.f("uq_users_registration")),
    )

    op.create_table(
        "wood_species",
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("scientific_name", sa.String(200), nullable=True),
        sa.Column("common_name", sa.String(120), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        *_base_columns(),
        sa.CheckConstraint(
            "scientific_name IS NOT NULL OR common_name IS NOT NULL",
            name=op.f("ck_wood_species_has_name"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wood_species")),
        sa.UniqueConstraint("code", name=op.f("uq_wood_species_code")),
    )

    op.create_table(
        "audit_logs",
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("entity", sa.String(60), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("before", postgresql.JSONB(), nullable=True),
        sa.Column("after", postgresql.JSONB(), nullable=True),
        *_base_columns(),
        _fk("audit_logs", "user_id", "users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_logs_entity_entity_id", "audit_logs", ["entity", "entity_id"])
    _index("audit_logs", "user_id")

    op.create_table(
        "sleepers",
        sa.Column("rfid_tag", sa.String(64), nullable=False),
        sa.Column("registration_record", sa.String(40), nullable=True),
        sa.Column("species_id", sa.Uuid(), nullable=True),
        sa.Column("wood_class", sa.String(10), nullable=True),
        sa.Column("length_m", sa.Numeric(4, 2), nullable=True),
        sa.Column("treatment", sa.String(40), nullable=True),
        sa.Column("supplier", sa.String(80), nullable=True),
        sa.Column("inspection_company", sa.String(80), nullable=True),
        sa.Column("manufacture_year", sa.SmallInteger(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("current_location_id", sa.Uuid(), nullable=True),
        *_base_columns(),
        _enum_check("sleepers", "status", "sleeper_status"),
        _fk("sleepers", "species_id", "wood_species"),
        _fk("sleepers", "current_location_id", "locations"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sleepers")),
        # Unique já cria o índice btree usado na busca por tag (caminho quente).
        sa.UniqueConstraint("rfid_tag", name=op.f("uq_sleepers_rfid_tag")),
    )
    for column in ("registration_record", "species_id", "status", "current_location_id"):
        _index("sleepers", column)

    op.create_table(
        "inventory_counts",
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("species_id", sa.Uuid(), nullable=False),
        sa.Column("counted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("read_tags", postgresql.JSONB(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("client_uuid", sa.Uuid(), nullable=True),
        *_base_columns(),
        sa.CheckConstraint("quantity >= 0", name=op.f("ck_inventory_counts_quantity_non_negative")),
        _fk("inventory_counts", "location_id", "locations"),
        _fk("inventory_counts", "species_id", "wood_species"),
        _fk("inventory_counts", "user_id", "users"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inventory_counts")),
        sa.UniqueConstraint("client_uuid", name=op.f("uq_inventory_counts_client_uuid")),
    )
    for column in ("location_id", "species_id", "counted_at", "user_id"):
        _index("inventory_counts", column)

    op.create_table(
        "sync_batches",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.String(120), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("accepted", sa.Integer(), nullable=False),
        sa.Column("duplicate", sa.Integer(), nullable=False),
        sa.Column("rejected", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("results", postgresql.JSONB(), nullable=False),
        *_base_columns(),
        _enum_check("sync_batches", "status", "sync_status"),
        _fk("sync_batches", "user_id", "users"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_batches")),
    )
    op.create_index(
        "ix_sync_batches_user_device_received",
        "sync_batches",
        ["user_id", "device_id", "received_at"],
    )

    op.create_table(
        "inspections",
        sa.Column("sleeper_id", sa.Uuid(), nullable=False),
        sa.Column("inspector_id", sa.Uuid(), nullable=False),
        sa.Column("inspected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("conservation", sa.String(20), nullable=False),
        sa.Column("has_cracks", sa.Boolean(), nullable=False),
        sa.Column("biological_attack", sa.Boolean(), nullable=False),
        sa.Column("moisture", sa.String(20), nullable=False),
        sa.Column("estimated_life_years", sa.SmallInteger(), nullable=True),
        sa.Column("species_confirmed", sa.Boolean(), nullable=True),
        sa.Column("species_corrected_id", sa.Uuid(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("client_uuid", sa.Uuid(), nullable=True),
        *_base_columns(),
        _enum_check("inspections", "conservation", "conservation_state"),
        _enum_check("inspections", "moisture", "moisture_level"),
        _enum_check("inspections", "result", "inspection_result"),
        _fk("inspections", "sleeper_id", "sleepers"),
        _fk("inspections", "inspector_id", "users"),
        _fk("inspections", "species_corrected_id", "wood_species"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inspections")),
        sa.UniqueConstraint("client_uuid", name=op.f("uq_inspections_client_uuid")),
    )
    for column in (
        "sleeper_id",
        "inspector_id",
        "inspected_at",
        "species_corrected_id",
        "result",
    ):
        _index("inspections", column)

    op.create_table(
        "movements",
        sa.Column("sleeper_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("from_location_id", sa.Uuid(), nullable=True),
        sa.Column("to_location_id", sa.Uuid(), nullable=True),
        sa.Column("requisition_number", sa.String(40), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("client_uuid", sa.Uuid(), nullable=True),
        *_base_columns(),
        _enum_check("movements", "kind", "movement_kind"),
        _fk("movements", "sleeper_id", "sleepers"),
        _fk("movements", "from_location_id", "locations"),
        _fk("movements", "to_location_id", "locations"),
        _fk("movements", "user_id", "users"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_movements")),
        sa.UniqueConstraint("client_uuid", name=op.f("uq_movements_client_uuid")),
    )
    for column in ("sleeper_id", "from_location_id", "to_location_id", "user_id", "occurred_at"):
        _index("movements", column)

    op.create_table(
        "occurrences",
        sa.Column("sleeper_id", sa.Uuid(), nullable=True),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("client_uuid", sa.Uuid(), nullable=True),
        *_base_columns(),
        _enum_check("occurrences", "kind", "occurrence_kind"),
        _fk("occurrences", "sleeper_id", "sleepers"),
        _fk("occurrences", "location_id", "locations"),
        _fk("occurrences", "user_id", "users"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_occurrences")),
        sa.UniqueConstraint("client_uuid", name=op.f("uq_occurrences_client_uuid")),
    )
    for column in ("sleeper_id", "location_id", "kind", "user_id", "occurred_at"):
        _index("occurrences", column)


def downgrade() -> None:
    # Ordem inversa das dependências de FK; índices caem junto com as tabelas.
    for table in (
        "occurrences",
        "movements",
        "inspections",
        "sync_batches",
        "inventory_counts",
        "sleepers",
        "audit_logs",
        "wood_species",
        "users",
        "locations",
    ):
        op.drop_table(table)
