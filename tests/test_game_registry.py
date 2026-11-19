"""Sync guard: a game is listed in many places (services.GAMES, running, guests, netfilter, the API's game_of, the coins
of live games …). Until there is one registry, this test says where a new game is still missing."""
from familyquest import guests, netfilter, running
from familyquest.api import community
from familyquest.api.parent import REWARD_GAMES
from familyquest.db import DEFAULT_SETTINGS
from familyquest.gamepasses import ARCADE
from familyquest.services import FamilyQuest

ALL = FamilyQuest.__dict__["GAMES"].games            # every game, the dev games included (channel.py)
BOTS = FamilyQuest.__dict__["BOT_GAMES"].games
TABLE = [g for g in ALL if g not in ARCADE and g not in FamilyQuest.FREE_GAMES]   # games at a table (not the game corner)
CARDS = ("tschau", "karussell")                      # the card games share /api/community/cards/<kind>
OWN = ("quiz", "bingo", "song", "poker")             # their own tables (not card_game)


def path(g: str) -> str:
    return f"/api/community/cards/{g}/state" if g in CARDS else f"/api/community/{g}/state"


def test_every_table_game_is_everywhere():
    missing = {}
    for g in TABLE:
        where = []
        if community.game_of(path(g)) != g:
            where.append("api/community.game_of")
        if g not in guests.GAMES:
            where.append("guests.GAMES")
        if not path(g).startswith(netfilter.GUEST_API):
            where.append("netfilter.GUEST_API")
        if g not in running.ICONS:
            where.append("running.ICONS")
        if g not in OWN and g not in running.TITLES:
            where.append("running.TITLES")
        if where:
            missing[g] = where
    assert not missing, missing


def test_card_game_kinds_and_coins_lists_agree(fq):
    assert set(running.TITLES) == set(running._games(fq)), "running.TITLES and running._games must list the same games"
    assert set(running.TITLES) <= set(ALL)
    assert set(BOTS) <= set(ALL)
    assert set(REWARD_GAMES) <= set(TABLE)
    assert set(DEFAULT_SETTINGS["game_rewards"]) == set(REWARD_GAMES)
    for g in REWARD_GAMES:                             # a live game with coins pays them from its module (CardGames._payout)
        assert g in running.TITLES, g
