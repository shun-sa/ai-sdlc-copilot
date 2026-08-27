from datetime import datetime

from app.errors import NotFoundError, OutOfSalesPeriodError, StockShortageError
from app.models.product import Product
from app.models.screening import Screening


def ensure_product_orderable(
    product: Product | None, quantity: int, reference: datetime | None = None
) -> Product:
    """商品が注文可能かを検証する（C-DATA-001/002/003, ERR-003/004）。"""
    if product is None or not product.is_published():
        raise NotFoundError()
    if not product.is_on_sale(reference):
        raise OutOfSalesPeriodError()
    if product.stock < quantity:
        raise StockShortageError()
    return product


def ensure_screening_purchasable(
    screening: Screening | None, quantity: int, reference: datetime | None = None
) -> Screening:
    """上映回が購入可能かを検証する（FR-009, ERR-003/004, C-DATA-002）。"""
    if screening is None:
        raise NotFoundError()
    if not screening.is_on_sale(reference):
        raise OutOfSalesPeriodError()
    if not screening.has_seats(quantity):
        raise StockShortageError()
    return screening
