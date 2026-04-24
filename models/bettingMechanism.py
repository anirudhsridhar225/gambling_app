from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Bet:
    gambler_id: int
    session_id: int
    bet_amount: float
    win_probability: float
    odds_value: float
    potential_win: float
    stake_before: float
    stake_after: float
    is_win: bool
    payout_amount: float
    bet_id: int | None = None
    strategy_id: int | None = None
    strategy_name: str | None = None
    placed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "bet_id": self.bet_id,
            "gambler_id": self.gambler_id,
            "session_id": self.session_id,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "bet_amount": self.bet_amount,
            "win_probability": self.win_probability,
            "odds_value": self.odds_value,
            "potential_win": self.potential_win,
            "stake_before": self.stake_before,
            "stake_after": self.stake_after,
            "is_win": self.is_win,
            "payout_amount": self.payout_amount,
            "placed_at": self.placed_at.isoformat() if self.placed_at else None,
        }


@dataclass
class BettingSession:
    gambler_id: int
    session_id: int
    started_at: datetime | None
    ended_at: datetime | None
    bets: list[Bet] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        total_bets = len(self.bets)
        total_wins = sum(1 for bet in self.bets if bet.is_win)
        total_losses = total_bets - total_wins
        total_wagered = round(sum(bet.bet_amount for bet in self.bets), 2)
        total_payout = round(sum(bet.payout_amount for bet in self.bets if bet.is_win), 2)

        starting_stake = self.bets[0].stake_before if self.bets else 0.0
        ending_stake = self.bets[-1].stake_after if self.bets else starting_stake

        return {
            "gambler_id": self.gambler_id,
            "session_id": self.session_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "summary": {
                "total_bets": total_bets,
                "total_wins": total_wins,
                "total_losses": total_losses,
                "win_rate": round((total_wins / total_bets) * 100, 2) if total_bets else 0.0,
                "total_wagered": total_wagered,
                "total_payout": total_payout,
                "net_profit_or_loss": round(ending_stake - starting_stake, 2),
                "starting_stake": starting_stake,
                "ending_stake": ending_stake,
            },
            "bets": [bet.to_dict() for bet in self.bets],
        }


class BaseBettingStrategy:
    def next_bet(self, current_stake: float) -> float:
        raise NotImplementedError()

    def record_outcome(self, is_win: bool) -> None:
        raise NotImplementedError()


class FixedAmountStrategy(BaseBettingStrategy):
    def __init__(self, amount: float):
        self.amount = float(amount)

    def next_bet(self, current_stake: float) -> float:
        return self.amount

    def record_outcome(self, is_win: bool) -> None:
        return


class PercentageStrategy(BaseBettingStrategy):
    def __init__(self, percentage: float):
        self.percentage = float(percentage)

    def next_bet(self, current_stake: float) -> float:
        return round(float(current_stake) * (self.percentage / 100.0), 2)

    def record_outcome(self, is_win: bool) -> None:
        return


class MartingaleStrategy(BaseBettingStrategy):
    def __init__(self, base_amount: float, multiplier: float = 2.0):
        self.base_amount = float(base_amount)
        self.multiplier = float(multiplier)
        self.current_amount = float(base_amount)

    def next_bet(self, current_stake: float) -> float:
        return self.current_amount

    def record_outcome(self, is_win: bool) -> None:
        if is_win:
            self.current_amount = self.base_amount
        else:
            self.current_amount = round(self.current_amount * self.multiplier, 2)


class ReverseMartingaleStrategy(BaseBettingStrategy):
    def __init__(self, base_amount: float, multiplier: float = 2.0):
        self.base_amount = float(base_amount)
        self.multiplier = float(multiplier)
        self.current_amount = float(base_amount)

    def next_bet(self, current_stake: float) -> float:
        return self.current_amount

    def record_outcome(self, is_win: bool) -> None:
        if is_win:
            self.current_amount = round(self.current_amount * self.multiplier, 2)
        else:
            self.current_amount = self.base_amount


class FibonacciStrategy(BaseBettingStrategy):
    def __init__(self, base_amount: float):
        self.base_amount = float(base_amount)
        self.sequence = [1, 1]
        self.index = 0

    def _ensure_sequence(self, position: int) -> None:
        while len(self.sequence) <= position:
            self.sequence.append(self.sequence[-1] + self.sequence[-2])

    def next_bet(self, current_stake: float) -> float:
        self._ensure_sequence(self.index)
        return round(self.base_amount * self.sequence[self.index], 2)

    def record_outcome(self, is_win: bool) -> None:
        if is_win:
            self.index = max(0, self.index - 2)
        else:
            self.index += 1


class DAlembertStrategy(BaseBettingStrategy):
    def __init__(self, base_amount: float, step_amount: float):
        self.base_amount = float(base_amount)
        self.step_amount = float(step_amount)
        self.current_amount = float(base_amount)

    def next_bet(self, current_stake: float) -> float:
        return self.current_amount

    def record_outcome(self, is_win: bool) -> None:
        if is_win:
            self.current_amount = max(self.base_amount, round(self.current_amount - self.step_amount, 2))
        else:
            self.current_amount = round(self.current_amount + self.step_amount, 2)
