"""Initial schema

Revision ID: 001_init
Revises: 
Create Date: 2026-11-15 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "slots",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_slots_start"), "slots", ["start"], unique=False)

    op.create_table(
        "bookings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("slot_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="confirmed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["slot_id"], ["slots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bookings_slot_id"), "bookings", ["slot_id"], unique=False)
    op.create_index(op.f("ix_bookings_email"), "bookings", ["email"], unique=False)

    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("request_fingerprint", sa.String(), nullable=False),
        sa.Column("response_body", sa.Text(), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_idempotency_records_idempotency_key"), "idempotency_records", ["idempotency_key"], unique=True)

    op.create_table(
        "booking_attempts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_booking_attempts_email_attempted_at"), "booking_attempts", ["email", "attempted_at"], unique=False)

    op.execute("CREATE UNIQUE INDEX uq_confirmed_booking_slot ON bookings(slot_id) WHERE status = 'confirmed'")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_confirmed_booking_slot")
    op.drop_index(op.f("ix_booking_attempts_email_attempted_at"), table_name="booking_attempts")
    op.drop_table("booking_attempts")
    op.drop_index(op.f("ix_idempotency_records_idempotency_key"), table_name="idempotency_records")
    op.drop_table("idempotency_records")
    op.drop_index(op.f("ix_bookings_email"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_slot_id"), table_name="bookings")
    op.drop_table("bookings")
    op.drop_index(op.f("ix_slots_start"), table_name="slots")
    op.drop_table("slots")
