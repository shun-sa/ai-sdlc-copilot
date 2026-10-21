# trace: ADDR-008
"""商品カタログの応答表現。"""

from __future__ import annotations

from typing import Any

from catalog.models import Collection, Item, StockUnit, price_incl_tax


def collection_payload(collection: Collection) -> dict[str, Any]:
    """商品分類一覧の1件（FR-010 手順3）。"""
    return {
        "collection_id": collection.pk,
        "collection_code": collection.collection_code,
        "name": collection.name,
        "parent_collection_id": collection.parent_id,
        "depth": collection.depth,
        "sort_order": collection.sort_order,
    }


def item_collections_payload(item: Item) -> list[dict[str, Any]]:
    """商品が所属する分類（分類ID・分類名）。"""
    return [
        {"collection_id": link.collection_id, "name": link.collection.name}
        for link in item.item_collections.all()
    ]


def item_summary_payload(item: Item) -> dict[str, Any]:
    """商品一覧検索の1件（FR-011 手順9）。"""
    min_price = item.min_price or 0
    return {
        "item_id": item.pk,
        "item_code": item.item_code,
        "name": item.name,
        "min_price": min_price,
        "min_price_incl_tax": price_incl_tax(min_price),
        "in_stock": bool(item.has_stock),
        "collections": item_collections_payload(item),
    }


def stock_unit_payload(stock_unit: StockUnit) -> dict[str, Any]:
    """商品詳細の在庫単位1件（FR-012 手順5）。仕入先は含めない。"""
    return {
        "stock_unit_id": stock_unit.pk,
        "sku": stock_unit.sku,
        "variant_name": stock_unit.variant_name,
        "price": stock_unit.price,
        "price_incl_tax": stock_unit.price_incl_tax,
        "quantity": stock_unit.quantity,
        "in_stock": stock_unit.in_stock,
    }


def item_detail_payload(item: Item) -> dict[str, Any]:
    """商品詳細照会の応答（FR-012 手順5）。"""
    return {
        "item_id": item.pk,
        "item_code": item.item_code,
        "name": item.name,
        "description": item.description,
        "collections": item_collections_payload(item),
        "stock_units": [stock_unit_payload(unit) for unit in item.ordered_stock_units],
    }


def admin_stock_unit_payload(stock_unit: StockUnit) -> dict[str, Any]:
    """在庫単位一覧照会（管理者）の1件（FR-040 6.20.5）。"""
    return {
        "stock_unit_id": stock_unit.pk,
        "sku": stock_unit.sku,
        "item_id": stock_unit.item_id,
        "item_code": stock_unit.item.item_code,
        "item_name": stock_unit.item.name,
        "variant_name": stock_unit.variant_name,
        "item_is_public": stock_unit.item.is_public,
        "supplier_id": stock_unit.supplier_id,
        "supplier_name": stock_unit.supplier.name,
        "price": stock_unit.price,
        "quantity": stock_unit.quantity,
        "is_low_stock": stock_unit.is_low_stock,
    }
