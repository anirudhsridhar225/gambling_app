import re
from dataclasses import dataclass
from datetime import datetime

from settings import settings


@dataclass
class GamblerCreate:
    username: str
    full_name: str
    email: str
    initial_stake: float
    win_threshold: float
    loss_threshold: float
    min_required_stake: float

    def __post_init__(self):
        email_pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"

        if self.initial_stake < settings.MINIMUM_STAKE:
            raise ValueError(
                f"Initial stake must be at least {settings.MINIMUM_STAKE}."
            )

        if not re.fullmatch(email_pattern, self.email):
            raise ValueError("Invalid email entered.")

        if self.min_required_stake <= 0:
            raise ValueError("Minimum required stake must be greater than 0.")

        if self.win_threshold <= self.initial_stake:
            raise ValueError("Win threshold must be greater than initial stake.")

        if self.loss_threshold >= self.initial_stake:
            raise ValueError("Loss threshold must be less than initial stake.")


@dataclass
class GamblerPersonalInfoUpdate:
    username: str | None = None
    full_name: str | None = None
    email: str | None = None

    def __post_init__(self):
        if self.email is None:
            return
        email_pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.fullmatch(email_pattern, self.email):
            raise ValueError("Invalid email entered.")


@dataclass
class GamblerThresholdUpdate:
    win_threshold: float | None = None
    loss_threshold: float | None = None


@dataclass
class GamblerDisplay:
    id: int
    username: str
    full_name: str
    email: str
    is_active: bool
    initial_stake: float
    current_stake: float
    win_threshold: float
    loss_threshold: float
    min_required_stake: float
    created_at: datetime
    updated_at: datetime