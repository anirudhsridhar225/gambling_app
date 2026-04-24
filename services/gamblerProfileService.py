from __future__ import annotations

from typing import Any

from models.bettingPreferences import BettingPreferencesCreate, BettingPreferencesUpdate
from models.gambler import (
	GamblerCreate,
	GamblerPersonalInfoUpdate,
	GamblerThresholdUpdate,
)
from models.gamblingStatistics import GamblerStatisticsDTO


class GamblerProfileService:
	def __init__(self, cnx):
		self.cnx = cnx

	def list_gamblers(self) -> list[dict[str, Any]]:
		cursor = self._dict_cursor()
		cursor.execute(
			"""
			SELECT
				id,
				username,
				full_name,
				email,
				is_active,
				initial_stake,
				current_stake,
				win_threshold,
				loss_threshold,
				min_required_stake,
				updated_at
			FROM gambler
			ORDER BY id ASC
			"""
		)
		rows = cursor.fetchall()
		cursor.close()
		return rows

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

	def create_gambler_profile(
		self,
		gambler_data: GamblerCreate,
		preferences_data: BettingPreferencesCreate,
	) -> int:
		cursor = self.cnx.cursor()

		try:
			create_gambler_sql = """
				INSERT INTO gambler (
					username, full_name, email, is_active,
					initial_stake, current_stake, win_threshold, loss_threshold, min_required_stake
				) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
			"""
			gambler_values = (
				gambler_data.username,
				gambler_data.full_name,
				str(gambler_data.email),
				True,
				gambler_data.initial_stake,
				gambler_data.initial_stake,
				gambler_data.win_threshold,
				gambler_data.loss_threshold,
				gambler_data.min_required_stake,
			)
			cursor.execute(create_gambler_sql, gambler_values)
			gambler_id = cursor.lastrowid

			create_preferences_sql = """
				INSERT INTO betting_preferences (
					gambler_id, min_bet, max_bet, preferred_game_type,
					auto_play_enabled, auto_play_max_games, session_loss_limit, session_win_target
				) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
			"""
			preference_values = (
				gambler_id,
				preferences_data.min_bet,
				preferences_data.max_bet,
				preferences_data.preferred_game_type,
				preferences_data.auto_play_enabled,
				preferences_data.auto_play_max_games,
				preferences_data.session_loss_limit,
				preferences_data.session_win_target,
			)
			cursor.execute(create_preferences_sql, preference_values)

			create_statistics_sql = """
				INSERT INTO betting_statistics (
					gambler_id, win_rate, average_bet_amount,
					total_bets, total_wins, total_losses, total_winnings
				) VALUES (%s, %s, %s, %s, %s, %s, %s)
			"""
			statistics_values = (gambler_id, 0.0, 0.0, 0, 0, 0, 0)
			cursor.execute(create_statistics_sql, statistics_values)

			self.cnx.commit()
			return gambler_id
		except Exception:
			self.cnx.rollback()
			raise
		finally:
			cursor.close()

	def update_gambler_profile(
		self,
		gambler_id: int,
		personal_info: GamblerPersonalInfoUpdate | None = None,
		preferences: BettingPreferencesUpdate | None = None,
		thresholds: GamblerThresholdUpdate | None = None,
	) -> None:
		gambler = self._get_gambler(gambler_id)
		cursor = self.cnx.cursor()

		try:
			if personal_info:
				updates = []
				values = []
				if personal_info.username is not None:
					updates.append("username = %s")
					values.append(personal_info.username)
				if personal_info.full_name is not None:
					updates.append("full_name = %s")
					values.append(personal_info.full_name)
				if personal_info.email is not None:
					updates.append("email = %s")
					values.append(str(personal_info.email))

				if updates:
					values.append(gambler_id)
					cursor.execute(
						f"UPDATE gambler SET {', '.join(updates)} WHERE id = %s",
						tuple(values),
					)

			if thresholds:
				next_win_threshold = (
					thresholds.win_threshold
					if thresholds.win_threshold is not None
					else float(gambler["win_threshold"])
				)
				next_loss_threshold = (
					thresholds.loss_threshold
					if thresholds.loss_threshold is not None
					else float(gambler["loss_threshold"])
				)
				initial_stake = float(gambler["initial_stake"])

				if next_win_threshold <= initial_stake:
					raise ValueError("Win threshold must be greater than initial stake.")
				if next_loss_threshold >= initial_stake:
					raise ValueError("Loss threshold must be less than initial stake.")

				updates = []
				values = []
				if thresholds.win_threshold is not None:
					updates.append("win_threshold = %s")
					values.append(thresholds.win_threshold)
				if thresholds.loss_threshold is not None:
					updates.append("loss_threshold = %s")
					values.append(thresholds.loss_threshold)

				if updates:
					values.append(gambler_id)
					cursor.execute(
						f"UPDATE gambler SET {', '.join(updates)} WHERE id = %s",
						tuple(values),
					)

			if preferences:
				pref_updates = []
				pref_values = []
				if preferences.min_bet is not None:
					pref_updates.append("min_bet = %s")
					pref_values.append(preferences.min_bet)
				if preferences.max_bet is not None:
					pref_updates.append("max_bet = %s")
					pref_values.append(preferences.max_bet)
				if preferences.preferred_game_type is not None:
					pref_updates.append("preferred_game_type = %s")
					pref_values.append(preferences.preferred_game_type)
				if preferences.auto_play_enabled is not None:
					pref_updates.append("auto_play_enabled = %s")
					pref_values.append(preferences.auto_play_enabled)
				if preferences.auto_play_max_games is not None:
					pref_updates.append("auto_play_max_games = %s")
					pref_values.append(preferences.auto_play_max_games)
				if preferences.session_loss_limit is not None:
					pref_updates.append("session_loss_limit = %s")
					pref_values.append(preferences.session_loss_limit)
				if preferences.session_win_target is not None:
					pref_updates.append("session_win_target = %s")
					pref_values.append(preferences.session_win_target)

				if pref_updates:
					pref_values.append(gambler_id)
					cursor.execute(
						f"UPDATE betting_preferences SET {', '.join(pref_updates)} WHERE gambler_id = %s",
						tuple(pref_values),
					)

			self.cnx.commit()
		except Exception:
			self.cnx.rollback()
			raise
		finally:
			cursor.close()

	def retrieve_gambler_statistics(self, gambler_id: int) -> dict[str, Any]:
		gambler = self._get_gambler(gambler_id)

		cursor = self._dict_cursor()
		cursor.execute(
			"SELECT * FROM betting_preferences WHERE gambler_id = %s",
			(gambler_id,),
		)
		preferences = cursor.fetchone() or {}

		cursor.execute(
			"SELECT * FROM betting_statistics WHERE gambler_id = %s",
			(gambler_id,),
		)
		stats = cursor.fetchone()
		cursor.close()

		if not stats:
			raise ValueError(f"Statistics were not found for gambler {gambler_id}.")

		current_stake = float(gambler["current_stake"])
		initial_stake = float(gambler["initial_stake"])
		net_profit_or_loss = round(current_stake - initial_stake, 2)

		statistics = GamblerStatisticsDTO(
			gambler_id=gambler_id,
			total_bets=int(stats["total_bets"]),
			total_wins=int(stats["total_wins"]),
			total_losses=int(stats["total_losses"]),
			total_winnings=float(stats["total_winnings"]),
			win_rate=float(stats["win_rate"]),
			average_bet_amount=float(stats["average_bet_amount"]),
			net_profit_or_loss=net_profit_or_loss,
			reached_win_threshold=current_stake >= float(gambler["win_threshold"]),
			reached_loss_threshold=current_stake <= float(gambler["loss_threshold"]),
		)

		return {
			"gambler": gambler,
			"preferences": preferences,
			"statistics": statistics.to_dict(),
		}

	def validate_gambler_eligibility(self, gambler_id: int) -> dict[str, Any]:
		gambler = self._get_gambler(gambler_id)

		current_stake = float(gambler["current_stake"])
		min_required_stake = float(gambler["min_required_stake"])
		reached_win_threshold = current_stake >= float(gambler["win_threshold"])
		reached_loss_threshold = current_stake <= float(gambler["loss_threshold"])

		reasons = []
		if not bool(gambler["is_active"]):
			reasons.append("Account is deactivated.")
		if current_stake < min_required_stake:
			reasons.append("Current stake is below minimum required stake.")
		if reached_win_threshold:
			reasons.append("Win threshold reached.")
		if reached_loss_threshold:
			reasons.append("Loss threshold reached.")

		return {
			"gambler_id": gambler_id,
			"is_eligible": len(reasons) == 0,
			"reasons": reasons,
			"current_stake": current_stake,
			"min_required_stake": min_required_stake,
		}

	def reset_gambler_profile_for_new_session(
		self,
		gambler_id: int,
		new_initial_stake: float | None = None,
	) -> dict[str, float]:
		gambler = self._get_gambler(gambler_id)
		cursor = self.cnx.cursor()

		try:
			old_initial_stake = float(gambler["initial_stake"])
			old_win_threshold = float(gambler["win_threshold"])
			old_loss_threshold = float(gambler["loss_threshold"])

			target_initial_stake = (
				float(new_initial_stake)
				if new_initial_stake is not None
				else old_initial_stake
			)

			if target_initial_stake <= 0:
				raise ValueError("New initial stake must be greater than 0.")

			win_ratio = old_win_threshold / old_initial_stake
			loss_ratio = old_loss_threshold / old_initial_stake

			next_win_threshold = round(target_initial_stake * win_ratio, 2)
			next_loss_threshold = round(target_initial_stake * loss_ratio, 2)

			cursor.execute(
				"""
				UPDATE gambler
				SET
					initial_stake = %s,
					current_stake = %s,
					win_threshold = %s,
					loss_threshold = %s,
					is_active = %s
				WHERE id = %s
				""",
				(
					target_initial_stake,
					target_initial_stake,
					next_win_threshold,
					next_loss_threshold,
					True,
					gambler_id,
				),
			)

			cursor.execute(
				"""
				UPDATE betting_statistics
				SET
					win_rate = 0,
					average_bet_amount = 0,
					total_bets = 0,
					total_wins = 0,
					total_losses = 0,
					total_winnings = 0
				WHERE gambler_id = %s
				""",
				(gambler_id,),
			)

			self.cnx.commit()
			return {
				"initial_stake": target_initial_stake,
				"win_threshold": next_win_threshold,
				"loss_threshold": next_loss_threshold,
			}
		except Exception:
			self.cnx.rollback()
			raise
		finally:
			cursor.close()

	def record_bet_result(
		self,
		gambler_id: int,
		bet_amount: float,
		is_win: bool,
		payout_amount: float = 0.0,
	) -> dict[str, Any]:
		if bet_amount <= 0:
			raise ValueError("Bet amount must be greater than 0.")

		gambler = self._get_gambler(gambler_id)
		if not bool(gambler["is_active"]):
			raise ValueError("Cannot place bets for a deactivated account.")

		cursor = self._dict_cursor()
		cursor.execute(
			"SELECT * FROM betting_statistics WHERE gambler_id = %s",
			(gambler_id,),
		)
		stats = cursor.fetchone()
		cursor.close()

		if not stats:
			raise ValueError(f"Statistics were not found for gambler {gambler_id}.")

		current_stake = float(gambler["current_stake"])
		new_stake = current_stake + payout_amount if is_win else current_stake - bet_amount
		if new_stake < 0:
			raise ValueError("Insufficient stake for this bet.")

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
			total_winnings += payout_amount

		cursor = self.cnx.cursor()
		try:
			cursor.execute(
				"UPDATE gambler SET current_stake = %s WHERE id = %s",
				(new_stake, gambler_id),
			)
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

		return self.validate_gambler_eligibility(gambler_id)

	def deactivate_account(self, gambler_id: int) -> None:
		self._get_gambler(gambler_id)
		cursor = self.cnx.cursor()
		try:
			cursor.execute(
				"UPDATE gambler SET is_active = %s WHERE id = %s",
				(False, gambler_id),
			)
			self.cnx.commit()
		except Exception:
			self.cnx.rollback()
			raise
		finally:
			cursor.close()

	def delete_gambler_profile(self, gambler_id: int) -> None:
		self._get_gambler(gambler_id)
		cursor = self.cnx.cursor()
		try:
			# Delete children first to satisfy foreign key constraints.
			cursor.execute("DELETE FROM stake_transactions WHERE gambler_id = %s", (gambler_id,))
			cursor.execute(
				"""
				DELETE gr
				FROM game_records gr
				INNER JOIN sessions s ON s.session_id = gr.session_id
				WHERE s.gambler_id = %s
				""",
				(gambler_id,),
			)
			cursor.execute(
				"""
				DELETE b
				FROM bets b
				INNER JOIN sessions s ON s.session_id = b.session_id
				WHERE s.gambler_id = %s
				""",
				(gambler_id,),
			)
			cursor.execute("DELETE FROM betting_statistics WHERE gambler_id = %s", (gambler_id,))
			cursor.execute("DELETE FROM betting_preferences WHERE gambler_id = %s", (gambler_id,))
			cursor.execute("DELETE FROM sessions WHERE gambler_id = %s", (gambler_id,))
			cursor.execute("DELETE FROM gambler WHERE id = %s", (gambler_id,))
			self.cnx.commit()
		except Exception:
			self.cnx.rollback()
			raise
		finally:
			cursor.close()
