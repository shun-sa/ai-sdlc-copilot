# 注文番号専用のシーケンス（ADDR-005 DD-001・DD-003：1から開始し、初期化・巻き戻しをしない）

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE SEQUENCE IF NOT EXISTS orders_order_number_seq START WITH 1 INCREMENT BY 1 MINVALUE 1 NO CYCLE;",
            reverse_sql="DROP SEQUENCE IF EXISTS orders_order_number_seq;",
        ),
    ]
