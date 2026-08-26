"""Initial Pokemon Resale Manager schema.

Revision ID: f0ee92bfef6d
Revises: None
"""
from typing import Sequence, Union

from alembic import op

# Import all v0.1 model modules so SQLAlchemy metadata is fully populated.
from app.core.database import Base
import app.models  # noqa: F401

revision: str = "f0ee92bfef6d"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
