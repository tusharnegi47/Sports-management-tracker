"""
agents/analytics_agent/analytics_engine.py
Analytics + Stats Engine — Agent 5

Aggregates player/team stats from player_stats table.
Subscribes to PLAYER_STATS_UPDATED and MATCH_FINISHED events.
"""

from typing import Dict, Any, List, Optional
import pandas as pd

from agents.database_agent.db_service import get_db
from agents.database_agent.models import (
    PlayerStats, Match, Team, User, Tournament,
    LeaderboardCache, BranchStanding
)
from shared.event_bus import get_event_bus, create_event, EventType
from shared.constants.sports import NIT_DELHI_BRANCHES
from shared.logging.logger import get_analytics_logger

logger = get_analytics_logger()
bus    = get_event_bus()

AGENT = "ANALYTICS_AGENT"
_subscriptions_registered = False


# ── Event Subscriptions ───────────────────────────────────────────────────────

def _on_match_finished(event):
    match_id      = event.entity_id
    tournament_id = event.payload.get("tournament_id")
    logger.info(f"[ANALYTICS] Match finished event received: {match_id}")
    if tournament_id:
        refresh_leaderboard(tournament_id)
        refresh_branch_standings(tournament_id)
    compute_mvp_scores(match_id)


def register_subscriptions():
    global _subscriptions_registered
    if _subscriptions_registered:
        return
    bus.subscribe(EventType.MATCH_FINISHED,        _on_match_finished)
    bus.subscribe(EventType.PLAYER_STATS_UPDATED,  lambda e: logger.info(f"Stats updated: {e.entity_id}"))
    _subscriptions_registered = True
    logger.info("Analytics agent subscriptions registered")


# ── Cricket Analytics ─────────────────────────────────────────────────────────

