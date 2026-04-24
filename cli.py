from __future__ import annotations

import json
from decimal import Decimal
from datetime import datetime
from typing import Any
import random

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from models.bettingPreferences import BettingPreferencesCreate, BettingPreferencesUpdate
from models.gambler import GamblerCreate, GamblerPersonalInfoUpdate, GamblerThresholdUpdate
from models.stakeManagement import TransactionType
from services.bettingService import BettingService
from services.gamblerProfileService import GamblerProfileService
from services.stakeManagementService import StakeManagementService

console = Console()


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _pretty_json(data: Any) -> str:
    return json.dumps(data, indent=2, default=_json_default)


def _to_float(value: str, field_name: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid number.") from exc


def _to_int(value: str, field_name: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a valid integer.") from exc


def _prompt_required_text(label: str) -> str:
    while True:
        value = Prompt.ask(label).strip()
        if value:
            return value
        console.print("[red]Value is required.[/red]")


def _prompt_required_float(label: str) -> float:
    while True:
        value = Prompt.ask(label).strip()
        try:
            return _to_float(value, label)
        except ValueError as err:
            console.print(f"[red]{err}[/red]")


def _prompt_optional_float(label: str) -> float | None:
    value = Prompt.ask(label, default="").strip()
    if not value:
        return None
    return _to_float(value, label)


def _prompt_optional_int(label: str) -> int | None:
    value = Prompt.ask(label, default="").strip()
    if not value:
        return None
    return _to_int(value, label)


def _prompt_optional_text(label: str) -> str | None:
    value = Prompt.ask(label, default="").strip()
    return value or None


def _prompt_gambler_id() -> int:
    while True:
        value = Prompt.ask("Enter gambler ID").strip()
        try:
            gambler_id = _to_int(value, "Gambler ID")
            if gambler_id <= 0:
                raise ValueError("Gambler ID must be greater than 0.")
            return gambler_id
        except ValueError as err:
            console.print(f"[red]{err}[/red]")


def _print_gamblers_table(rows: list[dict[str, Any]]) -> None:
    table = Table(title="Gambler Profiles")
    table.add_column("ID", justify="right")
    table.add_column("Username")
    table.add_column("Name")
    table.add_column("Email")
    table.add_column("Active")
    table.add_column("Initial")
    table.add_column("Current")
    table.add_column("Updated")

    for row in rows:
        table.add_row(
            str(row["id"]),
            str(row["username"]),
            str(row["full_name"]),
            str(row["email"]),
            "Yes" if bool(row["is_active"]) else "No",
            f"{float(row['initial_stake']):.2f}",
            f"{float(row['current_stake']):.2f}",
            str(row["updated_at"]),
        )

    console.print(table)


def _create_profile(service: GamblerProfileService) -> None:
    try:
        console.print("\n[bold]Create New Gambler[/bold]")
        gambler = GamblerCreate(
            username=_prompt_required_text("Username"),
            full_name=_prompt_required_text("Full name"),
            email=_prompt_required_text("Email"),
            initial_stake=_prompt_required_float("Initial stake"),
            win_threshold=_prompt_required_float("Win threshold"),
            loss_threshold=_prompt_required_float("Loss threshold"),
            min_required_stake=_prompt_required_float("Minimum required stake"),
        )

        auto_play_enabled = Confirm.ask("Enable auto-play?", default=False)

        preferences = BettingPreferencesCreate(
            min_bet=_prompt_required_float("Minimum bet"),
            max_bet=_prompt_required_float("Maximum bet"),
            preferred_game_type=_prompt_optional_text("Preferred game type (optional)"),
            auto_play_enabled=auto_play_enabled,
            auto_play_max_games=(
                _to_int(_prompt_required_text("Auto-play max games"), "Auto-play max games")
                if auto_play_enabled
                else None
            ),
            session_loss_limit=_prompt_optional_float("Session loss limit (optional)"),
            session_win_target=_prompt_optional_float("Session win target (optional)"),
        )

        gambler_id = service.create_gambler_profile(gambler, preferences)
        console.print(f"[green]Gambler created with ID {gambler_id}.[/green]")
    except Exception as err:
        console.print(f"[red]Create failed: {err}[/red]")


def _list_profiles(service: GamblerProfileService) -> None:
    rows = service.list_gamblers()
    if not rows:
        console.print("[yellow]No gamblers found.[/yellow]")
        return
    _print_gamblers_table(rows)


def _view_profile(service: GamblerProfileService) -> None:
    try:
        gambler_id = _prompt_gambler_id()
        profile = service.retrieve_gambler_statistics(gambler_id)

        gambler = profile["gambler"]
        prefs = profile["preferences"]
        stats = profile["statistics"]

        console.print(Panel.fit(_pretty_json(gambler), title="Gambler"))
        console.print(Panel.fit(_pretty_json(prefs), title="Betting Preferences"))
        console.print(Panel.fit(_pretty_json(stats), title="Statistics"))
    except Exception as err:
        console.print(f"[red]Retrieve failed: {err}[/red]")


def _update_profile(service: GamblerProfileService) -> None:
    try:
        gambler_id = _prompt_gambler_id()
        console.print("Leave any field blank to keep current value.")

        personal_info = GamblerPersonalInfoUpdate(
            username=_prompt_optional_text("Username"),
            full_name=_prompt_optional_text("Full name"),
            email=_prompt_optional_text("Email"),
        )

        thresholds = GamblerThresholdUpdate(
            win_threshold=_prompt_optional_float("Win threshold"),
            loss_threshold=_prompt_optional_float("Loss threshold"),
        )

        auto_play_toggle = _prompt_optional_text("Auto-play enabled? (true/false)")
        auto_play_enabled = None
        if auto_play_toggle is not None:
            lowered = auto_play_toggle.lower()
            if lowered in {"true", "t", "yes", "y", "1"}:
                auto_play_enabled = True
            elif lowered in {"false", "f", "no", "n", "0"}:
                auto_play_enabled = False
            else:
                raise ValueError("Auto-play enabled must be true or false.")

        preferences = BettingPreferencesUpdate(
            min_bet=_prompt_optional_float("Minimum bet"),
            max_bet=_prompt_optional_float("Maximum bet"),
            preferred_game_type=_prompt_optional_text("Preferred game type"),
            auto_play_enabled=auto_play_enabled,
            auto_play_max_games=_prompt_optional_int("Auto-play max games"),
            session_loss_limit=_prompt_optional_float("Session loss limit"),
            session_win_target=_prompt_optional_float("Session win target"),
        )

        has_personal = any(
            [personal_info.username, personal_info.full_name, personal_info.email]
        )
        has_thresholds = any(
            [thresholds.win_threshold is not None, thresholds.loss_threshold is not None]
        )
        has_preferences = any(
            [
                preferences.min_bet is not None,
                preferences.max_bet is not None,
                preferences.preferred_game_type is not None,
                preferences.auto_play_enabled is not None,
                preferences.auto_play_max_games is not None,
                preferences.session_loss_limit is not None,
                preferences.session_win_target is not None,
            ]
        )

        if not has_personal and not has_thresholds and not has_preferences:
            console.print("[yellow]No changes entered.[/yellow]")
            return

        service.update_gambler_profile(
            gambler_id,
            personal_info=personal_info if has_personal else None,
            thresholds=thresholds if has_thresholds else None,
            preferences=preferences if has_preferences else None,
        )
        console.print("[green]Gambler profile updated.[/green]")
    except Exception as err:
        console.print(f"[red]Update failed: {err}[/red]")


def _delete_profile(service: GamblerProfileService) -> None:
    try:
        gambler_id = _prompt_gambler_id()
        if not Confirm.ask(f"Delete gambler {gambler_id}? This cannot be undone.", default=False):
            console.print("[yellow]Delete cancelled.[/yellow]")
            return
        service.delete_gambler_profile(gambler_id)
        console.print("[green]Gambler deleted.[/green]")
    except Exception as err:
        console.print(f"[red]Delete failed: {err}[/red]")


def _validate_eligibility(service: GamblerProfileService) -> None:
    try:
        gambler_id = _prompt_gambler_id()
        result = service.validate_gambler_eligibility(gambler_id)
        console.print(Panel.fit(_pretty_json(result), title="Eligibility"))
    except Exception as err:
        console.print(f"[red]Validation failed: {err}[/red]")


def _reset_profile(service: GamblerProfileService) -> None:
    try:
        gambler_id = _prompt_gambler_id()
        new_initial_stake = _prompt_optional_float("New initial stake (blank keeps current initial)")
        result = service.reset_gambler_profile_for_new_session(
            gambler_id, new_initial_stake=new_initial_stake
        )
        console.print(Panel.fit(_pretty_json(result), title="Reset Result"))
    except Exception as err:
        console.print(f"[red]Reset failed: {err}[/red]")


def _record_bet(service: GamblerProfileService) -> None:
    try:
        gambler_id = _prompt_gambler_id()
        bet_amount = _prompt_required_float("Bet amount")
        is_win = Confirm.ask("Was this a winning bet?", default=False)
        payout_amount = 0.0
        if is_win:
            payout_amount = _prompt_required_float("Payout amount")

        result = service.record_bet_result(
            gambler_id,
            bet_amount=bet_amount,
            is_win=is_win,
            payout_amount=payout_amount,
        )
        console.print(Panel.fit(_pretty_json(result), title="Bet Recorded"))
    except Exception as err:
        console.print(f"[red]Record bet failed: {err}[/red]")


def _deactivate_profile(service: GamblerProfileService) -> None:
    try:
        gambler_id = _prompt_gambler_id()
        service.deactivate_account(gambler_id)
        console.print("[green]Account deactivated.[/green]")
    except Exception as err:
        console.print(f"[red]Deactivate failed: {err}[/red]")


def _prompt_transaction_type(include_all: bool = False) -> TransactionType | None:
    options = [item.value for item in TransactionType]
    if include_all:
        options = ["ALL"] + options
    choice = Prompt.ask("Transaction type", choices=options, default="ALL" if include_all else options[0])
    if include_all and choice == "ALL":
        return None
    return TransactionType(choice)


def _initialize_stake_session(stake_service: StakeManagementService) -> None:
    try:
        gambler_id = _prompt_gambler_id()
        starting_stake = _prompt_required_float("Starting stake")
        lower_limit = _prompt_required_float("Lower limit")
        upper_limit = _prompt_required_float("Upper limit")
        max_games_value = _prompt_optional_int("Max games (optional)")

        result = stake_service.initialize_stake_session(
            gambler_id,
            starting_stake=starting_stake,
            lower_limit=lower_limit,
            upper_limit=upper_limit,
            max_games=max_games_value,
        )
        console.print(Panel.fit(_pretty_json(result), title="Stake Session Initialized"))
    except Exception as err:
        console.print(f"[red]Initialize stake session failed: {err}[/red]")


def _track_stake(stake_service: StakeManagementService) -> None:
    try:
        gambler_id = _prompt_gambler_id()
        result = stake_service.track_current_stake(gambler_id)
        console.print(Panel.fit(_pretty_json(result), title="Current Stake"))
    except Exception as err:
        console.print(f"[red]Track stake failed: {err}[/red]")


def _apply_bet_outcome(stake_service: StakeManagementService) -> None:
    try:
        gambler_id = _prompt_gambler_id()
        bet_amount = _prompt_required_float("Bet amount")
        # is_win = Confirm.ask("Was the bet a win?", default=False)
        is_win = True if (random.random() > 0.5) else False
        payout_amount = _prompt_required_float("Payout amount") if is_win else 0.0
        result = stake_service.apply_bet_outcome(
            gambler_id,
            bet_amount=bet_amount,
            is_win=is_win,
            payout_amount=payout_amount,
        )
        console.print(Panel.fit(_pretty_json(result), title="Manual Stake Outcome Applied"))
        console.print(
            "[yellow]Option 12 records stake transactions only. bet_id/game_id are null unless a bet is placed via options 19-21.[/yellow]"
        )
    except Exception as err:
        console.print(f"[red]Apply bet outcome failed: {err}[/red]")


def _monitor_stake(stake_service: StakeManagementService) -> None:
    try:
        gambler_id = _prompt_gambler_id()
        result = stake_service.monitor_stake_fluctuations(gambler_id)
        console.print(Panel.fit(_pretty_json(result), title="Stake Monitor"))
    except Exception as err:
        console.print(f"[red]Monitor stake failed: {err}[/red]")


def _validate_stake(stake_service: StakeManagementService) -> None:
    try:
        gambler_id = _prompt_gambler_id()
        result = stake_service.validate_stake_boundaries(gambler_id)
        console.print(Panel.fit(_pretty_json(result), title="Stake Validation"))
    except Exception as err:
        console.print(f"[red]Validate stake failed: {err}[/red]")


def _stake_report(stake_service: StakeManagementService) -> None:
    try:
        gambler_id = _prompt_gambler_id()
        session_id = _prompt_optional_int("Session ID (optional)")
        transaction_type = _prompt_transaction_type(include_all=True)
        result = stake_service.generate_stake_history_report(
            gambler_id,
            session_id=session_id,
            transaction_type=transaction_type,
        )
        console.print(Panel.fit(_pretty_json(result), title="Stake History Report"))
    except Exception as err:
        console.print(f"[red]Generate report failed: {err}[/red]")


def _deposit_funds(stake_service: StakeManagementService) -> None:
    try:
        gambler_id = _prompt_gambler_id()
        amount = _prompt_required_float("Deposit amount")
        result = stake_service.deposit_funds(gambler_id, amount)
        console.print(Panel.fit(_pretty_json(result), title="Deposit Recorded"))
    except Exception as err:
        console.print(f"[red]Deposit failed: {err}[/red]")


def _withdraw_funds(stake_service: StakeManagementService) -> None:
    try:
        gambler_id = _prompt_gambler_id()
        amount = _prompt_required_float("Withdrawal amount")
        result = stake_service.withdraw_funds(gambler_id, amount)
        console.print(Panel.fit(_pretty_json(result), title="Withdrawal Recorded"))
    except Exception as err:
        console.print(f"[red]Withdrawal failed: {err}[/red]")


def _adjust_stake(stake_service: StakeManagementService) -> None:
    try:
        gambler_id = _prompt_gambler_id()
        amount = _prompt_required_float("Adjustment amount (positive adds, negative subtracts)")
        result = stake_service.adjust_stake(gambler_id, amount)
        console.print(Panel.fit(_pretty_json(result), title="Stake Adjusted"))
    except Exception as err:
        console.print(f"[red]Adjust stake failed: {err}[/red]")


def _prompt_strategy_name() -> str:
    return Prompt.ask(
        "Strategy",
        choices=[
            "fixed",
            "percentage",
            "martingale",
            "reverse_martingale",
            "fibonacci",
            "d_alembert",
        ],
        default="fixed",
    )


def _prompt_strategy_config(strategy_name: str) -> dict[str, float]:
    config: dict[str, float] = {}
    key = strategy_name.strip().lower()

    if key == "fixed":
        config["amount"] = _prompt_required_float("Fixed bet amount")
        return config

    if key == "percentage":
        config["percentage"] = _prompt_required_float("Stake percentage (e.g. 5)")
        return config

    if key in {"martingale", "reverse_martingale"}:
        config["base_amount"] = _prompt_required_float("Base bet amount")
        multiplier = _prompt_optional_float("Multiplier (optional, default 2.0)")
        if multiplier is not None:
            config["multiplier"] = multiplier
        return config

    if key == "fibonacci":
        config["base_amount"] = _prompt_required_float("Base bet amount")
        return config

    if key == "d_alembert":
        config["base_amount"] = _prompt_required_float("Base bet amount")
        config["step_amount"] = _prompt_required_float("Step amount")
        return config

    return config


def _place_single_bet(betting_service: BettingService) -> None:
    try:
        gambler_id = _prompt_gambler_id()
        bet_amount = _prompt_required_float("Bet amount")
        result = betting_service.place_bet(gambler_id, bet_amount)
        console.print(Panel.fit(_pretty_json(result), title="Single Bet Result"))
    except Exception as err:
        console.print(f"[red]Place single bet failed: {err}[/red]")


def _place_strategy_bet(betting_service: BettingService) -> None:
    try:
        gambler_id = _prompt_gambler_id()
        strategy_name = _prompt_strategy_name()
        strategy_config = _prompt_strategy_config(strategy_name)
        result = betting_service.place_bet_with_strategy(
            gambler_id=gambler_id,
            strategy_name=strategy_name,
            strategy_config=strategy_config,
        )
        console.print(Panel.fit(_pretty_json(result), title="Strategy Bet Result"))
    except Exception as err:
        console.print(f"[red]Place strategy bet failed: {err}[/red]")


def _place_consecutive_bets(betting_service: BettingService) -> None:
    try:
        gambler_id = _prompt_gambler_id()
        strategy_name = _prompt_strategy_name()
        strategy_config = _prompt_strategy_config(strategy_name)
        number_of_bets = _to_int(_prompt_required_text("Number of bets"), "Number of bets")

        result = betting_service.place_consecutive_bets(
            gambler_id=gambler_id,
            strategy_name=strategy_name,
            number_of_bets=number_of_bets,
            strategy_config=strategy_config,
        )
        console.print(Panel.fit(_pretty_json(result), title="Consecutive Bets Result"))
    except Exception as err:
        console.print(f"[red]Place consecutive bets failed: {err}[/red]")


def _betting_session_summary(betting_service: BettingService) -> None:
    try:
        gambler_id = _prompt_gambler_id()
        result = betting_service.get_betting_session_summary(gambler_id)
        console.print(Panel.fit(_pretty_json(result), title="Betting Session Summary"))
    except Exception as err:
        console.print(f"[red]Get betting session summary failed: {err}[/red]")


def run_cli(
    profile_service: GamblerProfileService,
    stake_service: StakeManagementService,
    betting_service: BettingService,
) -> None:
    actions = {
        "1": ("Create gambler", _create_profile),
        "2": ("List gamblers", _list_profiles),
        "3": ("View gambler details", _view_profile),
        "4": ("Update gambler", _update_profile),
        "5": ("Delete gambler", _delete_profile),
        "6": ("Validate eligibility", _validate_eligibility),
        "7": ("Reset gambler session", _reset_profile),
        "8": ("Record bet result", _record_bet),
        "9": ("Deactivate account", _deactivate_profile),
        "10": ("Initialize stake session", _initialize_stake_session),
        "11": ("Track current stake", _track_stake),
        "12": ("Apply manual stake outcome", _apply_bet_outcome),
        "13": ("Monitor stake fluctuations", _monitor_stake),
        "14": ("Validate stake boundaries", _validate_stake),
        "15": ("Generate stake report", _stake_report),
        "16": ("Deposit funds", _deposit_funds),
        "17": ("Withdraw funds", _withdraw_funds),
        "18": ("Adjust stake", _adjust_stake),
        "19": ("Place single probability bet", _place_single_bet),
        "20": ("Place strategy bet", _place_strategy_bet),
        "21": ("Place consecutive strategy bets", _place_consecutive_bets),
        "22": ("Betting session summary", _betting_session_summary),
        "0": ("Exit", None),
    }

    while True:
        menu = Table(title="Gambler Profile Management CLI")
        menu.add_column("Option", justify="right")
        menu.add_column("Action")
        for key, (label, _) in actions.items():
            menu.add_row(key, label)
        console.print(menu)

        choice = Prompt.ask("Choose an option", choices=list(actions.keys()), default="2")
        if choice == "0":
            console.print("[bold green]Goodbye.[/bold green]")
            break

        _, handler = actions[choice]
        if handler:
            if choice in {"1", "2", "3", "4", "5", "6", "7", "8", "9"}:
                handler(profile_service)
            elif choice in {"10", "11", "12", "13", "14", "15", "16", "17", "18"}:
                handler(stake_service)
            else:
                handler(betting_service)
