import db
from cli import run_cli
from services.bettingService import BettingService
from services.gamblerProfileService import GamblerProfileService
from services.stakeManagementService import StakeManagementService


if __name__ == "__main__":
    db.create_tables(db.cursor, db.cnx)

    profile_service = GamblerProfileService(db.cnx)
    stake_service = StakeManagementService(db.cnx)
    betting_service = BettingService(db.cnx, stake_service)
    run_cli(profile_service, stake_service, betting_service)