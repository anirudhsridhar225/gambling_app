from __future__ import annotations

import json
from decimal import Decimal
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from models.bettingPreferences import BettingPreferencesCreate, BettingPreferencesUpdate
from models.gambler import GamblerCreate, GamblerPersonalInfoUpdate, GamblerThresholdUpdate
from services.gamblerProfileService import GamblerProfileService

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
				_to_int(_prompt_required_text("Auto-play max games"), "Auto-play max games") if auto_play_enabled else None
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


def run_cli(service: GamblerProfileService) -> None:
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
            handler(service)
