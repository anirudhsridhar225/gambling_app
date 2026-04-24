from __future__ import annotations

from collections import Counter
from threading import RLock
from typing import Any

from models.stakeManagement import (
    StakeBoundary,
    StakeHistoryReport,
    StakeMonitor,
    StakeTransaction,
    TransactionType,
)


class StakeManagementService:
    def __init__(self, cnx):
        self.cnx = cnx
        self._lock = RLock()
        self._supported_db_transaction_types = self._load_supported_transaction_types()
        self._has_transaction_ref = self._column_exists("stake_transactions", "transaction_ref")
        self._has_transaction_created_at = self._column_exists("stake_transactions", "created_at")

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

    def _load_supported_transaction_types(self) -> set[str]:
        cursor = self.cnx.cursor()
        cursor.execute(
            """
            SELECT COLUMN_TYPE
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'stake_transactions'
              AND COLUMN_NAME = 'transaction_type'
            """
        )
        row = cursor.fetchone()
        cursor.close()

        if not row:
            return {"BET", "WIN", "LOSS", "ADJUSTMENT"}

        column_type = str(row[0])
        # Example: enum('BET','WIN','LOSS','ADJUSTMENT')
        if not column_type.startswith("enum("):
            return {"BET", "WIN", "LOSS", "ADJUSTMENT"}

        values: set[str] = set()
        inner = column_type[len("enum("):-1]
        for part in inner.split(","):
            values.add(part.strip().strip("'"))
        return values

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

    def _get_active_session(self, gambler_id: int) -> dict[str, Any] | None:
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
        return session

    def _get_session_transactions(
        self,
        gambler_id: int,
        session_id: int | None = None,
        transaction_type: TransactionType | None = None,
    ) -> list[dict[str, Any]]:
        cursor = self._dict_cursor()
        query = [
            "SELECT * FROM stake_transactions WHERE gambler_id = %s",
        ]
        values: list[Any] = [gambler_id]
        if session_id is not None:
            query.append("AND session_id = %s")
            values.append(session_id)
        if transaction_type is not None:
            query.append("AND transaction_type = %s")
            values.append(transaction_type.db_value)
        query.append("ORDER BY created_at ASC, transaction_id ASC")
        cursor.execute(" ".join(query), tuple(values))
        rows = cursor.fetchall()
        cursor.close()
        return rows

    def _normalize_transaction_type(self, transaction_type: TransactionType) -> str:
        preferred = transaction_type.db_value
        if preferred in self._supported_db_transaction_types:
            return preferred

        fallback_order = ["ADJUSTMENT", "BET", "WIN", "LOSS"]
        for fallback in fallback_order:
            if fallback in self._supported_db_transaction_types:
                return fallback

        raise ValueError("No supported transaction_type values were found in stake_transactions.")

    def _row_to_transaction_type(self, row: dict[str, Any]) -> TransactionType:
        ref_value = row.get("transaction_ref")
        if ref_value:
            try:
                return TransactionType(str(ref_value))
            except ValueError:
                pass

        mapped_type = row["transaction_type"]
        reverse_map = {
            "BET": TransactionType.BET_PLACED,
            "WIN": TransactionType.BET_WIN,
            "LOSS": TransactionType.BET_LOSS,
            "ADJUSTMENT": TransactionType.ADJUSTMENT,
        }
        if mapped_type in reverse_map:
            return reverse_map[mapped_type]
        return TransactionType(mapped_type)

    def _record_transaction(
        self,
        cursor,
        session_id: int,
        gambler_id: int,
        transaction_type: TransactionType,
        amount: float,
        balance_before: float,
        balance_after: float,
        bet_id: int | None = None,
        game_id: int | None = None,
    ) -> StakeTransaction:
        db_type = self._normalize_transaction_type(transaction_type)
        created_at = None
        if self._has_transaction_ref:
            cursor.execute(
                """
                INSERT INTO stake_transactions (
                    session_id,
                    gambler_id,
                    bet_id,
                    game_id,
                    transaction_type,
                    amount,
                    balance_before,
                    balance_after,
                    transaction_ref
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session_id,
                    gambler_id,
                    bet_id,
                    game_id,
                    db_type,
                    amount,
                    balance_before,
                    balance_after,
                    transaction_type.value,
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO stake_transactions (
                    session_id,
                    gambler_id,
                    bet_id,
                    game_id,
                    transaction_type,
                    amount,
                    balance_before,
                    balance_after
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session_id,
                    gambler_id,
                    bet_id,
                    game_id,
                    db_type,
                    amount,
                    balance_before,
                    balance_after,
                ),
            )

        transaction_id = cursor.lastrowid
        if self._has_transaction_created_at:
            cursor.execute(
                "SELECT created_at FROM stake_transactions WHERE transaction_id = %s",
                (transaction_id,),
            )
            row = cursor.fetchone()
            if row:
                created_at = row[0]

        return StakeTransaction(
            gambler_id=gambler_id,
            session_id=session_id,
            transaction_type=transaction_type,
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            transaction_id=transaction_id,
            bet_id=bet_id,
            game_id=game_id,
            created_at=created_at,
        )

    def initialize_stake_session(
        self,
        gambler_id: int,
        starting_stake: float,
        lower_limit: float,
        upper_limit: float,
        max_games: int | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            gambler = self._get_gambler(gambler_id)
            if self._get_active_session(gambler_id):
                raise ValueError("An active stake session already exists for this gambler.")

            if starting_stake <= 0:
                raise ValueError("Starting stake must be greater than 0.")

            boundary = StakeBoundary(lower_limit=lower_limit, upper_limit=upper_limit)
            if not boundary.is_within_bounds(starting_stake):
                raise ValueError("Starting stake must be within the configured boundaries.")

            cursor = self.cnx.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO sessions (
                        gambler_id,
                        status,
                        starting_stake,
                        ending_stake,
                        peak_stake,
                        lowest_stake,
                        lower_limit,
                        upper_limit,
                        max_games,
                        games_played
                    ) VALUES (%s, 'ACTIVE', %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        gambler_id,
                        starting_stake,
                        starting_stake,
                        starting_stake,
                        starting_stake,
                        boundary.lower_limit,
                        boundary.upper_limit,
                        max_games,
                        0,
                    ),
                )
                session_id = cursor.lastrowid
                cursor.execute(
                    "UPDATE gambler SET current_stake = %s WHERE id = %s",
                    (starting_stake, gambler_id),
                )

                self._record_transaction(
                    cursor,
                    session_id=session_id,
                    gambler_id=gambler_id,
                    transaction_type=TransactionType.INITIAL_STAKE,
                    amount=starting_stake,
                    balance_before=0.0,
                    balance_after=starting_stake,
                )
                self.cnx.commit()
            except Exception:
                self.cnx.rollback()
                raise
            finally:
                cursor.close()

            return {
                "gambler_id": gambler_id,
                "username": gambler["username"],
                "session_id": session_id,
                "starting_stake": starting_stake,
                "boundaries": boundary.to_dict(),
                "warnings": boundary.warning_messages(starting_stake),
            }

    def track_current_stake(self, gambler_id: int) -> dict[str, Any]:
        gambler = self._get_gambler(gambler_id)
        session = self._get_active_session(gambler_id)
        warnings = []
        boundary_data = None
        if session:
            boundary = StakeBoundary(
                lower_limit=float(session["lower_limit"]),
                upper_limit=float(session["upper_limit"]),
            )
            boundary_data = boundary.to_dict()
            warnings = boundary.warning_messages(gambler["current_stake"])

        return {
            "gambler_id": gambler_id,
            "current_stake": float(gambler["current_stake"]),
            "is_active": bool(gambler["is_active"]),
            "session": session,
            "boundaries": boundary_data,
            "warnings": warnings,
        }

    def _update_session_snapshot(
        self,
        cursor,
        session_id: int,
        balance_after: float,
        games_played_increment: int = 0,
    ) -> None:
        cursor.execute(
            """
            UPDATE sessions
            SET
                ending_stake = %s,
                peak_stake = GREATEST(COALESCE(peak_stake, %s), %s),
                lowest_stake = LEAST(COALESCE(lowest_stake, %s), %s),
                games_played = games_played + %s
            WHERE session_id = %s
            """,
            (
                balance_after,
                balance_after,
                balance_after,
                balance_after,
                balance_after,
                games_played_increment,
                session_id,
            ),
        )

    def apply_bet_outcome(
        self,
        gambler_id: int,
        bet_amount: float,
        is_win: bool,
        payout_amount: float = 0.0,
        bet_id: int | None = None,
        game_id: int | None = None,
    ) -> dict[str, Any]:
        if bet_amount <= 0:
            raise ValueError("Bet amount must be greater than 0.")
        if payout_amount < 0:
            raise ValueError("Payout amount cannot be negative.")

        with self._lock:
            gambler = self._get_gambler(gambler_id)
            session = self._get_active_session(gambler_id)
            if not session:
                raise ValueError("No active stake session found for this gambler.")

            boundary = StakeBoundary(
                lower_limit=float(session["lower_limit"]),
                upper_limit=float(session["upper_limit"]),
            )

            current_balance = float(gambler["current_stake"])
            if bet_amount > current_balance:
                raise ValueError("Insufficient stake for this bet.")

            post_placement_balance = round(current_balance - bet_amount, 2)
            if not boundary.is_within_bounds(post_placement_balance):
                raise ValueError("Placing this bet would move the stake outside the lower boundary.")

            final_balance = post_placement_balance
            if is_win:
                final_balance = round(post_placement_balance + payout_amount, 2)
                if not boundary.is_within_bounds(final_balance):
                    raise ValueError("Winning this bet would move the stake outside the upper boundary.")

            cursor = self.cnx.cursor()
            try:
                placement_tx = self._record_transaction(
                    cursor,
                    session_id=int(session["session_id"]),
                    gambler_id=gambler_id,
                    transaction_type=TransactionType.BET_PLACED,
                    amount=bet_amount,
                    balance_before=current_balance,
                    balance_after=post_placement_balance,
                    bet_id=bet_id,
                    game_id=game_id,
                )

                if is_win:
                    result_tx = self._record_transaction(
                        cursor,
                        session_id=int(session["session_id"]),
                        gambler_id=gambler_id,
                        transaction_type=TransactionType.BET_WIN,
                        amount=payout_amount,
                        balance_before=post_placement_balance,
                        balance_after=final_balance,
                        bet_id=bet_id,
                        game_id=game_id,
                    )
                else:
                    result_tx = self._record_transaction(
                        cursor,
                        session_id=int(session["session_id"]),
                        gambler_id=gambler_id,
                        transaction_type=TransactionType.BET_LOSS,
                        amount=bet_amount,
                        balance_before=post_placement_balance,
                        balance_after=final_balance,
                        bet_id=bet_id,
                        game_id=game_id,
                    )

                cursor.execute(
                    "UPDATE gambler SET current_stake = %s WHERE id = %s",
                    (final_balance, gambler_id),
                )
                self._update_session_snapshot(
                    cursor,
                    session_id=int(session["session_id"]),
                    balance_after=final_balance,
                    games_played_increment=1,
                )
                self.cnx.commit()
            except Exception:
                self.cnx.rollback()
                raise
            finally:
                cursor.close()

            monitor = self.monitor_stake_fluctuations(gambler_id)
            return {
                "placement": placement_tx.to_dict(),
                "result": result_tx.to_dict(),
                "monitor": monitor,
                "warnings": boundary.warning_messages(final_balance),
            }

    def deposit_funds(self, gambler_id: int, amount: float) -> dict[str, Any]:
        return self._apply_adjustment(gambler_id, amount, TransactionType.DEPOSIT)

    def withdraw_funds(self, gambler_id: int, amount: float) -> dict[str, Any]:
        return self._apply_adjustment(gambler_id, amount, TransactionType.WITHDRAWAL)

    def adjust_stake(self, gambler_id: int, amount: float) -> dict[str, Any]:
        if amount >= 0:
            return self._apply_adjustment(gambler_id, amount, TransactionType.ADJUSTMENT)
        return self._apply_adjustment(gambler_id, abs(amount), TransactionType.WITHDRAWAL)

    def _apply_adjustment(
        self,
        gambler_id: int,
        amount: float,
        transaction_type: TransactionType,
    ) -> dict[str, Any]:
        if amount <= 0:
            raise ValueError("Amount must be greater than 0.")

        with self._lock:
            gambler = self._get_gambler(gambler_id)
            session = self._get_active_session(gambler_id)
            if not session:
                raise ValueError("No active stake session found for this gambler.")

            boundary = StakeBoundary(
                lower_limit=float(session["lower_limit"]),
                upper_limit=float(session["upper_limit"]),
            )
            current_balance = float(gambler["current_stake"])
            next_balance = current_balance

            if transaction_type in {TransactionType.WITHDRAWAL}:
                next_balance = round(current_balance - amount, 2)
            else:
                next_balance = round(current_balance + amount, 2)

            if not boundary.is_within_bounds(next_balance):
                raise ValueError("This transaction would move the stake outside the configured boundaries.")

            cursor = self.cnx.cursor()
            try:
                tx = self._record_transaction(
                    cursor,
                    session_id=int(session["session_id"]),
                    gambler_id=gambler_id,
                    transaction_type=transaction_type,
                    amount=amount,
                    balance_before=current_balance,
                    balance_after=next_balance,
                )
                cursor.execute(
                    "UPDATE gambler SET current_stake = %s WHERE id = %s",
                    (next_balance, gambler_id),
                )
                self._update_session_snapshot(cursor, int(session["session_id"]), next_balance)
                self.cnx.commit()
            except Exception:
                self.cnx.rollback()
                raise
            finally:
                cursor.close()

            return {
                "transaction": tx.to_dict(),
                "warnings": boundary.warning_messages(next_balance),
                "current_stake": next_balance,
            }

    def validate_stake_boundaries(self, gambler_id: int) -> dict[str, Any]:
        gambler = self._get_gambler(gambler_id)
        session = self._get_active_session(gambler_id)
        if not session:
            raise ValueError("No active stake session found for this gambler.")

        boundary = StakeBoundary(
            lower_limit=float(session["lower_limit"]),
            upper_limit=float(session["upper_limit"]),
        )
        current_stake = float(gambler["current_stake"])
        return {
            "gambler_id": gambler_id,
            "current_stake": current_stake,
            "within_bounds": boundary.is_within_bounds(current_stake),
            "warnings": boundary.warning_messages(current_stake),
            "boundaries": boundary.to_dict(),
            "session_id": session["session_id"],
        }

    def monitor_stake_fluctuations(self, gambler_id: int) -> dict[str, Any]:
        gambler = self._get_gambler(gambler_id)
        session = self._get_active_session(gambler_id)
        if not session:
            raise ValueError("No active stake session found for this gambler.")

        rows = self._get_session_transactions(gambler_id, session_id=int(session["session_id"]))
        monitor = StakeMonitor(
            session_id=int(session["session_id"]),
            starting_stake=float(session["starting_stake"]),
            current_stake=float(gambler["current_stake"]),
            peak_stake=float(session["peak_stake"] or gambler["current_stake"]),
            lowest_stake=float(session["lowest_stake"] or gambler["current_stake"]),
        )
        for row in rows:
            monitor.record(
                StakeTransaction(
                    transaction_id=row["transaction_id"],
                    session_id=row["session_id"],
                    gambler_id=row["gambler_id"],
                    bet_id=row["bet_id"],
                    game_id=row["game_id"],
                    transaction_type=self._row_to_transaction_type(row),
                    amount=float(row["amount"]),
                    balance_before=float(row["balance_before"] or 0),
                    balance_after=float(row["balance_after"] or 0),
                    created_at=row["created_at"],
                )
            )

        return monitor.to_dict()

    def generate_stake_history_report(
        self,
        gambler_id: int,
        session_id: int | None = None,
        transaction_type: TransactionType | None = None,
    ) -> dict[str, Any]:
        gambler = self._get_gambler(gambler_id)
        if session_id is None:
            active_session = self._get_active_session(gambler_id)
            if active_session:
                session_id = int(active_session["session_id"])
                session = active_session
            else:
                cursor = self._dict_cursor()
                cursor.execute(
                    """
                    SELECT *
                    FROM sessions
                    WHERE gambler_id = %s
                    ORDER BY session_id DESC
                    LIMIT 1
                    """,
                    (gambler_id,),
                )
                session = cursor.fetchone()
                cursor.close()
                session_id = int(session["session_id"]) if session else None
        else:
            session = None

        rows = self._get_session_transactions(
            gambler_id,
            session_id=session_id,
            transaction_type=transaction_type,
        )
        transactions: list[StakeTransaction] = []
        for row in rows:
            transaction = StakeTransaction(
                transaction_id=row["transaction_id"],
                session_id=row["session_id"],
                gambler_id=row["gambler_id"],
                bet_id=row["bet_id"],
                game_id=row["game_id"],
                transaction_type=self._row_to_transaction_type(row),
                amount=float(row["amount"]),
                balance_before=float(row["balance_before"] or 0),
                balance_after=float(row["balance_after"] or 0),
                created_at=row["created_at"],
            )
            transactions.append(transaction)

        if session is None and session_id is not None:
            cursor = self._dict_cursor()
            cursor.execute("SELECT * FROM sessions WHERE session_id = %s", (session_id,))
            session = cursor.fetchone()
            cursor.close()

        starting_stake = float(session["starting_stake"] if session else gambler["initial_stake"])
        current_stake = float(
            session["ending_stake"] if session and session["ending_stake"] is not None else gambler["current_stake"]
        )
        peak_stake = float(session["peak_stake"] if session else current_stake)
        lowest_stake = float(session["lowest_stake"] if session else current_stake)
        net_profit_or_loss = round(current_stake - starting_stake, 2)

        monitor = StakeMonitor(
            session_id=session_id,
            starting_stake=starting_stake,
            current_stake=current_stake,
            peak_stake=peak_stake,
            lowest_stake=lowest_stake,
        )
        for transaction in transactions:
            monitor.record(transaction)

        breakdown = Counter(transaction.transaction_type.value for transaction in transactions)
        report = StakeHistoryReport(
            gambler_id=gambler_id,
            session_id=session_id,
            starting_stake=starting_stake,
            current_stake=current_stake,
            peak_stake=max(monitor.peak_stake, peak_stake),
            lowest_stake=min(monitor.lowest_stake, lowest_stake),
            net_profit_or_loss=net_profit_or_loss,
            volatility=monitor.volatility,
            transaction_breakdown=dict(breakdown),
            transactions=transactions,
        )
        return report.to_dict()
