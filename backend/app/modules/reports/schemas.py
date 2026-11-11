from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.core.text import MULTILINE
from app.modules.reports.models import DETAILS_MAX, ReportReason

Details = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=DETAILS_MAX, pattern=MULTILINE)
]


class ReportIn(BaseModel):
    reason: ReportReason
    details: Details = ""
