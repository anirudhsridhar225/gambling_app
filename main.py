import db
from cli import run_cli
from services.gamblerProfileService import GamblerProfileService


if __name__ == "__main__":
    db.create_tables(db.cursor, db.cnx)

    service = GamblerProfileService(db.cnx)
    run_cli(service)