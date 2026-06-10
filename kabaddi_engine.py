"""
agents/scoring_agent/kabaddi_engine.py
Kabaddi Scoring Engine — Agent 3
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone

from agents.database_agent.db_service import get_db
from agents.database_agent.models import Match, LiveScore, MatchEvent, PlayerStats
from shared.event_bus import get_event_bus, create_event, EventType
from shared.logging.logger import get_scoring_logger

logger = get_scoring_logger()
bus    = get_event_bus()


class KabaddiEngine:
    """
    Kabaddi scoring logic.
    Points: raids, tackles, bonuses, all-outs, super raids.
    """

    AGENT_NAME   = "SCORING_AGENT"
    POINTS_ALLOUT = 2

    def __init__(self, match_id: str, scorer_user_id: str):
        self.match_id       = match_id
        self.scorer_user_id = scorer_user_id

    def _assert_scorer(self, db):
        match = db.query(Match).filter(Match.id == self.match_id).first()
        if not match:
            raise ValueError("Match not found")
        if match.scorer_id != self.scorer_user_id:
            raise PermissionError("Only the assigned scorer can update this match")
        if match.status not in ("live", "paused"):
            raise ValueError("Match is not live")
        return match

    def _get_live_score(self, db) -> Dict:
        live = db.query(LiveScore).filter(LiveScore.match_id == self.match_id).first()
        if not live:
            return self._init_score(db)
        return live.score_data

    def _init_score(self, db) -> Dict:
        match = db.query(Match).filter(Match.id == self.match_id).first()
        score_data = {
            "match_id":     self.match_id,
            "status":       "live",
            "team_a_id":    str(match.team_a_id),
            "team_b_id":    str(match.team_b_id),
            "team_a_score": 0,
            "team_b_score": 0,
            "team_a_players_out": 0,
            "team_b_players_out": 0,
            "raids":        [],
            "half":         1,
            "updated_at":   datetime.now(timezone.utc).isoformat(),
        }
        db.add(LiveScore(match_id=self.match_id, score_data=score_data))
        db.flush()
        return score_data

    def _save_live_score(self, db, score_data: Dict):
        score_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        live = db.query(LiveScore).filter(LiveScore.match_id == self.match_id).first()
        if live:
            live.score_data = score_data
            live.updated_at = datetime.now(timezone.utc)
        else:
            db.add(LiveScore(match_id=self.match_id, score_data=score_data))

    # ── Raid ──────────────────────────────────────────────────────────────────

    def record_raid(
        self,
        raiding_team_id: str,
        raider_id: str,
        raid_points: int = 0,
        is_bonus: bool = False,
        is_super_raid: bool = False,
        tackled: bool = False,
        tackle_points: int = 0,
        tacklers: Optional[list] = None,
    ) -> Dict[str, Any]:
        """Record a single raid and update scores."""
        with get_db() as db:
            match      = self._assert_scorer(db)
            score_data = self._get_live_score(db)

            is_team_a = str(match.team_a_id) == raiding_team_id
            a_score   = score_data.get("team_a_score", 0)
            b_score   = score_data.get("team_b_score", 0)
            a_out     = score_data.get("team_a_players_out", 0)
            b_out     = score_data.get("team_b_players_out", 0)

            if is_team_a:
                a_score += raid_points + (1 if is_bonus else 0)
                b_out   += raid_points
                if tackled:
                    b_score += tackle_points
                    a_out   += 1
            else:
                b_score += raid_points + (1 if is_bonus else 0)
                a_out   += raid_points
                if tackled:
                    a_score += tackle_points
                    b_out   += 1

            # All-out detection (7 players per side)
            if a_out >= 7:
                b_score += self.POINTS_ALLOUT
                a_out    = 0
                bus.publish(create_event(EventType.ALL_OUT, self.AGENT_NAME, self.match_id,
                                         {"team": "team_a", "bonus_points": self.POINTS_ALLOUT}))
            if b_out >= 7:
                a_score += self.POINTS_ALLOUT
                b_out    = 0
                bus.publish(create_event(EventType.ALL_OUT, self.AGENT_NAME, self.match_id,
                                         {"team": "team_b", "bonus_points": self.POINTS_ALLOUT}))

            score_data.update({
                "team_a_score":        a_score,
                "team_b_score":        b_score,
                "team_a_players_out":  a_out,
                "team_b_players_out":  b_out,
            })
            score_data.setdefault("raids", []).append({
                "raider": raider_id,
                "team":   "team_a" if is_team_a else "team_b",
                "points": raid_points,
                "bonus":  is_bonus,
                "super":  is_super_raid,
                "tackled": tackled,
            })

            self._save_live_score(db, score_data)

            # Player stats
            self._update_raider_stats(db, raider_id, match, raid_points, is_bonus, is_super_raid)
            if tackled and tacklers:
                for t in tacklers:
                    self._update_tackler_stats(db, t, match, tackle_points // max(len(tacklers), 1))

            db.add(MatchEvent(
                match_id=self.match_id,
                event_type="RAID",
                description=f"{'Super raid' if is_super_raid else 'Raid'}: {raid_points} pts" +
                            (" — BONUS!" if is_bonus else "") +
                            (" — TACKLED!" if tackled else ""),
                created_by=self.scorer_user_id,
            ))

        bus.publish(create_event(
            EventType.SCORE_UPDATED,
            self.AGENT_NAME,
            self.match_id,
            {"team_a": score_data["team_a_score"], "team_b": score_data["team_b_score"]},
        ))
        return {"success": True, "score": score_data}

    def finish_match(self, result_summary: str) -> Dict:
        with get_db() as db:
            match = self._assert_scorer(db)
            tournament_id = str(match.tournament_id)
            score_data = self._get_live_score(db)
            a = score_data.get("team_a_score", 0)
            b = score_data.get("team_b_score", 0)
            winner_id = str(match.team_a_id) if a >= b else str(match.team_b_id)
            match.status         = "completed"
            match.winner_id      = winner_id
            match.result_summary = result_summary
            match.finished_at    = datetime.now(timezone.utc)

        bus.publish(create_event(EventType.MATCH_FINISHED, self.AGENT_NAME, self.match_id,
                                  {
                                      "winner_id": winner_id,
                                      "result": result_summary,
                                      "tournament_id": tournament_id,
                                  }))
        return {"success": True, "winner_id": winner_id}

    # ── Player Stats ──────────────────────────────────────────────────────────

    def _update_raider_stats(self, db, raider_id, match, raid_pts, is_bonus, is_super):
        s = self._get_or_create_stats(db, raider_id, match)
        s.raid_points  += raid_pts
        s.bonus_points += 1 if is_bonus else 0
        s.super_raids  += 1 if is_super else 0

    def _update_tackler_stats(self, db, tackler_id, match, pts):
        s = self._get_or_create_stats(db, tackler_id, match)
        s.tackle_points += pts

    def _get_or_create_stats(self, db, user_id, match) -> PlayerStats:
        s = db.query(PlayerStats).filter(
            PlayerStats.user_id == user_id,
            PlayerStats.match_id == self.match_id,
        ).first()
        if not s:
            s = PlayerStats(
                user_id=user_id,
                match_id=self.match_id,
                sport_id=str(match.sport_id),
                tournament_id=str(match.tournament_id),
            )
            db.add(s)
            db.flush()
        return s

    @staticmethod
    def get_scorecard(match_id: str) -> Dict:
        with get_db() as db:
            live = db.query(LiveScore).filter(LiveScore.match_id == match_id).first()
            return live.score_data if live else {}