def get_cricket_batting_stats(tournament_id: str) -> pd.DataFrame:
    with get_db() as db:
        rows = (
            db.query(PlayerStats, User.name, User.branch, Team.name.label("team_name"))
            .join(User, PlayerStats.user_id == User.id)
            .join(Team, PlayerStats.team_id == Team.id)
            .filter(PlayerStats.tournament_id == tournament_id)
            .all()
        )
        if not rows:
            return pd.DataFrame()

        data = []
        for ps, player_name, branch, team_name in rows:
            innings_count = max(ps.balls_faced // 10, 1)  # approximate
            sr = round((ps.runs_scored / ps.balls_faced) * 100, 2) if ps.balls_faced else 0
            avg = round(ps.runs_scored / innings_count, 2) if innings_count else ps.runs_scored
            data.append({
                "Player":     player_name,
                "Team":       team_name,
                "Branch":     branch or "N/A",
                "Runs":       ps.runs_scored,
                "Balls":      ps.balls_faced,
                "4s":         ps.fours,
                "6s":         ps.sixes,
                "SR":         sr,
                "Avg":        avg,
            })

    df = pd.DataFrame(data)
    return df.sort_values("Runs", ascending=False).reset_index(drop=True)


def get_cricket_bowling_stats(tournament_id: str) -> pd.DataFrame:
    with get_db() as db:
        rows = (
            db.query(PlayerStats, User.name, User.branch, Team.name.label("team_name"))
            .join(User, PlayerStats.user_id == User.id)
            .join(Team, PlayerStats.team_id == Team.id)
            .filter(PlayerStats.tournament_id == tournament_id, PlayerStats.wickets_taken > 0)
            .all()
        )
        if not rows:
            return pd.DataFrame()

        data = []
        for ps, player_name, branch, team_name in rows:
            eco = round(ps.runs_given / ps.overs_bowled, 2) if ps.overs_bowled else 0
            data.append({
                "Player":   player_name,
                "Team":     team_name,
                "Branch":   branch or "N/A",
                "Overs":    ps.overs_bowled,
                "Wickets":  ps.wickets_taken,
                "Runs":     ps.runs_given,
                "Economy":  eco,
                "Catches":  ps.catches,
            })

    df = pd.DataFrame(data)
    return df.sort_values("Wickets", ascending=False).reset_index(drop=True)


# ── Kabaddi Analytics ─────────────────────────────────────────────────────────

def get_kabaddi_stats(tournament_id: str) -> pd.DataFrame:
    with get_db() as db:
        rows = (
            db.query(PlayerStats, User.name, User.branch, Team.name.label("team_name"))
            .join(User, PlayerStats.user_id == User.id)
            .join(Team, PlayerStats.team_id == Team.id)
            .filter(PlayerStats.tournament_id == tournament_id)
            .all()
        )
        if not rows:
            return pd.DataFrame()

        data = [{
            "Player":       pn,
            "Team":         tn,
            "Branch":       b or "N/A",
            "Raid Pts":     ps.raid_points,
            "Tackle Pts":   ps.tackle_points,
            "Bonus Pts":    ps.bonus_points,
            "Super Raids":  ps.super_raids,
            "Total Pts":    ps.raid_points + ps.tackle_points + ps.bonus_points,
        } for ps, pn, b, tn in rows]

    df = pd.DataFrame(data)
    return df.sort_values("Total Pts", ascending=False).reset_index(drop=True)


# ── Volleyball Analytics ──────────────────────────────────────────────────────

def get_volleyball_stats(tournament_id: str) -> pd.DataFrame:
    with get_db() as db:
        rows = (
            db.query(PlayerStats, User.name, User.branch, Team.name.label("team_name"))
            .join(User, PlayerStats.user_id == User.id)
            .join(Team, PlayerStats.team_id == Team.id)
            .filter(PlayerStats.tournament_id == tournament_id)
            .all()
        )
        if not rows:
            return pd.DataFrame()

        data = [{
            "Player":   pn,
            "Team":     tn,
            "Branch":   b or "N/A",
            "Aces":     ps.aces,
            "Kills":    ps.kills,
            "Blocks":   ps.blocks,
            "Sets Won": ps.sets_won,
            "Total":    ps.aces + ps.kills + ps.blocks,
        } for ps, pn, b, tn in rows]

    df = pd.DataFrame(data)
    return df.sort_values("Total", ascending=False).reset_index(drop=True)


# ── Leaderboard ───────────────────────────────────────────────────────────────

def refresh_leaderboard(tournament_id: str) -> None:
    with get_db() as db:
        matches = (
            db.query(Match)
            .filter(Match.tournament_id == tournament_id, Match.status == "completed")
            .all()
        )
        standings: Dict[str, Dict] = {}

        for m in matches:
            for team_id in [str(m.team_a_id), str(m.team_b_id)]:
                if team_id not in standings:
                    standings[team_id] = {
                        "played": 0, "won": 0, "lost": 0,
                        "drawn": 0, "points": 0,
                    }
                standings[team_id]["played"] += 1

            if m.winner_id:
                wid = str(m.winner_id)
                lid = str(m.team_a_id) if wid == str(m.team_b_id) else str(m.team_b_id)
                if wid in standings:
                    standings[wid]["won"]    += 1
                    standings[wid]["points"] += 2
                if lid in standings:
                    standings[lid]["lost"] += 1

        # Upsert into leaderboard_cache
        for team_id, s in standings.items():
            existing = db.query(LeaderboardCache).filter(
                LeaderboardCache.tournament_id == tournament_id,
                LeaderboardCache.team_id == team_id,
            ).first()
            if existing:
                for k, v in s.items():
                    setattr(existing, k, v)
            else:
                db.add(LeaderboardCache(tournament_id=tournament_id, team_id=team_id, **s))

    bus.publish(create_event(EventType.LEADERBOARD_REFRESHED, AGENT, tournament_id,
                              {"tournament_id": tournament_id}))
    logger.info(f"Leaderboard refreshed for tournament {tournament_id}")


def get_leaderboard(tournament_id: str) -> pd.DataFrame:
    with get_db() as db:
        rows = (
            db.query(LeaderboardCache, Team.name)
            .join(Team, LeaderboardCache.team_id == Team.id)
            .filter(LeaderboardCache.tournament_id == tournament_id)
            .order_by(LeaderboardCache.points.desc())
            .all()
        )
        if not rows:
            return pd.DataFrame()

        data = [{
            "Team":   tn,
            "P":      lc.played,
            "W":      lc.won,
            "L":      lc.lost,
            "D":      lc.drawn,
            "Pts":    lc.points,
            "NRR":    lc.nrr,
        } for lc, tn in rows]

    df = pd.DataFrame(data)
    df.index = range(1, len(df) + 1)
    return df


# ── Branch Standings ──────────────────────────────────────────────────────────

def refresh_branch_standings(tournament_id: str) -> None:
    with get_db() as db:
        matches = (
            db.query(Match)
            .filter(Match.tournament_id == tournament_id, Match.status == "completed")
            .all()
        )
        branch_pts: Dict[str, Dict] = {b: {"gold": 0, "silver": 0, "bronze": 0} for b in NIT_DELHI_BRANCHES}

        for m in matches:
            if m.winner_id:
                winner_team = db.query(Team).filter(Team.id == m.winner_id).first()
                if winner_team and winner_team.branch in branch_pts:
                    branch_pts[winner_team.branch]["gold"] += 1

        for branch, pts in branch_pts.items():
            total = pts["gold"] * 3 + pts["silver"] * 2 + pts["bronze"]
            existing = db.query(BranchStanding).filter(
                BranchStanding.tournament_id == tournament_id,
                BranchStanding.branch == branch,
            ).first()
            if existing:
                existing.gold         = pts["gold"]
                existing.silver       = pts["silver"]
                existing.bronze       = pts["bronze"]
                existing.total_points = total
            else:
                db.add(BranchStanding(
                    tournament_id=tournament_id,
                    branch=branch,
                    **pts,
                    total_points=total,
                ))

    bus.publish(create_event(EventType.BRANCH_STANDINGS_UPDATED, AGENT, tournament_id, {}))
    logger.info(f"Branch standings refreshed for tournament {tournament_id}")


def get_branch_standings(tournament_id: str) -> pd.DataFrame:
    with get_db() as db:
        rows = (
            db.query(BranchStanding)
            .filter(BranchStanding.tournament_id == tournament_id)
            .order_by(BranchStanding.total_points.desc())
            .all()
        )
        if not rows:
            return pd.DataFrame()

        data = [{
            "Branch":     r.branch,
            "🥇 Gold":   r.gold,
            "🥈 Silver": r.silver,
            "🥉 Bronze": r.bronze,
            "Total Pts": r.total_points,
        } for r in rows]

    df = pd.DataFrame(data)
    df.index = range(1, len(df) + 1)
    return df


# ── MVP Score ─────────────────────────────────────────────────────────────────

def compute_mvp_scores(match_id: str) -> None:
    with get_db() as db:
        stats = db.query(PlayerStats).filter(PlayerStats.match_id == match_id).all()
        for s in stats:
            mvp = 0.0
            # Cricket
            mvp += s.runs_scored * 0.5
            mvp += s.wickets_taken * 15
            mvp += s.fours * 0.5
            mvp += s.sixes * 1.0
            mvp += s.catches * 5
            # Kabaddi
            mvp += s.raid_points * 3
            mvp += s.tackle_points * 4
            mvp += s.super_raids * 5
            # Volleyball
            mvp += s.aces * 4
            mvp += s.kills * 3
            mvp += s.blocks * 3
            s.mvp_score = round(mvp, 2)

    logger.info(f"MVP scores computed for match {match_id}")


def get_top_players(tournament_id: str, limit: int = 10) -> pd.DataFrame:
    with get_db() as db:
        all_stats = (
            db.query(PlayerStats, User.name, User.branch, Team.name.label("team_name"))
            .join(User, PlayerStats.user_id == User.id)
            .join(Team, PlayerStats.team_id == Team.id)
            .filter(PlayerStats.tournament_id == tournament_id)
            .all()
        )
        if not all_stats:
            return pd.DataFrame()

        player_scores: Dict[str, Dict] = {}
        for ps, name, branch, team_name in all_stats:
            uid = str(ps.user_id)
            if uid not in player_scores:
                player_scores[uid] = {"Player": name, "Branch": branch or "N/A",
                                       "Team": team_name, "MVP Score": 0.0}
            player_scores[uid]["MVP Score"] += ps.mvp_score

    df = pd.DataFrame(list(player_scores.values()))
    df = df.sort_values("MVP Score", ascending=False).head(limit).reset_index(drop=True)
    df.index = range(1, len(df) + 1)
    return df
