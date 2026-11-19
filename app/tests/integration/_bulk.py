# trace: NFR-PF-06, NFR-AV-04, NFR-AV-12, NFR-OM-15
"""結合試験の共通部品：業務データ（利用者・マスタ・注文と関連データ）の COPY による一括生成（架空の値・決定的な乱数）。

scale=1.0 で 3年後相当の件数（12章 VDC-01〜VDC-03：会員 10,000・商品 600・在庫単位 1,600・商品分類 45・仕入先 35・
クーポン 150・注文 110,000・注文明細 330,000・配送先 110,000・決済記録 約120,000・注文状態履歴 約330,000〜360,000）。
注文の金額は FR-026 の計算（送料 5,000円未満 500円、消費税 10% 切捨て）で整合させる。識別子は offset 以降の範囲を使い、
アプリケーションの採番（シーケンス）と重ならないようにする。本ファイルは期待値を持たない。
"""

import random
from datetime import timedelta

from tests.integration._helpers import PASSWORD, jst

OFFSET = 50_000_000


# trace: NFR-PF-06, NFR-AV-04, NFR-AV-12, NFR-OM-15
def copy_rows(model, columns, rows):
    """COPY で一括投入する（モデルの属性名で列を指定）。投入件数を返す。"""
    from django.db import connection

    table = model._meta.db_table
    names = ", ".join(model._meta.get_field(c).column for c in columns)
    count = 0
    with connection.cursor() as cursor:
        with cursor.cursor.copy(f"COPY {table} ({names}) FROM STDIN") as copy:
            for row in rows:
                copy.write_row(row)
                count += 1
    return count


