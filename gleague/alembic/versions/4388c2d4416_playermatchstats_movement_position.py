"""playermatchstats_movement

Revision ID: 4388c2d4416
Revises: 1cb8b35fcb0
Create Date: 2019-07-02 17:54:34.008907

"""

# revision identifiers, used by Alembic.
revision = "4388c2d4416"
down_revision = "1cb8b35fcb0"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "player_match_stats", sa.Column("movement", postgresql.JSONB, nullable=True)
    )
    op.add_column("player_match_stats", sa.Column("position", sa.String, nullable=True))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("player_match_stats", "movement")
    op.drop_column("player_match_stats", "position")
    ### end Alembic commands ###
