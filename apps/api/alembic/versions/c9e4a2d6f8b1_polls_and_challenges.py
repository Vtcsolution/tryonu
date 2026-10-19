"""community: "Buy or skip?" polls and weekly style challenges

Revision ID: c9e4a2d6f8b1
Revises: b7d2f4a8c1e6
Create Date: 2026-10-19
"""

import sqlalchemy as sa
from alembic import op

revision = "c9e4a2d6f8b1"
down_revision = "b7d2f4a8c1e6"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "community_challenges",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("prize_1", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("prize_2", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("prize_3", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("sponsor_store_id", sa.String(length=36), sa.ForeignKey("stores.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_community_challenges_ends_at", "community_challenges", ["ends_at"])
    op.create_table(
        "community_challenge_winners",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("challenge_id", sa.String(length=36), sa.ForeignKey("community_challenges.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("post_id", sa.String(length=36), sa.ForeignKey("community_posts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("place", sa.Integer(), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("likes", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
        sa.UniqueConstraint("challenge_id", "place", name="uq_community_challenge_winners_place"),
    )
    op.create_index("ix_community_challenge_winners_challenge_id", "community_challenge_winners", ["challenge_id"])
    op.create_index("ix_community_challenge_winners_user_id", "community_challenge_winners", ["user_id"])
    op.create_table(
        "community_poll_votes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("post_id", sa.String(length=36), sa.ForeignKey("community_posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("choice", sa.String(length=8), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("post_id", "user_id", name="uq_community_poll_votes_pair"),
    )
    op.create_index("ix_community_poll_votes_post_id", "community_poll_votes", ["post_id"])
    op.create_index("ix_community_poll_votes_user_id", "community_poll_votes", ["user_id"])
    with op.batch_alter_table("community_posts") as batch:
        batch.add_column(sa.Column("poll", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("poll_buy", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("poll_skip", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("challenge_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_community_posts_challenge", "community_challenges", ["challenge_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_index("ix_community_posts_challenge_id", ["challenge_id"])
    with op.batch_alter_table("notifications") as batch:
        batch.add_column(sa.Column("challenge_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            "fk_notifications_challenge", "community_challenges", ["challenge_id"], ["id"], ondelete="CASCADE"
        )


def downgrade() -> None:
    with op.batch_alter_table("notifications") as batch:
        batch.drop_constraint("fk_notifications_challenge", type_="foreignkey")
        batch.drop_column("challenge_id")
    with op.batch_alter_table("community_posts") as batch:
        batch.drop_index("ix_community_posts_challenge_id")
        batch.drop_constraint("fk_community_posts_challenge", type_="foreignkey")
        batch.drop_column("challenge_id")
        batch.drop_column("poll_skip")
        batch.drop_column("poll_buy")
        batch.drop_column("poll")
    op.drop_table("community_poll_votes")
    op.drop_table("community_challenge_winners")
    op.drop_index("ix_community_challenges_ends_at", table_name="community_challenges")
    op.drop_table("community_challenges")
