"""
agents/scoring_agent/volleyball_engine.py
Volleyball Scoring Engine — Agent 3
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone

from agents.database_agent.db_service import get_db
from agents.database_agent.models import Match, LiveScore, MatchEvent, PlayerStats
from shared.event_bus import get_event_bus, create_event, EventType
from shared.constants.sports import VOLLEYBALL_SETS_TO_WIN, VOLLEYBALL_POINTS_PER_SET, VOLLEYBALL_FINAL_SET_POINTS
from shared.logging.logger import get_scoring_logger

logger = get_scoring_logger()
bus    = get_event_bus()


class VolleyballEngine:
    """
    Volleyball scoring: best of 5 sets.
    First to 25 pts (15 in final set) with 2+ lead wins a set.
    First to 3 sets wins the match.
    """

    AGENT_NAME = "SCORING_AGENT"

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
            "match_id":       self.match_id,
            "status":         "live",
            "team_a_id":      str(match.team_a_id),
            "team_b_id":      str(match.team_b_id),
            "current_set":    1,
            "team_a_sets":    0,
            "team_b_sets":    0,
            "sets":           [{
                "set_number": 1,
                "team_a_pts": 0,
                "team_b_pts": 0,
                "winner":     None,
            }],
            "updated_at": datetime.now(timezone.utc).isoformat(),
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

    # ── Point ─────────────────────────────────────────────────────────────────

    def add_point(
        self,
        scoring_team_id: str,
        point_type: str = "rally",
        scorer_player_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a point to the current set for the given team."""
        with get_db() as db:
            match      = self._assert_scorer(db)
            score_data = self._get_live_score(db)

            is_team_a    = str(match.team_a_id) == scoring_team_id
            current_set  = score_data.get("current_set", 1)
            sets         = score_data.get("sets", [])
            set_obj      = next((s for s in sets if s["set_number"] == current_set), None)

            if not set_obj:
                return {"success": False, "error": "Set not found"}

            if is_team_a:
                set_obj["team_a_pts"] += 1
            else:
                set_obj["team_b_pts"] += 1

            # Check set winner
            set_complete, set_winner = self._check_set_winner(
                set_obj["team_a_pts"],
                set_obj["team_b_pts"],
                current_set,
                str(match.team_a_id),
                str(match.team_b_id),
            )

            match_over = False
            if set_complete:
                set_obj["winner"] = set_winner
                if set_winner == str(match.team_a_id):
                    score_data["team_a_sets"] += 1
                else:
                    score_data["team_b_sets"] += 1

                bus.publish(create_event(EventType.SET_COMPLETED, self.AGENT_NAME, self.match_id,
                                          {"set": current_set, "winner": set_winner}))
                logger.info(f"Set {current_set} complete. Winner: {set_winner}")

                # Start next set or end match
                a_sets = score_data["team_a_sets"]
                b_sets = score_data["team_b_sets"]
                if a_sets == VOLLEYBALL_SETS_TO_WIN or b_sets == VOLLEYBALL_SETS_TO_WIN:
                    match_over   = True
                    winner_id    = str(match.team_a_id) if a_sets > b_sets else str(match.team_b_id)
                    result       = f"Match won {a_sets}-{b_sets} sets"
                    match.status         = "completed"
                    match.winner_id      = winner_id
                    match.result_summary = result
                    match.finished_at    = datetime.now(timezone.utc)
                    bus.publish(create_event(EventType.MATCH_FINISHED, self.AGENT_NAME, self.match_id,
                                              {
                                                  "winner_id": winner_id,
                                                  "result": result,
                                                  "tournament_id": str(match.tournament_id),
                                              }))
                else:
                    next_set = current_set + 1
                    score_data["current_set"] = next_set
                    sets.append({"set_number": next_set, "team_a_pts": 0, "team_b_pts": 0, "winner": None})

            score_data["sets"] = sets
            self._save_live_score(db, score_data)

            # Player stats
            if scorer_player_id:
                self._update_player_stats(db, scorer_player_id, match, point_type)

            db.add(MatchEvent(
                match_id=self.match_id,
                event_type="POINT",
                description=f"Set {current_set}: {'Team A' if is_team_a else 'Team B'} scores ({point_type}) "
                            f"— {set_obj['team_a_pts']}-{set_obj['team_b_pts']}",
                created_by=self.scorer_user_id,
            ))

        bus.publish(create_event(EventType.SCORE_UPDATED, self.AGENT_NAME, self.match_id,
                                  {"current_set": current_set, "score": set_obj}))
        return {"success": True, "score_data": score_data, "set_complete": set_complete}

    def _check_set_winner(self, a_pts, b_pts, set_num, team_a_id, team_b_id):
        limit = VOLLEYBALL_FINAL_SET_POINTS if set_num == 5 else VOLLEYBALL_POINTS_PER_SET
        if a_pts >= limit and a_pts - b_pts >= 2:
            return True, team_a_id
        if b_pts >= limit and b_pts - a_pts >= 2:
            return True, team_b_id
        return False, None

    def _update_player_stats(self, db, player_id, match, point_type):
        s = db.query(PlayerStats).filter(
            PlayerStats.user_id == player_id,
            PlayerStats.match_id == self.match_id
        ).first()
        if not s:
            s = PlayerStats(user_id=player_id, match_id=self.match_id,
                            sport_id=str(match.sport_id), tournament_id=str(match.tournament_id))
            db.add(s)
            db.flush()
        if point_type == "ace":
            s.aces  += 1
        elif point_type == "kill":
            s.kills += 1
        elif point_type == "block":
            s.blocks += 1

    @staticmethod
    def get_scorecard(match_id: str) -> Dict:
        with get_db() as db:
            live = db.query(LiveScore).filter(LiveScore.match_id == match_id).first()
            return live.score_data if live else {}
