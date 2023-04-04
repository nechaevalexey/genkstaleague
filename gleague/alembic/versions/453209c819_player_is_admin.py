"""player_is_admin

Revision ID: 453209c819
Revises: 4a6a586ab8d
Create Date: 2023-04-04 00:10:04.485744

"""

# revision identifiers, used by Alembic.
revision = "453209c819"
down_revision = "4a6a586ab8d"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column("player", sa.Column("is_admin", sa.Boolean(), nullable=True))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("player", "is_admin")
    ### end Alembic commands ###