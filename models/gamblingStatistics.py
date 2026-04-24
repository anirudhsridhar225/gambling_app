from dataclasses import asdict, dataclass


@dataclass
class GamblerStatisticsDTO:
    gambler_id: int
    total_bets: int
    total_wins: int
    total_losses: int
    total_winnings: float
    win_rate: float
    average_bet_amount: float
    net_profit_or_loss: float
    reached_win_threshold: bool
    reached_loss_threshold: bool

    def to_dict(self):
        return asdict(self)