from dataclasses import dataclass

from models.gambler import GamblerDisplay
from models.gamblingStatistics import GamblerStatisticsDTO


@dataclass
class GamblingProfile:
    gambler: GamblerDisplay
    preferences: dict
    statistics: GamblerStatisticsDTO