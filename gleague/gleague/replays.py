import dataclasses as dc
import requests

from gleague.core import db
from gleague.models import Match
from gleague.models import Season
from gleague.models import CMPicksBans
from gleague.models import PlayerMatchStats
from gleague.models import Player
from gleague.models import SeasonStats
from gleague.models import Role
from gleague.models import PlayerMatchItem
from gleague.utils.position import detect_position


@dc.dataclass
class ReplayDataProcessor:
    base_pts_diff: int

    def save_replay_data(self, replay_data: dict) -> Match:
        match_id = replay_data["match_id"]
        match = Match.query.get(match_id)
        if match is None:
            match = Match(
                season=Season.current(),
                id=replay_data["match_id"],
            )
        db.session.add(match)
        return self.update_match(match, replay_data)

    def update_match(self, match: Match, replay_data: dict) -> Match:
        self._save_match_attributes(match, replay_data)
        self._save_match_game_mode_attributes(match, replay_data)
        self._save_match_players(match, replay_data)
        db.session.flush()
        return match

    def _save_match_attributes(self, match: Match, replay_data: dict):
        match.radiant_win = bool(replay_data["radiant_win"])
        for key in ("duration", "game_mode", "start_time"):
            setattr(match, key, replay_data[key])

    def _save_match_game_mode_attributes(self, match: Match, replay_data: dict):
        if match.game_mode == 2:
            match.cm_captains = replay_data["draft"]["captains"]
            pick_bans_from_data = {
                (
                    pick_ban_data["is_pick"],
                    pick_ban_data["is_radiant"],
                    pick_ban_data["hero"],
                )
                for pick_ban_data in replay_data["draft"]["picks_and_bans"]
            }
            match_pick_bans_map = {
                (
                    cmpb.is_pick,
                    cmpb.is_radiant,
                    cmpb.hero,
                ): cmpb
                for cmpb in match.cm_picks_bans
            }
            for data, cmpb in match_pick_bans_map.items():
                if data not in pick_bans_from_data:
                    db.session.delete(cmpb)
            for data in pick_bans_from_data:
                if data not in match_pick_bans_map:
                    db.session.add(
                        CMPicksBans(
                            **dict(zip(("is_pick", "is_radiant", "hero"), data)),
                            match=match,
                        )
                    )

    def _save_match_players(self, match: Match, replay_data: dict):
        player_stats_created = False
        match_stats_map = {
            str(ms.season_stats.steam_id): ms for ms in match.players_stats
        }
        for player_data in replay_data["players"]:
            account_id = "765" + str(player_data["account_id"] + 61197960265728)
            try:
                player_stats = match_stats_map[account_id]
            except KeyError:
                player_stats_created = True
                player = Player.get_or_create(account_id)
                if player is None:
                    db.session.rollback()
                    return None
                db.session.flush()
                season_stats = SeasonStats.get_or_create(account_id, match.season_id)
                db.session.add(season_stats)
                player_stats = PlayerMatchStats(
                    match=match,
                    season_stats=season_stats,
                    pts_diff=20,
                    old_pts=season_stats.pts,
                )
            db.session.add(player_stats)
            for key in (
                "kills",
                "assists",
                "level",
                "deaths",
                "hero_damage",
                "last_hits",
                "player_slot",
                "denies",
                "tower_damage",
                "damage_taken",
                "xp_per_min",
                "gold_per_min",
                "movement",
                "early_denies",
                "early_last_hits",
                "observer_wards_placed",
                "sentry_wards_placed",
            ):
                setattr(player_stats, key, player_data[key])
            player_stats.hero = player_data["hero_name"].replace("npc_dota_hero_", "")
            player_stats.position = detect_position(
                list([[pos["x"], pos["y"]] for pos in player_stats.movement])
            )
            match_player_items_map = {
                mpi.name: mpi for mpi in player_stats.player_match_items
            }
            items_from_data = {item for item in player_data["items"] if item}
            for item, mpi in match_player_items_map.items():
                if item not in items_from_data:
                    db.session.delete(mpi)
            for item in items_from_data:
                if item not in match_player_items_map:
                    db.session.add(
                        PlayerMatchItem(name=item, player_match_stats=player_stats)
                    )

        if player_stats_created:
            self._set_match_players_pts(match)
            self._set_match_players_roles(match)
            self._set_match_players_streaks(match)

    def _set_match_players_pts(self, match):
        pts = dict(radiant=0, dire=0)
        pts_deviation = int(abs(pts["radiant"] - pts["dire"]) / 20)
        if pts_deviation > self.base_pts_diff - 5:
            pts_deviation = self.base_pts_diff - 5
        pts_diff = self.base_pts_diff
        if (pts["dire"] > pts["radiant"]) == match.radiant_win:
            pts_diff += pts_deviation
        else:
            pts_diff -= pts_deviation
        for stats in match.players_stats:
            if stats.is_winner():
                stats.pts_diff = pts_diff
            else:
                stats.pts_diff = -pts_diff
            stats.season_stats.pts += stats.pts_diff

    def _set_match_players_roles(self, match):
        sort_by_lh = lambda s: s.early_last_hits  # noqa
        radiant_players = sorted(
            filter(lambda s: s.player_slot < 5, match.players_stats), key=sort_by_lh
        )
        dire_players = sorted(
            filter(lambda s: s.player_slot > 5, match.players_stats), key=sort_by_lh
        )
        supports_number = 2
        supports = radiant_players[:supports_number] + dire_players[:supports_number]
        cores = radiant_players[supports_number:] + dire_players[supports_number:]
        for sup in supports:
            sup.role = Role.support
        for core in cores:
            core.role = Role.core

    def _set_match_players_streaks(self, match):
        for stats in match.players_stats:
            season_stats = stats.season_stats
            if stats.pts_diff > 0:
                season_stats.wins += 1
                if season_stats.streak > 0:
                    season_stats.streak += 1
                else:
                    season_stats.streak = 1
                if season_stats.streak > season_stats.longest_winstreak:
                    season_stats.longest_winstreak = season_stats.streak
            else:
                if season_stats.streak > 0:
                    season_stats.streak = -1
                else:
                    season_stats.streak -= 1
                season_stats.losses += 1
                if season_stats.streak < -(season_stats.longest_losestreak):
                    season_stats.longest_losestreak = -(season_stats.streak)


class ReplayParserException(Exception):
    pass


@dc.dataclass
class ReplayParserService:
    url: str

    def parse_replay(self, replay_io) -> dict:
        resp = requests.post(
            url=self.url,
            data=replay_io.read(),
            headers={"Content-Type": "application/octet-stream"},
        )

        if resp.status_code == 200:
            match_data = resp.json()["result"]
            return match_data

        if resp.status_code == 400:
            error = resp.json()["error"]
            raise ReplayParserException(error)

        raise ReplayParserException("Internal Server Error")