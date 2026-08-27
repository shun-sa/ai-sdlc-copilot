import enum

# NFR-PERF-003 / ADR-013: 一覧は1ページ20件を標準とする。
DEFAULT_PAGE_SIZE = 20


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class MovieStatus(str, enum.Enum):
    PUBLISHED = "PUBLISHED"
    UNPUBLISHED = "UNPUBLISHED"


class PublishStatus(str, enum.Enum):
    PUBLISHED = "PUBLISHED"
    UNPUBLISHED = "UNPUBLISHED"


class OrderStatus(str, enum.Enum):
    CONFIRMED = "CONFIRMED"
    SHIPPED = "SHIPPED"
    CANCELLED = "CANCELLED"


# ADR-011: 支払方法は固定enumの模擬手段。いずれも常に成功扱い。
class PaymentMethod(str, enum.Enum):
    CREDIT_CARD_MOCK = "CREDIT_CARD_MOCK"
    CASH_ON_DELIVERY_MOCK = "CASH_ON_DELIVERY_MOCK"


PAYMENT_METHOD_LABELS: dict[PaymentMethod, str] = {
    PaymentMethod.CREDIT_CARD_MOCK: "クレジットカード（模擬）",
    PaymentMethod.CASH_ON_DELIVERY_MOCK: "代金引換（模擬）",
}


# ADR-012: 券種は固定enum。単価は上映回に紐づく価格設定データで保持する。
class TicketType(str, enum.Enum):
    GENERAL = "GENERAL"
    STUDENT = "STUDENT"
    SENIOR = "SENIOR"


TICKET_TYPE_LABELS: dict[TicketType, str] = {
    TicketType.GENERAL: "一般",
    TicketType.STUDENT: "学生",
    TicketType.SENIOR: "シニア",
}
