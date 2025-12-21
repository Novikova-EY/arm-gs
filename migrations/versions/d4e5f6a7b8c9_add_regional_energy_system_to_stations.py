"""add regional energy system to stations

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2025-01-28 14:00:00.000000

Р¤РёРєС‚РёРІРЅР°СЏ РјРёРіСЂР°С†РёСЏ РґР»СЏ СЃРёРЅС…СЂРѕРЅРёР·Р°С†РёРё СЃРѕСЃС‚РѕСЏРЅРёСЏ Р±Р°Р·С‹ РґР°РЅРЅС‹С… СЃ С„Р°Р№Р»Р°РјРё РјРёРіСЂР°С†РёР№.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    """РџСѓСЃС‚Р°СЏ РјРёРіСЂР°С†РёСЏ РґР»СЏ СЃРёРЅС…СЂРѕРЅРёР·Р°С†РёРё."""
    pass


def downgrade():
    """РџСѓСЃС‚Р°СЏ РјРёРіСЂР°С†РёСЏ РґР»СЏ СЃРёРЅС…СЂРѕРЅРёР·Р°С†РёРё."""
    pass