# trace: NFR-PF-06, NFR-AV-04, NFR-AV-12, NFR-OM-15
def generate(scale=1.0, offset=OFFSET, seed=20271118):
    """業務データを一括生成し、モデルごとの投入件数を返す（最後に ANALYZE）。"""
    from django.contrib.auth.hashers import make_password
    from django.db import connection

    from accounts.models import User
    from catalog.models import Category, Product, ProductCategory, StockUnit, Supplier
    from orders.models import Order, OrderItem, OrderStatusHistory, PaymentRecord, ShippingAddress
    from promotions.models import Coupon

    rng = random.Random(seed)
    base = jst(2024, 4, 1, 0, 0, 0)
    hashed = make_password(PASSWORD)
    buyers, orders_total = max(1, int(10_000 * scale)), max(1, int(110_000 * scale))
    counts = {}
    users = [
        (offset + i, hashed, f"vdc01.buyer{i:05d}@example.com", f"会員{i:05d}", "buyer", base) for i in range(buyers)
    ]
    users += [
        (offset + buyers + i, hashed, f"vdc01.admin{i}@example.com", f"管理者{i}", "admin", base) for i in range(7)
    ]
    counts["User"] = copy_rows(User, ["id", "password", "email", "name", "user_type", "registered_at"], users)
    counts["Supplier"] = copy_rows(
        Supplier,
        ["id", "supplier_code", "name"],
        [(offset + i, f"V-SUP{i:03d}", f"架空仕入先{i:03d}") for i in range(35)],
    )
    categories = [(offset + i, f"v-top-{i:02d}", f"大分類{i:02d}", None, 1, i) for i in range(15)]
    categories += [(offset + 15 + i, f"v-sub-{i:02d}", f"小分類{i:02d}", offset + i % 15, 2, i) for i in range(30)]
    counts["Category"] = copy_rows(
        Category, ["id", "category_code", "name", "parent", "depth", "display_order"], categories
    )
    counts["Product"] = copy_rows(
        Product,
        ["id", "product_code", "name", "description", "is_public", "registered_at"],
        [(offset + i, f"V-P{i:04d}", f"架空商品{i:04d}", "一括生成した計測用の商品", True, base) for i in range(600)],
    )
    counts["ProductCategory"] = copy_rows(
        ProductCategory,
        ["id", "product", "category"],
        [(offset + i, offset + i, offset + 15 + i % 30) for i in range(600)],
    )
    prices = [500 + (i % 60) * 50 for i in range(1600)]
    counts["StockUnit"] = copy_rows(
        StockUnit,
        ["id", "product", "supplier", "sku", "variant_name", "price_excluding_tax", "stock_quantity", "updated_at"],
        [
            (
                offset + i,
                offset + i % 600,
                offset + i % 35,
                f"V-SKU{i:05d}",
                f"規格{i // 600 + 1}",
                prices[i],
                99_999,
                base,
            )
            for i in range(1600)
        ],
    )
    counts["Coupon"] = copy_rows(
        Coupon,
        [
            "id",
            "coupon_code",
            "name",
            "discount_type",
            "discount_value",
            "minimum_purchase_amount",
            "valid_from",
            "valid_to",
        ],
        [
            (offset + i, f"V-CPN{i:03d}", f"架空クーポン{i:03d}", "fixed_amount", 300, 0, base, jst(2099, 12, 31))
            for i in range(150)
        ],
    )
    orders, items, addresses, payments, history = [], [], [], [], []
    admin_id = offset + buyers
    for n in range(orders_total):
        oid = offset + n
        buyer = offset + rng.randrange(buyers)
        at = base + timedelta(minutes=n * 14 + rng.randrange(10))
        units = rng.sample(range(1600), 3)
        lines = [(units[0], 2), (units[1], 2), (units[2], 1)]
        subtotal = sum(prices[u] * q for u, q in lines)
        shipping = 0 if subtotal >= 5000 else 500
        tax = (subtotal + shipping) * 10 // 100
        roll = rng.random()
        if roll < 0.58:
            status, path = "delivered", ["accepted", "paid", "shipped", "delivered"]
        elif roll < 0.65:
            status, path = "shipped", ["accepted", "paid", "shipped"]
        elif roll < 0.72:
            status, path = "paid", ["accepted", "paid"]
        elif roll < 0.80:
            status, path = "accepted", ["accepted"]
        elif roll < 0.90:
            status, path = "cancelled", ["accepted", "paid", "cancelled"]
        else:
            status, path = "cancelled", ["accepted", "cancelled"]
        stamps = {s: at + timedelta(hours=k * 6) for k, s in enumerate(path)}
        total = subtotal + shipping + tax
        orders.append(
            (
                oid,
                f"PO-{5_000_000 + n:08d}",
                buyer,
                status,
                subtotal,
                0,
                subtotal,
                shipping,
                tax,
                total,
                at,
                stamps.get("paid"),
                stamps.get("shipped"),
                stamps.get("delivered"),
                stamps.get("cancelled"),
                f"TRK{n:08d}" if "shipped" in stamps else None,
            )
        )
        for k, (u, q) in enumerate(lines):
            items.append(
                (
                    offset * 2 + n * 3 + k,
                    oid,
                    offset + u,
                    f"V-SKU{u:05d}",
                    f"架空商品{u % 600:04d}",
                    f"規格{u // 600 + 1}",
                    prices[u],
                    q,
                    prices[u] * q,
                )
            )
        addresses.append(
            (oid, oid, "架空 受取人", "1000001", f"{1 + n % 47:02d}", "架空区架空町1-1", None, "0312345678")
        )
        if rng.random() < 0.27:
            payments.append((oid, "declined", total, None, at + timedelta(hours=1)))
        if "paid" in stamps:
            payments.append((oid, "approved", total, f"MOCK-{n:016d}", stamps["paid"]))
        previous = None
        for s in path:
            actor = buyer if s in ("accepted", "paid") or (s == "cancelled" and n % 2) else admin_id
            history.append((oid, previous, s, stamps[s], actor, "buyer" if actor == buyer else "admin"))
            previous = s
    counts["Order"] = copy_rows(
        Order,
        [
            "id",
            "order_number",
            "buyer",
            "status",
            "subtotal",
            "discount_amount",
            "discounted_subtotal",
            "shipping_fee",
            "tax_amount",
            "total_amount",
            "ordered_at",
            "paid_at",
            "shipped_at",
            "delivered_at",
            "cancelled_at",
            "tracking_number",
        ],
        orders,
    )
    counts["OrderItem"] = copy_rows(
        OrderItem,
        ["id", "order", "stock_unit", "sku", "product_name", "variant_name", "unit_price", "quantity", "line_amount"],
        items,
    )
    counts["ShippingAddress"] = copy_rows(
        ShippingAddress,
        [
            "id",
            "order",
            "recipient_name",
            "postal_code",
            "prefecture",
            "address_line1",
            "address_line2",
            "phone_number",
        ],
        addresses,
    )
    counts["PaymentRecord"] = copy_rows(
        PaymentRecord, ["order", "result", "amount", "transaction_ref", "processed_at"], payments
    )
    counts["OrderStatusHistory"] = copy_rows(
        OrderStatusHistory, ["order", "from_status", "to_status", "changed_at", "actor", "actor_user_type"], history
    )
    with connection.cursor() as cursor:
        cursor.execute("ANALYZE")
    return counts
