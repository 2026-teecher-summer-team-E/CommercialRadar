from pydantic import BaseModel


class BuzzGapItem(BaseModel):
    district_name: str
    gu_name: str | None = None
    buzz_index: int
    foot_pctl: int
    spend_pctl: int
    visit_gap: int
    spend_gap: int


class BuzzGapResponse(BaseModel):
    period: str | None
    source: str
    items: list[BuzzGapItem]
