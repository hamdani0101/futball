"""Exports the futball data models used across the project."""

from importlib import import_module

from .competition import Competition
from .match import Match
from .player import Player
from .season import Season
from .stadium import Stadium
from .team import Team

Pass = import_module("core.models.pass").Pass

__all__ = ["Team", "Player", "Match", "Season", "Stadium", "Competition", "Pass"]
