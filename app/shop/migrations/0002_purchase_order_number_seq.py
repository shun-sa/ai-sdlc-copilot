# trace: ADDR-003
"""注文番号専用シーケンスの作成（ADDR-003 DD-001）。"""
from django.db import migrations

CREATE_SEQUENCE = "CREATE SEQUENCE IF NOT EXISTS purchase_order_number_seq START 1 INCREMENT 1 CACHE 1 NO CYCLE"
DROP_SEQUENCE = "DROP SEQUENCE IF EXISTS purchase_order_number_seq"


# trace: ADDR-003
class Migration(migrations.Migration):
    """注文番号の採番に用いるシーケンスを作成する。"""

    dependencies = [
        ("shop", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(sql=CREATE_SEQUENCE, reverse_sql=DROP_SEQUENCE),
    ]
