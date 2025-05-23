"""переопределение поля group в модели machine

Revision ID: b3efdb7be9c1
Revises: f803c92ab985
Create Date: 2025-05-21 13:57:38.179317

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'b3efdb7be9c1'
down_revision = 'f803c92ab985'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('machines', schema=None) as batch_op:
        batch_op.alter_column('machine_group',
               existing_type=mysql.VARCHAR(length=255),
               nullable=True)

    # Удаляем индекс, если существует
    op.execute("""
        DROP PROCEDURE IF EXISTS drop_index_if_exists;
    """)

    op.execute("""
        CREATE PROCEDURE drop_index_if_exists()
        BEGIN
            DECLARE index_exists INT;

            SELECT COUNT(*) INTO index_exists
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_NAME = 'stations'
              AND INDEX_NAME = 'uq_station_name_district'
              AND TABLE_SCHEMA = DATABASE();

            IF index_exists > 0 THEN
                SET @stmt = 'DROP INDEX uq_station_name_district ON stations';
                PREPARE stmt FROM @stmt;
                EXECUTE stmt;
                DEALLOCATE PREPARE stmt;
            END IF;
        END;
    """)

    op.execute("CALL drop_index_if_exists();")
    op.execute("DROP PROCEDURE drop_index_if_exists;")

    # И теперь создаём индекс
    with op.batch_alter_table('stations', schema=None) as batch_op:
        batch_op.create_index('uq_station_name_district', ['name', 'id_regional_district'], unique=True)


    # ### end Alembic commands ###


def downgrade():
    with op.batch_alter_table('stations', schema=None) as batch_op:
        batch_op.drop_index('uq_station_name_district')

    with op.batch_alter_table('machines', schema=None) as batch_op:
        batch_op.alter_column('machine_group',
               existing_type=mysql.VARCHAR(length=255),
               nullable=False)


    # ### end Alembic commands ###
