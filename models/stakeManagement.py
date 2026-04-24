from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TransactionType(str, Enum):
    INITIAL_STAKE = "INITIAL_STAKE"
    BET_PLACED = "BET_PLACED"
    BET_WIN = "BET_WIN"
    BET_LOSS = "BET_LOSS"
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    ADJUSTMENT = "ADJUSTMENT"
    RESET = "RESET"

    @property
    def db_value(self) -> str:
        mapping = {
            TransactionType.BET_PLACED: "BET",
            TransactionType.BET_WIN: "WIN",
            TransactionType.BET_LOSS: "LOSS",
        }
        return mapping.get(self, self.value)


@dataclass
class StakeTransaction:
    gambler_id: int
    transaction_type: TransactionType
    amount: float
    balance_before: float
    balance_after: float
    session_id: int | None = None
    transaction_id: int | None = None
    bet_id: int | None = None
    game_id: int | None = None
    created_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["transaction_type"] = self.transaction_type.value
        if self.created_at is not None:
            payload["created_at"] = self.created_at.isoformat()
        return payload


@dataclass
class StakeBoundary:
    lower_limit: float
    upper_limit: float
    warning_low_threshold: float | None = None
    warning_high_threshold: float | None = None

    def __post_init__(self) -> None:
        self.lower_limit = float(self.lower_limit)
        self.upper_limit = float(self.upper_limit)

        if self.lower_limit < 0:
            raise ValueError("Lower limit must be greater than or equal to 0.")
        if self.upper_limit <= self.lower_limit:
            raise ValueError("Upper limit must be greater than lower limit.")

        spread = self.upper_limit - self.lower_limit
        if self.warning_low_threshold is None:
            self.warning_low_threshold = round(self.lower_limit + (spread * 0.2), 2)
        if self.warning_high_threshold is None:
            self.warning_high_threshold = round(self.lower_limit + (spread * 0.8), 2)

    def is_within_bounds(self, stake_amount: float) -> bool:
        value = float(stake_amount)
        return self.lower_limit <= value <= self.upper_limit

    def warning_messages(self, stake_amount: float) -> list[str]:
        value = float(stake_amount)
        warnings: list[str] = []
        if value <= float(self.warning_low_threshold):
            warnings.append("Stake is approaching the lower limit.")
        if value >= float(self.warning_high_threshold):
            warnings.append("Stake is approaching the upper limit.")
        return warnings

    def to_dict(self) -> dict[str, Any]:
        return {
            "lower_limit": self.lower_limit,
            "upper_limit": self.upper_limit,
            "warning_low_threshold": self.warning_low_threshold,
            "warning_high_threshold": self.warning_high_threshold,
        }


@dataclass
class StakeMonitor:
    session_id: int | None = None
    starting_stake: float = 0.0
    current_stake: float = 0.0
    peak_stake: float = 0.0
    lowest_stake: float = 0.0
    transactions: list[StakeTransaction] = field(default_factory=list)

    def record(self, transaction: StakeTransaction) -> None:
        self.transactions.append(transaction)
        self.current_stake = float(transaction.balance_after)
        if len(self.transactions) == 1:
            self.starting_stake = float(transaction.balance_after)
            self.peak_stake = float(transaction.balance_after)
            self.lowest_stake = float(transaction.balance_after)
            return

        self.peak_stake = max(self.peak_stake, float(transaction.balance_after))
        self.lowest_stake = min(self.lowest_stake, float(transaction.balance_after))

    @property
    def change_count(self) -> int:
        return max(len(self.transactions) - 1, 0)

    @property
    def volatility(self) -> float:
        if len(self.transactions) < 2:
            return 0.0

        changes = []
        previous_balance = float(self.transactions[0].balance_before)
        for transaction in self.transactions:
            current_balance = float(transaction.balance_after)
            changes.append(abs(current_balance - previous_balance))
            previous_balance = current_balance

        return round(sum(changes) / len(changes), 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "starting_stake": self.starting_stake,
            "current_stake": self.current_stake,
            "peak_stake": self.peak_stake,
            "lowest_stake": self.lowest_stake,
            "volatility": self.volatility,
            "change_count": self.change_count,
            "transactions": [transaction.to_dict() for transaction in self.transactions],
        }


@dataclass
class StakeHistoryReport:
    gambler_id: int
    session_id: int | None
    starting_stake: float
    current_stake: float
    peak_stake: float
    lowest_stake: float
    net_profit_or_loss: float
    volatility: float
    transaction_breakdown: dict[str, int]
    transactions: list[StakeTransaction]
    generated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gambler_id": self.gambler_id,
            "session_id": self.session_id,
            "starting_stake": self.starting_stake,
            "current_stake": self.current_stake,
            "peak_stake": self.peak_stake,
            "lowest_stake": self.lowest_stake,
            "net_profit_or_loss": self.net_profit_or_loss,
            "volatility": self.volatility,
            "transaction_breakdown": self.transaction_breakdown,
            "generated_at": self.generated_at.isoformat(),
            "transactions": [transaction.to_dict() for transaction in self.transactions],
        }
