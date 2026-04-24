from __future__ import annotations

import random
from typing import Any

from models.bettingMechanism import (
    BaseBettingStrategy,
    Bet,
    BettingSession,
    DAlembertStrategy,
    FibonacciStrategy,
    FixedAmountStrategy,
    MartingaleStrategy,
    PercentageStrategy,
    ReverseMartingaleStrategy,
)
from services.stakeManagementService import StakeManagementService


class BettingService:
    def __init__(self, cnx, stake_service: StakeManagementService):
        self.cnx = cnx
        self.stake_service = stake_service
        self._has_bets_game_index = self._column_exists("bets", "game_index")
        self._has_game_records_game_index = self._column_exists("game_records", "game_index")

    def _column_exists(self, table_name: str, column_name: str) -> bool:
        cursor = self.cnx.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
              AND COLUMN_NAME = %s
            """,
            (table_name, column_name),
        )
        exists = cursor.fetchone()[0] > 0
        cursor.close()
        return exists

    def _dict_cursor(self):
        return self.cnx.cursor(dictionary=True)

    def _get_gambler(self, gambler_id: int) -> dict[str, Any]:
        cursor = self._dict_cursor()
        cursor.execute("SELECT * FROM gambler WHERE id = %s", (gambler_id,))
        gambler = cursor.fetchone()
        cursor.close()
        if not gambler:
            raise ValueError(f"Gambler {gambler_id} was not found.")
        return gambler

    def _get_active_session(self, gambler_id: int) -> dict[str, Any]:
        cursor = self._dict_cursor()
        cursor.execute(
            """
            SELECT *
            FROM sessions
            WHERE gambler_id = %s AND status = 'ACTIVE'
            ORDER BY session_id DESC
            LIMIT 1
            """,
            (gambler_id,),
        )
        session = cursor.fetchone()
        cursor.close()
        if not session:
            raise ValueError("No active betting session found. Initialize stake session first.")
        return session

    def _get_preferences(self, gambler_id: int) -> dict[str, Any]:
        cursor = self._dict_cursor()
        cursor.execute(
            "SELECT * FROM betting_preferences WHERE gambler_id = %s",
            (gambler_id,),
        )
        preferences = cursor.fetchone()
        cursor.close()
        if not preferences:
            raise ValueError(f"Betting preferences not found for gambler {gambler_id}.")
        return preferences

    def _validate_probability(self, win_probability: float) -> None:
        if win_probability <= 0 or win_probability >= 1:
            raise ValueError("Win probability must be greater than 0 and less than 1.")

    def _generate_win_probability(self) -> float:
        # Keep probability in a realistic and bounded range for game simulation.
        return round(random.uniform(0.35, 0.75), 4)

    def _validate_bet_amount(
        self,
        amount: float,
        current_stake: float,
        preferences: dict[str, Any],
    ) -> None:
        if amount <= 0:
            raise ValueError("Bet amount must be greater than 0.")

        min_bet = float(preferences["min_bet"])
        max_bet = float(preferences["max_bet"])
        if amount < min_bet:
            raise ValueError(f"Bet amount must be at least {min_bet}.")
        if amount > max_bet:
            raise ValueError(f"Bet amount must be at most {max_bet}.")
        if amount > current_stake:
            raise ValueError("Bet amount cannot exceed current stake.")

    def _validate_session_limits(self, session: dict[str, Any], preferences: dict[str, Any]) -> None:
        max_games = session.get("max_games")
        games_played = int(session.get("games_played") or 0)
        if max_games is not None and games_played >= int(max_games):
            raise ValueError("Session has reached the maximum games limit.")

        session_loss_limit = preferences.get("session_loss_limit")
        session_win_target = preferences.get("session_win_target")
        if session_loss_limit is None and session_win_target is None:
            return

        starting_stake = float(session["starting_stake"])
        ending_stake = float(session.get("ending_stake") or session["starting_stake"])
        net = round(ending_stake - starting_stake, 2)

        if session_loss_limit is not None and net <= -abs(float(session_loss_limit)):
            raise ValueError("Session loss limit reached. No more bets are allowed.")
        if session_win_target is not None and net >= float(session_win_target):
            raise ValueError("Session win target reached. No more bets are allowed.")

    def determine_bet_outcome(self, win_probability: float) -> bool:
        self._validate_probability(win_probability)
        return random.random() < win_probability

    def _decimal_odds_from_probability(self, win_probability: float) -> float:
        self._validate_probability(win_probability)
        return round(1.0 / win_probability, 2)

    def _ensure_strategy_row(self, strategy_name: str) -> int:
        normalized = strategy_name.strip().upper()
        cursor = self._dict_cursor()
        cursor.execute(
            "SELECT strategy_id FROM betting_strategies WHERE strategy_name = %s LIMIT 1",
            (normalized,),
        )
        row = cursor.fetchone()
        cursor.close()
        if row:
            return int(row["strategy_id"])

        strategy_type = "RANDOM"
        if normalized in {"FIXED", "MARTINGALE", "REVERSE_MARTINGALE", "FIBONACCI", "D_ALEMBERT"}:
            strategy_type = "FIXED"
        if normalized == "PERCENTAGE":
            strategy_type = "PERCENTAGE"

        # Generate strategy code from strategy name
        strategy_code_map = {
            "FIXED": "FIX",
            "PERCENTAGE": "PCT",
            "MARTINGALE": "MAR",
            "REVERSE_MARTINGALE": "RMAR",
            "FIBONACCI": "FIB",
            "D_ALEMBERT": "DAL",
            "RANDOM": "RND",
        }
        strategy_code = strategy_code_map.get(normalized, normalized[:3].upper())

        cursor = self.cnx.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO betting_strategies (strategy_name, strategy_code, strategy_type, is_active)
                VALUES (%s, %s, %s, %s)
                """,
                (normalized, strategy_code, strategy_type, True),
            )
            strategy_id = cursor.lastrowid
            self.cnx.commit()
        except Exception:
            self.cnx.rollback()
            raise
        finally:
            cursor.close()

        return int(strategy_id)

    def _insert_bet(
        self,
        session_id: int,
        gambler_id: int,
        strategy_id: int | None,
        amount: float,
        win_probability: float,
        odds_value: float,
        stake_before: float,
    ) -> int:
        cursor = self.cnx.cursor()
        try:
            game_index = None
            if self._has_bets_game_index:
                cursor.execute(
                    "SELECT COALESCE(MAX(game_index), 0) + 1 FROM bets WHERE session_id = %s",
                    (session_id,),
                )
                game_index = int(cursor.fetchone()[0])

            if self._has_bets_game_index:
                cursor.execute(
                    """
                    INSERT INTO bets (
                        session_id,
                        gambler_id,
                        strategy_id,
                        game_index,
                        bet_amount,
                        win_probability,
                        odds_type,
                        odds_value,
                        stake_before,
                        stake_after,
                        is_settled
                    ) VALUES (%s, %s, %s, %s, %s, %s, 'DECIMAL', %s, %s, %s, %s)
                    """,
                    (
                        session_id,
                        gambler_id,
                        strategy_id,
                        game_index,
                        amount,
                        win_probability,
                        odds_value,
                        stake_before,
                        stake_before,
                        False,
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO bets (
                        session_id,
                        gambler_id,
                        strategy_id,
                        bet_amount,
                        win_probability,
                        odds_type,
                        odds_value,
                        stake_before,
                        stake_after,
                        is_settled
                    ) VALUES (%s, %s, %s, %s, %s, 'DECIMAL', %s, %s, %s, %s)
                    """,
                    (
                        session_id,
                        gambler_id,
                        strategy_id,
                        amount,
                        win_probability,
                        odds_value,
                        stake_before,
                        stake_before,
                        False,
                    ),
                )
            bet_id = cursor.lastrowid
            self.cnx.commit()
            return int(bet_id)
        except Exception:
            self.cnx.rollback()
            raise
        finally:
            cursor.close()

    def _update_bet_settlement(self, bet_id: int, stake_after: float) -> None:
        cursor = self.cnx.cursor()
        try:
            cursor.execute(
                "UPDATE bets SET stake_after = %s, is_settled = %s WHERE bet_id = %s",
                (stake_after, True, bet_id),
            )
            self.cnx.commit()
        except Exception:
            self.cnx.rollback()
            raise
        finally:
            cursor.close()

    def _get_recent_outcome_streak(self, session_id: int, outcome: str) -> int:
        cursor = self._dict_cursor()
        cursor.execute(
            """
            SELECT outcome
            FROM game_records
            WHERE session_id = %s
            ORDER BY game_id DESC
            LIMIT 100
            """,
            (session_id,),
        )
        rows = cursor.fetchall()
        cursor.close()

        streak = 0
        for row in rows:
            if row["outcome"] == outcome:
                streak += 1
            else:
                break
        return streak

    def _insert_game_record(
        self,
        session_id: int,
        bet_id: int,
        is_win: bool,
        payout_amount: float,
        loss_amount: float,
        stake_before: float,
        stake_after: float,
    ) -> int:
        outcome = "WIN" if is_win else "LOSS"
        win_streak = self._get_recent_outcome_streak(session_id, "WIN")
        loss_streak = self._get_recent_outcome_streak(session_id, "LOSS")
        if is_win:
            win_streak += 1
            loss_streak = 0
        else:
            loss_streak += 1
            win_streak = 0

        net_change = round(stake_after - stake_before, 2)

        cursor = self.cnx.cursor()
        try:
            game_index = None
            if self._has_game_records_game_index:
                cursor.execute(
                    "SELECT COALESCE(MAX(game_index), 0) + 1 FROM game_records WHERE session_id = %s",
                    (session_id,),
                )
                game_index = int(cursor.fetchone()[0])

            if self._has_game_records_game_index:
                cursor.execute(
                    """
                    INSERT INTO game_records (
                        session_id,
                        bet_id,
                        odds_config_id,
                        game_index,
                        outcome,
                        payout_amount,
                        loss_amount,
                        net_change,
                        stake_before,
                        stake_after,
                        consecutive_win_streak,
                        consecutive_loss_streak,
                        game_duration_ms
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        session_id,
                        bet_id,
                        None,
                        game_index,
                        outcome,
                        payout_amount if is_win else 0,
                        loss_amount if not is_win else 0,
                        net_change,
                        stake_before,
                        stake_after,
                        win_streak,
                        loss_streak,
                        None,
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO game_records (
                        session_id,
                        bet_id,
                        odds_config_id,
                        outcome,
                        payout_amount,
                        loss_amount,
                        net_change,
                        stake_before,
                        stake_after,
                        consecutive_win_streak,
                        consecutive_loss_streak,
                        game_duration_ms
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        session_id,
                        bet_id,
                        None,
                        outcome,
                        payout_amount if is_win else 0,
                        loss_amount if not is_win else 0,
                        net_change,
                        stake_before,
                        stake_after,
                        win_streak,
                        loss_streak,
                        None,
                    ),
                )
            game_id = cursor.lastrowid
            cursor.execute(
                """
                UPDATE stake_transactions
                SET game_id = %s
                WHERE bet_id = %s AND game_id IS NULL
                """,
                (game_id, bet_id),
            )
            self.cnx.commit()
            return int(game_id)
        except Exception:
            self.cnx.rollback()
            raise
        finally:
            cursor.close()

    def _update_statistics(
        self,
        gambler_id: int,
        bet_amount: float,
        is_win: bool,
        payout_amount: float,
    ) -> None:
        cursor = self._dict_cursor()
        cursor.execute(
            "SELECT * FROM betting_statistics WHERE gambler_id = %s",
            (gambler_id,),
        )
        stats = cursor.fetchone()
        cursor.close()
        if not stats:
            return

        total_bets = int(stats["total_bets"]) + 1
        total_wins = int(stats["total_wins"]) + (1 if is_win else 0)
        total_losses = int(stats["total_losses"]) + (0 if is_win else 1)

        previous_avg = float(stats["average_bet_amount"])
        average_bet_amount = round(
            ((previous_avg * (total_bets - 1)) + bet_amount) / total_bets,
            2,
        )
        win_rate = round((total_wins / total_bets) * 100, 2)

        total_winnings = float(stats["total_winnings"])
        if is_win:
            total_winnings = round(total_winnings + payout_amount, 2)

        cursor = self.cnx.cursor()
        try:
            cursor.execute(
                """
                UPDATE betting_statistics
                SET
                    total_bets = %s,
                    total_wins = %s,
                    total_losses = %s,
                    average_bet_amount = %s,
                    win_rate = %s,
                    total_winnings = %s
                WHERE gambler_id = %s
                """,
                (
                    total_bets,
                    total_wins,
                    total_losses,
                    average_bet_amount,
                    win_rate,
                    total_winnings,
                    gambler_id,
                ),
            )
            self.cnx.commit()
        except Exception:
            self.cnx.rollback()
            raise
        finally:
            cursor.close()

    def place_bet(
        self,
        gambler_id: int,
        bet_amount: float,
        win_probability: float | None = None,
        strategy_id: int | None = None,
        strategy_name: str | None = None,
    ) -> dict[str, Any]:
        gambler = self._get_gambler(gambler_id)
        if not bool(gambler["is_active"]):
            raise ValueError("Cannot place bets for a deactivated account.")

        session = self._get_active_session(gambler_id)
        preferences = self._get_preferences(gambler_id)

        if win_probability is None:
            win_probability = self._generate_win_probability()
        self._validate_probability(win_probability)
        self._validate_session_limits(session, preferences)

        current_stake = float(gambler["current_stake"])
        self._validate_bet_amount(bet_amount, current_stake, preferences)

        odds_value = self._decimal_odds_from_probability(win_probability)
        potential_win = round(bet_amount * odds_value, 2)
        is_win = self.determine_bet_outcome(win_probability)
        payout_amount = potential_win if is_win else 0.0

        bet_id = self._insert_bet(
            session_id=int(session["session_id"]),
            gambler_id=gambler_id,
            strategy_id=strategy_id,
            amount=bet_amount,
            win_probability=win_probability,
            odds_value=odds_value,
            stake_before=current_stake,
        )

        settlement = self.stake_service.apply_bet_outcome(
            gambler_id,
            bet_amount=bet_amount,
            is_win=is_win,
            payout_amount=payout_amount,
            bet_id=bet_id,
        )

        refreshed = self._get_gambler(gambler_id)
        stake_after = float(refreshed["current_stake"])
        self._update_bet_settlement(bet_id, stake_after)

        game_id = self._insert_game_record(
            session_id=int(session["session_id"]),
            bet_id=bet_id,
            is_win=is_win,
            payout_amount=payout_amount,
            loss_amount=bet_amount,
            stake_before=current_stake,
            stake_after=stake_after,
        )

        self._update_statistics(
            gambler_id=gambler_id,
            bet_amount=bet_amount,
            is_win=is_win,
            payout_amount=payout_amount,
        )

        bet = Bet(
            bet_id=bet_id,
            gambler_id=gambler_id,
            session_id=int(session["session_id"]),
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            bet_amount=bet_amount,
            win_probability=win_probability,
            odds_value=odds_value,
            potential_win=potential_win,
            stake_before=current_stake,
            stake_after=stake_after,
            is_win=is_win,
            payout_amount=payout_amount,
        )

        return {
            "bet": bet.to_dict(),
            "game_id": game_id,
            "settlement": settlement,
        }

    def _build_strategy(
        self,
        strategy_name: str,
        strategy_config: dict[str, float] | None,
    ) -> BaseBettingStrategy:
        config = strategy_config or {}
        key = strategy_name.strip().lower()

        if key == "fixed":
            return FixedAmountStrategy(config.get("amount", 10.0))
        if key == "percentage":
            return PercentageStrategy(config.get("percentage", 5.0))
        if key == "martingale":
            return MartingaleStrategy(
                config.get("base_amount", 10.0),
                config.get("multiplier", 2.0),
            )
        if key in {"reverse_martingale", "reverse-martingale", "reversemartingale"}:
            return ReverseMartingaleStrategy(
                config.get("base_amount", 10.0),
                config.get("multiplier", 2.0),
            )
        if key == "fibonacci":
            return FibonacciStrategy(config.get("base_amount", 10.0))
        if key in {"d_alembert", "dalembert", "d'alembert"}:
            return DAlembertStrategy(
                config.get("base_amount", 10.0),
                config.get("step_amount", 5.0),
            )

        raise ValueError(
            "Unsupported strategy. Use: fixed, percentage, martingale, reverse_martingale, fibonacci, d_alembert."
        )

    def place_bet_with_strategy(
        self,
        gambler_id: int,
        strategy_name: str,
        win_probability: float | None = None,
        strategy_config: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        strategy = self._build_strategy(strategy_name, strategy_config)
        gambler = self._get_gambler(gambler_id)
        amount = strategy.next_bet(float(gambler["current_stake"]))
        strategy_id = self._ensure_strategy_row(strategy_name)

        result = self.place_bet(
            gambler_id=gambler_id,
            bet_amount=amount,
            win_probability=win_probability,
            strategy_id=strategy_id,
            strategy_name=strategy_name,
        )
        strategy.record_outcome(bool(result["bet"]["is_win"]))
        return result

    def place_consecutive_bets(
        self,
        gambler_id: int,
        strategy_name: str,
        number_of_bets: int,
        win_probability: float | None = None,
        strategy_config: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        if number_of_bets <= 0:
            raise ValueError("Number of bets must be greater than 0.")

        strategy = self._build_strategy(strategy_name, strategy_config)
        strategy_id = self._ensure_strategy_row(strategy_name)

        results = []
        for _ in range(number_of_bets):
            gambler = self._get_gambler(gambler_id)
            amount = strategy.next_bet(float(gambler["current_stake"]))
            bet_result = self.place_bet(
                gambler_id=gambler_id,
                bet_amount=amount,
                win_probability=win_probability,
                strategy_id=strategy_id,
                strategy_name=strategy_name,
            )
            strategy.record_outcome(bool(bet_result["bet"]["is_win"]))
            results.append(bet_result)

        summary = self.get_betting_session_summary(gambler_id)
        return {
            "strategy": strategy_name,
            "requested_bets": number_of_bets,
            "executed_bets": len(results),
            "results": results,
            "session_summary": summary,
        }

    def get_betting_session_summary(self, gambler_id: int) -> dict[str, Any]:
        session = self._get_active_session(gambler_id)

        cursor = self._dict_cursor()
        cursor.execute(
            """
            SELECT
                b.bet_id,
                b.gambler_id,
                b.session_id,
                b.strategy_id,
                s.strategy_name,
                b.bet_amount,
                b.win_probability,
                b.odds_value,
                b.stake_before,
                b.stake_after,
                b.placed_at,
                gr.outcome,
                gr.payout_amount
            FROM bets b
            LEFT JOIN betting_strategies s ON s.strategy_id = b.strategy_id
            LEFT JOIN game_records gr ON gr.bet_id = b.bet_id
            WHERE b.gambler_id = %s AND b.session_id = %s
            ORDER BY b.bet_id ASC
            """,
            (gambler_id, session["session_id"]),
        )
        rows = cursor.fetchall()
        cursor.close()

        bets: list[Bet] = []
        for row in rows:
            is_win = row["outcome"] == "WIN"
            payout_amount = float(row["payout_amount"] or 0)
            bet_amount = float(row["bet_amount"])
            bet = Bet(
                bet_id=int(row["bet_id"]),
                gambler_id=int(row["gambler_id"]),
                session_id=int(row["session_id"]),
                strategy_id=int(row["strategy_id"]) if row["strategy_id"] is not None else None,
                strategy_name=row["strategy_name"],
                bet_amount=bet_amount,
                win_probability=float(row["win_probability"] or 0),
                odds_value=float(row["odds_value"]),
                potential_win=round(bet_amount * float(row["odds_value"]), 2),
                stake_before=float(row["stake_before"] or 0),
                stake_after=float(row["stake_after"] or 0),
                is_win=is_win,
                payout_amount=payout_amount,
                placed_at=row["placed_at"],
            )
            bets.append(bet)

        betting_session = BettingSession(
            gambler_id=gambler_id,
            session_id=int(session["session_id"]),
            started_at=session.get("started_at"),
            ended_at=session.get("ended_at"),
            bets=bets,
        )
        return betting_session.to_dict()
