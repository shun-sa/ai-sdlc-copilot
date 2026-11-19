# trace: ADDR-012
"""消費税・税込価格の共通規則（CMN-30〜CMN-32。業務処理層の規則を1か所で定義する：ADDR-012 INV-001）。"""

TAX_RATE_PERCENT = 10


# trace: ADDR-012
def price_including_tax(price_excluding_tax: int) -> int:
    """税込価格＝税抜価格×110÷100 の1円未満切り捨て（CMN-32）。"""
    return price_excluding_tax * (100 + TAX_RATE_PERCENT) // 100


# trace: ADDR-012
def consumption_tax(taxable_amount: int) -> int:
    """消費税額＝課税対象額×10÷100 の1円未満切り捨て（CMN-31）。"""
    return taxable_amount * TAX_RATE_PERCENT // 100
