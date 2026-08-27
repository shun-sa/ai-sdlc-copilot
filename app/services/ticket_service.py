import secrets

from sqlalchemy.orm import Session

from app.errors import InputInvalidError
from app.models.movie import Movie
from app.models.ticket import TicketPurchase, TicketPurchaseItem
from app.payment import MockPayment
from app.repositories.screening_repository import ScreeningRepository
from app.repositories.ticket_repository import TicketRepository
from app.schemas.commerce import TicketPurchaseInput
from app.services.availability import ensure_screening_purchasable


class TicketService:
    """FR-009。チケット購入・残席減算・スナップショット保持を単一トランザクションで行う（ADR-007/008/012）。"""

    def __init__(self, session: Session, payment: MockPayment | None = None) -> None:
        self._session = session
        self._tickets = TicketRepository(session)
        self._screenings = ScreeningRepository(session)
        self._payment = payment or MockPayment()

    def purchase(self, user_id: int, data: TicketPurchaseInput) -> TicketPurchase:
        try:
            # ADR-007: 残席行を悲観ロックで取得。確認から減算までを同一トランザクションで実行。
            screening = self._screenings.get_for_update(data.screening_id)
            ensure_screening_purchasable(screening, data.quantity)
            assert screening is not None

            # ADR-012: 金額はサーバー側の単価設定から算出。クライアント入力値を信頼しない。
            price = self._screenings.get_price(screening.id, data.ticket_type)
            if price is None:
                raise InputInvalidError("指定された券種は購入できません。")

            subtotal = price.unit_price * data.quantity
            screening.seats_remaining -= data.quantity  # 残席減算

            movie = self._session.get(Movie, screening.movie_id)
            movie_title = movie.title if movie is not None else ""

            purchase = TicketPurchase(
                purchase_number=self._generate_purchase_number(),
                user_id=user_id,
                total_amount=subtotal,
            )
            purchase.items.append(
                TicketPurchaseItem(
                    screening_id=screening.id,
                    movie_title_snapshot=movie_title,  # ADR-008: 確定時点スナップショット
                    screening_starts_at_snapshot=screening.starts_at,
                    ticket_type=data.ticket_type,
                    unit_price=price.unit_price,
                    quantity=data.quantity,
                    subtotal=subtotal,
                )
            )

            self._payment.charge(data.payment_method, subtotal)  # CON-002: 模擬決済
            self._tickets.add(purchase)
            self._session.commit()
            return purchase
        except Exception:
            # ERR-005 / NFR-AVL-004: 失敗時はロールバックし不完全購入を残さない。
            self._session.rollback()
            raise

    def _generate_purchase_number(self) -> str:
        for _ in range(5):
            candidate = "TKT-" + secrets.token_hex(8).upper()
            if not self._tickets.exists_purchase_number(candidate):
                return candidate
        raise RuntimeError("購入番号の採番に失敗しました。")
