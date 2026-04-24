from dataclasses import dataclass


@dataclass
class BettingPreferencesCreate:
    min_bet: float
    max_bet: float
    preferred_game_type: str | None = None
    auto_play_enabled: bool = False
    auto_play_max_games: int | None = None
    session_loss_limit: float | None = None
    session_win_target: float | None = None

    def __post_init__(self):
        if self.min_bet <= 0:
            raise ValueError("Minimum bet must be greater than 0.")

        if self.max_bet < self.min_bet:
            raise ValueError("Maximum bet must be greater than or equal to minimum bet.")

        if self.auto_play_enabled and (self.auto_play_max_games is None or self.auto_play_max_games <= 0):
            raise ValueError("Auto-play max games must be set and greater than 0 when auto-play is enabled.")


@dataclass
class BettingPreferencesUpdate:
    min_bet: float | None = None
    max_bet: float | None = None
    preferred_game_type: str | None = None
    auto_play_enabled: bool | None = None
    auto_play_max_games: int | None = None
    session_loss_limit: float | None = None
    session_win_target: float | None = None