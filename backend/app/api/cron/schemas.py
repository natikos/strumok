from typing import Literal

from pydantic import BaseModel

JobStatus = Literal["ok", "notConfigured", "unavailable", "busy", "failed", "skipped"]


class InboxOut(BaseModel):
    received: int = 0
    imported: int = 0
    rejected: int = 0


class CronTickOut(BaseModel):
    reminders_status: JobStatus
    reminders_sent: int = 0
    reminders_removed: int = 0
    inbox_status: JobStatus
    inbox: InboxOut | None = None
