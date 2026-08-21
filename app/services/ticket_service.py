"""映画チケット購入サービス (FR-009)。

購入確定・残席減算・番号発行を単一トランザクションで実行する (ADR-007)。
明細は上映スナップショットを保持する (ADR-008)。決済は模擬 (ADR-009)。
失敗時は全体ロールバックし不整合を残さない (ERR-005 / NFR-AVL-002/004)。
座席指定は行わず残席数のみ管理する (CON-004)。
"""

from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.constants import TICKET_TYPES
from app.errors import ConflictError, NotSaleableError, OutOfStockError, ValidationError
from app.models.movie import Movie
from app.models.ticket import TicketPurchase, TicketPurchaseItem
from app.payment import PaymentGateway
from app.repositories.screening_repository import ScreeningRepository
from app.repositories.ticket_repository import TicketRepository
from app.schemas.commerce import TicketPurchaseInput


class TicketService:
    def __init__(self, db: Session, payment: PaymentGateway) -> None:
        self.db = db
        self.payment = payment
        self.screenings = ScreeningRepository(db)
        self.tickets = TicketRepository(db)

    def purchase(self, user_id: int, data: TicketPurchaseInput) -> TicketPurchase:
        # OQ-REQ-002 (暫定): 券種と価格は暫定定義。未確定仕様。
        if data.ticket_type not in TICKET_TYPES:
            raise ValidationError("券種の指定が正しくありません。")
        unit_price = TICKET_TYPES[data.ticket_type]

        try:
            # ADR-007: 残席確認と減算を同一トランザクション内で行う
            screening = self.screenings.get_for_update(data.screening_id)  # 悲観ロック
            if screening is None:
                raise ValidationError("対象の上映回が見つかりません。")
            # ERR-004: 販売期間外/上映開始後は不可
            if not ScreeningRepository.is_saleable(screening):
                raise NotSaleableError("この上映回は現在購入できません。")
            if screening.seats_remaining < data.quantity:
                # ERR-003: 残席不足で購入失敗
                raise OutOfStockError("残席が不足しています。")

            screening.seats_remaining -= data.quantity  # 残席減算 (FR-009)

            movie = self.db.get(Movie, screening.movie_id)
            movie_title = movie.title if movie else ""
            subtotal = unit_price * data.quantity

            # ADR-009: 模擬決済（常に成功）
            self.payment.charge(subtotal, data.payment_method)

            purchase = TicketPurchase(
                purchase_number=_generate_number("TKT"),
                user_id=user_id,
                total_amount=subtotal,
                items=[
                    TicketPurchaseItem(
                        screening_id=screening.id,
                        ticket_type=data.ticket_type,
                        unit_price=unit_price,
                        quantity=data.quantity,
                        subtotal=subtotal,
                        # ADR-008: 確定時点の上映スナップショット
                        movie_title_snapshot=movie_title,
                        screening_starts_at_snapshot=screening.starts_at,
                        theater_name_snapshot=screening.theater_name,
                    )
                ],
            )
            self.tickets.add(purchase)
            self.db.commit()
        except (OutOfStockError, NotSaleableError, ValidationError):
            self.db.rollback()  # ERR-005: 不整合を残さない
            raise
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError() from exc
        self.db.refresh(purchase)
        return purchase


def _generate_number(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:16].upper()}"
