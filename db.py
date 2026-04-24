from settings import settings
import mysql.connector

cnx = mysql.connector.connect(
    host = settings.DB_HOST,
    port = settings.DB_PORT,
    user = settings.DB_USERNAME,
    password = settings.DB_PASSWORD,
    database = settings.DB_NAME
)

cursor = cnx.cursor()

def create_tables(cursor, cnx):
    CREATE_GAMBLERS_TABLE = """CREATE TABLE IF NOT EXISTS gambler (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        username VARCHAR(50) NOT NULL,
        full_name VARCHAR(50) NOT NULL,
        email VARCHAR(255) NOT NULL,
        is_active BOOLEAN DEFAULT TRUE,
        initial_stake DECIMAL(10, 2) NOT NULL,
        current_stake DECIMAL(10, 2) NOT NULL,
        win_threshold DECIMAL(10, 2) NOT NULL,
        loss_threshold DECIMAL(10, 2) NOT NULL,
        min_required_stake DECIMAL(10, 2) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    );"""

    CREATE_BETTING_PREFERENCES_TABLE = """CREATE TABLE IF NOT EXISTS betting_preferences (
        preference_id BIGINT PRIMARY KEY AUTO_INCREMENT,
        gambler_id BIGINT NOT NULL,
        min_bet DECIMAL(10, 2) NOT NULL,
        max_bet DECIMAL(10, 2) NOT NULL,
        preferred_game_type VARCHAR(50),
        auto_play_enabled BOOLEAN DEFAULT FALSE,
        auto_play_max_games INT,
        session_loss_limit DECIMAL(10, 2),
        session_win_target DECIMAL(10, 2),
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        FOREIGN KEY (gambler_id) REFERENCES gambler(id)
    );"""

    CREATE_BETTING_STATISTICS_TABLE = """CREATE TABLE IF NOT EXISTS betting_statistics (
        statistic_id BIGINT PRIMARY KEY AUTO_INCREMENT,
        gambler_id BIGINT NOT NULL,
        win_rate DECIMAL(10, 2) NOT NULL,
        average_bet_amount DECIMAL(10, 2) NOT NULL,
        total_bets BIGINT NOT NULL,
        total_wins BIGINT NOT NULL,
        total_losses BIGINT NOT NULL,
        total_winnings BIGINT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        FOREIGN KEY (gambler_id) REFERENCES gambler(id)
    );"""

    CREATE_SESSIONS_TABLE = """CREATE TABLE IF NOT EXISTS sessions (
        session_id BIGINT PRIMARY KEY AUTO_INCREMENT,
        gambler_id BIGINT NOT NULL,
        status ENUM('ACTIVE', 'PAUSED', 'ENDED') NOT NULL,
        starting_stake DECIMAL(10, 2) NOT NULL,
        ending_stake DECIMAL(10, 2),
        peak_stake DECIMAL(10, 2),
        lowest_stake DECIMAL(10, 2),
        lower_limit DECIMAL(10, 2),
        upper_limit DECIMAL(10, 2),
        max_games INT,
        games_played INT DEFAULT 0,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ended_at TIMESTAMP NULL,
        FOREIGN KEY (gambler_id) REFERENCES gambler(id)
    );"""

    CREATE_BETTING_STRATEGIES_TABLE = """CREATE TABLE IF NOT EXISTS betting_strategies (
        strategy_id TINYINT PRIMARY KEY AUTO_INCREMENT,
        strategy_name VARCHAR(255) NOT NULL,
        strategy_code VARCHAR(20),
        strategy_type ENUM('FIXED', 'PERCENTAGE', 'RANDOM') NOT NULL,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );"""

    CREATE_ODDS_CONFIGURATIONS_TABLE = """CREATE TABLE IF NOT EXISTS odds_configurations (
        odds_config_id BIGINT PRIMARY KEY AUTO_INCREMENT,
        odds_type ENUM('FIXED', 'AMERICAN', 'DECIMAL', 'PROBABILITY') NOT NULL,
        fixed_multiplier DECIMAL(10, 2),
        american_odds INT,
        decimal_odds DECIMAL(10, 2),
        probability_payout_factor DECIMAL(10, 2),
        house_edge DECIMAL(5, 4),
        is_default BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    );"""

    CREATE_BETS_TABLE = """CREATE TABLE IF NOT EXISTS bets (
        bet_id BIGINT PRIMARY KEY AUTO_INCREMENT,
        session_id BIGINT NOT NULL,
        gambler_id BIGINT NOT NULL,
        strategy_id TINYINT,
        game_index INT,
        bet_amount DECIMAL(10, 2) NOT NULL,
        win_probability DECIMAL(5, 4),
        odds_type ENUM('FIXED', 'AMERICAN', 'DECIMAL', 'PROBABILITY') NOT NULL,
        odds_value DECIMAL(10, 2) NOT NULL,
        stake_before DECIMAL(10, 2),
        stake_after DECIMAL(10, 2),
        is_settled BOOLEAN DEFAULT FALSE,
        placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id),
        FOREIGN KEY (gambler_id) REFERENCES gambler(id),
        FOREIGN KEY (strategy_id) REFERENCES betting_strategies(strategy_id)
    );"""

    CREATE_GAME_RECORDS_TABLE = """CREATE TABLE IF NOT EXISTS game_records (
        game_id BIGINT PRIMARY KEY AUTO_INCREMENT,
        session_id BIGINT NOT NULL,
        bet_id BIGINT,
        odds_config_id BIGINT,
        outcome ENUM('WIN', 'LOSS', 'PUSH') NOT NULL,
        payout_amount DECIMAL(10, 2),
        loss_amount DECIMAL(10, 2),
        net_change DECIMAL(10, 2),
        stake_before DECIMAL(10, 2),
        stake_after DECIMAL(10, 2),
        consecutive_win_streak INT DEFAULT 0,
        consecutive_loss_streak INT DEFAULT 0,
        game_duration_ms INT,
        resolved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id),
        FOREIGN KEY (bet_id) REFERENCES bets(bet_id),
        FOREIGN KEY (odds_config_id) REFERENCES odds_configurations(odds_config_id)
    );"""

    CREATE_STAKE_TRANSACTIONS_TABLE = """CREATE TABLE IF NOT EXISTS stake_transactions (
        transaction_id BIGINT PRIMARY KEY AUTO_INCREMENT,
        session_id BIGINT,
        gambler_id BIGINT NOT NULL,
        bet_id BIGINT,
        game_id BIGINT,
        transaction_type ENUM('INITIAL_STAKE', 'BET', 'WIN', 'LOSS', 'ADJUSTMENT', 'DEPOSIT', 'WITHDRAWAL', 'RESET') NOT NULL,
        amount DECIMAL(10, 2) NOT NULL,
        balance_before DECIMAL(10, 2),
        balance_after DECIMAL(10, 2),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id),
        FOREIGN KEY (gambler_id) REFERENCES gambler(id),
        FOREIGN KEY (bet_id) REFERENCES bets(bet_id),
        FOREIGN KEY (game_id) REFERENCES game_records(game_id)
    );"""

    cursor.execute(CREATE_GAMBLERS_TABLE)
    cursor.execute(CREATE_BETTING_PREFERENCES_TABLE)
    cursor.execute(CREATE_SESSIONS_TABLE)
    cursor.execute(CREATE_BETTING_STRATEGIES_TABLE)
    cursor.execute(CREATE_BETTING_STATISTICS_TABLE)
    cursor.execute(CREATE_ODDS_CONFIGURATIONS_TABLE)
    cursor.execute(CREATE_BETS_TABLE)
    cursor.execute(CREATE_GAME_RECORDS_TABLE)
    cursor.execute(CREATE_STAKE_TRANSACTIONS_TABLE)

    required_columns = {
        "gambler": {
            "username": "VARCHAR(50) NOT NULL DEFAULT ''",
            "full_name": "VARCHAR(50) NOT NULL DEFAULT ''",
            "email": "VARCHAR(255) NOT NULL DEFAULT ''",
            "is_active": "BOOLEAN DEFAULT TRUE",
            "initial_stake": "DECIMAL(10, 2) NOT NULL DEFAULT 0",
            "current_stake": "DECIMAL(10, 2) NOT NULL DEFAULT 0",
            "win_threshold": "DECIMAL(10, 2) NOT NULL DEFAULT 0",
            "loss_threshold": "DECIMAL(10, 2) NOT NULL DEFAULT 0",
            "min_required_stake": "DECIMAL(10, 2) NOT NULL DEFAULT 0",
        },
        "betting_preferences": {
            "min_bet": "DECIMAL(10, 2) NOT NULL DEFAULT 0",
            "max_bet": "DECIMAL(10, 2) NOT NULL DEFAULT 0",
            "preferred_game_type": "VARCHAR(50) NULL",
            "auto_play_enabled": "BOOLEAN DEFAULT FALSE",
            "auto_play_max_games": "INT NULL",
            "session_loss_limit": "DECIMAL(10, 2) NULL",
            "session_win_target": "DECIMAL(10, 2) NULL",
        },
        "betting_statistics": {
            "win_rate": "DECIMAL(10, 2) NOT NULL DEFAULT 0",
            "average_bet_amount": "DECIMAL(10, 2) NOT NULL DEFAULT 0",
            "total_bets": "BIGINT NOT NULL DEFAULT 0",
            "total_wins": "BIGINT NOT NULL DEFAULT 0",
            "total_losses": "BIGINT NOT NULL DEFAULT 0",
            "total_winnings": "BIGINT NOT NULL DEFAULT 0",
        },
        "betting_strategies": {
            "strategy_code": "VARCHAR(20) NULL",
        },
    }

    for table_name, columns in required_columns.items():
        for column_name, column_definition in columns.items():
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
            column_exists = cursor.fetchone()[0] > 0
            if not column_exists:
                cursor.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
                )

    # Ensure legacy databases have all expected transaction_type enum values.
    cursor.execute(
        """
        SELECT COLUMN_TYPE
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'stake_transactions'
          AND COLUMN_NAME = 'transaction_type'
        """
    )
    enum_row = cursor.fetchone()
    expected_enum_values = {
        "INITIAL_STAKE",
        "BET",
        "WIN",
        "LOSS",
        "ADJUSTMENT",
        "DEPOSIT",
        "WITHDRAWAL",
        "RESET",
    }

    current_enum_values = set()
    if enum_row and enum_row[0]:
        column_type = str(enum_row[0])
        if column_type.startswith("enum(") and column_type.endswith(")"):
            inner = column_type[len("enum(") : -1]
            current_enum_values = {
                value.strip().strip("'")
                for value in inner.split(",")
                if value.strip()
            }

    if not expected_enum_values.issubset(current_enum_values):
        cursor.execute(
            """
            ALTER TABLE stake_transactions
            MODIFY COLUMN transaction_type ENUM(
                'INITIAL_STAKE',
                'BET',
                'WIN',
                'LOSS',
                'ADJUSTMENT',
                'DEPOSIT',
                'WITHDRAWAL',
                'RESET'
            ) NOT NULL
            """
        )

    # Ensure betting_strategies table has all expected strategy_type enum values.
    cursor.execute(
        """
        SELECT COLUMN_TYPE
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'betting_strategies'
          AND COLUMN_NAME = 'strategy_type'
        """
    )
    strategy_type_row = cursor.fetchone()
    expected_strategy_types = {"FIXED", "PERCENTAGE", "RANDOM"}

    current_strategy_types = set()
    if strategy_type_row and strategy_type_row[0]:
        column_type = str(strategy_type_row[0])
        if column_type.startswith("enum(") and column_type.endswith(")"):
            inner = column_type[len("enum(") : -1]
            current_strategy_types = {
                value.strip().strip("'")
                for value in inner.split(",")
                if value.strip()
            }

    if not expected_strategy_types.issubset(current_strategy_types):
        cursor.execute(
            """
            ALTER TABLE betting_strategies
            MODIFY COLUMN strategy_type ENUM(
                'FIXED',
                'PERCENTAGE',
                'RANDOM'
            ) NOT NULL
            """
        )

    cnx.commit()
    print("All tables created successfully!")