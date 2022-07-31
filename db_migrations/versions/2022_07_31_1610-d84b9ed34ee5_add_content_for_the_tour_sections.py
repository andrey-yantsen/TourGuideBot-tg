"""Add content for the tour sections

Revision ID: d84b9ed34ee5
Revises: eecf06e78783
Create Date: 2022-07-31 16:10:05.723020

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd84b9ed34ee5'
down_revision = 'eecf06e78783'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('tour_section_content',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tour_section_id', sa.Integer(), nullable=False),
    sa.Column('position', sa.SmallInteger(), nullable=False),
    sa.Column('message_type', sa.Enum('text', 'location', 'audio', 'voice', 'video', 'video_note', 'photo', name='messagetype'), nullable=False),
    sa.Column('media_group_id', sa.String(), nullable=True),
    sa.Column('content', sa.JSON(), nullable=False),
    sa.Column('created_ts', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_ts', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['tour_section_id'], ['tour_section.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tour_section_content_secion_id_media_group', 'tour_section_content', ['tour_section_id', 'message_type', 'media_group_id'], unique=True)
    op.create_index('ix_tour_section_id_position', 'tour_section_content', ['tour_section_id', 'position'], unique=True)
    op.create_index('ix_tour_section_translation_id_position', 'tour_section', ['tour_translation_id', 'position'], unique=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('ix_tour_section_translation_id_position', table_name='tour_section')
    op.drop_index('ix_tour_section_id_position', table_name='tour_section_content')
    op.drop_index('ix_tour_section_content_secion_id_media_group', table_name='tour_section_content')
    op.drop_table('tour_section_content')
    # ### end Alembic commands ###
