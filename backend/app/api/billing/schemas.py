from pydantic import BaseModel

from app.core.time import UtcDatetime


class BillingWindowOut(BaseModel):
    period: str
    opens_at: UtcDatetime
    closes_at: UtcDatetime
    is_open: bool
