"""
agents/scoring_agent/cricket_engine.py
Cricket Scoring Engine — Agent 3

Handles ball-by-ball cricket logic:
- Runs, wickets, overs, extras
- Strike rotation, innings transitions
- Match result calculations
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from agents.database_agent.db_service import get_db
from agents.database_agent.models import Match, Innings, Delivery, LiveScore, MatchEvent, PlayerStats
from agents.database_agent.permissions import is_scorer
from shared.event_bus import get_event_bus, create_event, EventType
from shared.constants.sports import CRICKET_DISMISSALS, CRICKET_EXTRAS
from shared.logging.logger import get_scoring_logger

logger = get_scoring_logger()
bus    = get_event_bus()


class CricketEngine:
    """
    Core cricket scoring logic.
    Each method is atomic — wraps a single DB transaction.
    """

    AGENT_NAME = "SCORING_AGENT"

    def __init__(self, match_id: str, scorer_user_id: str):
        self.match_id       = match_id
        self.scorer_user_id = scorer_user_id

    # ── Validation ────────────────────────────────────────────────────────────

    def _assert_scorer(self, db):
        from agents.database_agent.models import Match
        match = db.query(Match).filter(Match.id == self.match_id).first()
        if not match:
            raise ValueError(f"Match {self.match_id} not found")
        if match.scorer_id != self.scorer_user_id:
            raise PermissionError("Only the assigned scorer can update this match")
        if match.status not in ("live", "paused"):
            raise ValueError(f"Match is not live (status={match.status})")
        return match

    # ── Innings Management ────────────────────────────────────────────────────

    def start_innings(self, batting_team_id: str, bowling_team_id: str, innings_num: int, target: Optional[int] = None) -> Dict:
        with get_db() as db:
            match = self._assert_scorer(db)
            innings = Innings(
                match_id=self.match_id,
                batting_team_id=batting_team_id,
                bowling_team_id=bowling_team_id,
                innings_number=innings_num,
                target=target,
                extras={"wide": 0, "no_ball": 0, "bye": 0, "leg_bye": 0},
            )
            db.add(innings)
            db.flush()
            self._upsert_live_score(db, match)
            logger.info(f"Innings {innings_num} started for match {self.match_id}")
            return {"success": True, "innings_id": innings.id}

    # ── Ball Recording ────────────────────────────────────────────────────────

    def record_delivery(
        self,
        innings_id: str,
        over_number: int,
        ball_number: int,
        runs_scored: int = 0,
        extra_type: Optional[str] = None,
        extra_runs: int = 0,
        is_wicket: bool = False,
        dismissal_type: Optional[str] = None,
        batter_id: Optional[str] = None,
        bowler_id: Optional[str] = None,
        fielder_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record a single delivery. Validates and publishes events."""

        # Validate
        if extra_type and extra_type not in CRICKET_EXTRAS:
            raise ValueError(f"Invalid extra type: {extra_type}")
        if dismissal_type and dismissal_type not in CRICKET_DISMISSALS:
            raise ValueError(f"Invalid dismissal type: {dismissal_type}")

        is_valid_ball = extra_type not in ("wide", "no_ball") if extra_type else True

        with get_db() as db:
            match   = self._assert_scorer(db)
            innings = db.query(Innings).filter(Innings.id == innings_id).first()
            if not innings or innings.is_complete:
                raise ValueError("Innings not found or already complete")

            # Record delivery
            delivery = Delivery(
                innings_id=innings_id,
                over_number=over_number,
                ball_number=ball_number,
                batter_id=batter_id,
                bowler_id=bowler_id,
                runs_scored=runs_scored,
                extra_type=extra_type,
                extra_runs=extra_runs,
                is_wicket=is_wicket,
                dismissal_type=dismissal_type,
                fielder_id=fielder_id,
                is_valid_ball=is_valid_ball,
            )
            db.add(delivery)
            db.flush()

            # Update innings totals
            innings.runs += runs_scored + extra_runs
            if is_wicket:
                innings.wickets += 1
            if is_valid_ball:
                innings.overs_played = self._calculate_overs_played(db, innings_id)
            if extra_type:
                extras = dict(innings.extras or {})
                extras[extra_type] = extras.get(extra_type, 0) + extra_runs
                innings.extras = extras

            # Update player stats
            if batter_id:
                self._update_batter_stats(db, batter_id, innings, runs_scored, is_valid_ball, is_wicket)
            if bowler_id:
                self._update_bowler_stats(db, bowler_id, innings, runs_scored, extra_runs, is_wicket, is_valid_ball)

            # Update live score cache
            self._upsert_live_score(db, match)
            db.flush()

            # Build event description
            description = self._describe_ball(runs_scored, extra_type, extra_runs, is_wicket, dismissal_type)
            db.add(MatchEvent(
                match_id=self.match_id,
                event_type="DELIVERY",
                description=description,
                payload={
                    "over": over_number,
                    "ball": ball_number,
                    "runs": runs_scored,
                    "extra_type": extra_type,
                    "extra_runs": extra_runs,
                    "is_wicket": is_wicket,
                    "dismissal": dismissal_type,
                },
                created_by=self.scorer_user_id,
            ))

        # Publish events
        bus.publish(create_event(
            EventType.SCORE_UPDATED,
            source_agent=self.AGENT_NAME,
            entity_id=self.match_id,
            payload={"innings_id": innings_id, "description": description},
        ))

        if is_wicket:
            bus.publish(create_event(
                EventType.WICKET_FALLEN,
                source_agent=self.AGENT_NAME,
                entity_id=self.match_id,
                payload={"innings_id": innings_id, "dismissal": dismissal_type, "batter_id": batter_id},
            ))

        logger.info(f"Delivery recorded: {description} (match={self.match_id})")
        return {"success": True, "description": description}

    def complete_over(self, innings_id: str, over_number: int) -> Dict:
        with get_db() as db:
            self._assert_scorer(db)
            bus.publish(create_event(
                EventType.OVER_COMPLETED,
                source_agent=self.AGENT_NAME,
                entity_id=self.match_id,
                payload={"innings_id": innings_id, "over": over_number},
            ))
        return {"success": True, "message": f"Over {over_number} completed"}

    def complete_innings(self, innings_id: str) -> Dict:
        with get_db() as db:
            match   = self._assert_scorer(db)
            innings = db.query(Innings).filter(Innings.id == innings_id).first()
            if innings:
                innings.is_complete = True

        bus.publish(create_event(
            EventType.INNINGS_COMPLETED,
            source_agent=self.AGENT_NAME,
            entity_id=self.match_id,
            payload={"innings_id": innings_id},
        ))
        return {"success": True, "message": "Innings completed"}

    # ── Match Completion ──────────────────────────────────────────────────────

    def finish_match(self, winner_id: str, result_summary: str) -> Dict:
        with get_db() as db:
            match = self._assert_scorer(db)
            tournament_id = str(match.tournament_id)
            match.status         = "completed"
            match.winner_id      = winner_id
            match.result_summary = result_summary
            match.finished_at    = datetime.now(timezone.utc)
            self._upsert_live_score(db, match)

        bus.publish(create_event(
            EventType.MATCH_FINISHED,
            source_agent=self.AGENT_NAME,
            entity_id=self.match_id,
            payload={
                "winner_id": winner_id,
                "result": result_summary,
                "tournament_id": tournament_id,
            },
        ))
        logger.info(f"Match {self.match_id} finished. Winner: {winner_id}")
        return {"success": True, "result": result_summary}

    # ── Undo Last Ball ────────────────────────────────────────────────────────

    def undo_last_delivery(self, innings_id: str) -> Dict:
        """Remove the last delivery and revert innings totals."""
        with get_db() as db:
            self._assert_scorer(db)
            innings = db.query(Innings).filter(Innings.id == innings_id).first()
            if not innings:
                return {"success": False, "error": "Innings not found"}

            last = (
                db.query(Delivery)
                .filter(Delivery.innings_id == innings_id)
                .order_by(Delivery.created_at.desc())
                .first()
            )
            if not last:
                return {"success": False, "error": "No deliveries to undo"}

            # Revert
            innings.runs    -= (last.runs_scored + last.extra_runs)
            if last.is_wicket:
                innings.wickets = max(0, innings.wickets - 1)
            if last.extra_type:
                extras = dict(innings.extras or {})
                extras[last.extra_type] = max(0, extras.get(last.extra_type, 0) - last.extra_runs)
                innings.extras = extras

            db.delete(last)
            db.flush()
            innings.overs_played = self._calculate_overs_played(db, innings_id)
            logger.info(f"Last delivery undone for innings {innings_id}")
            return {"success": True, "message": "Last delivery undone"}

    # ── Live Score Cache ──────────────────────────────────────────────────────

    def _upsert_live_score(self, db, match):
        innings_list = (
            db.query(Innings)
            .filter(Innings.match_id == self.match_id)
            .order_by(Innings.innings_number)
            .all()
        )
        score_data = {
            "match_id": self.match_id,
            "status":   match.status,
            "innings": [
                {
                    "number":      i.innings_number,
                    "batting_team": str(i.batting_team_id),
                    "runs":        i.runs,
                    "wickets":     i.wickets,
                    "overs":       i.overs_played,
                    "extras":      i.extras or {},
                    "target":      i.target,
                    "is_complete": i.is_complete,
                }
                for i in innings_list
            ],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        existing = db.query(LiveScore).filter(LiveScore.match_id == self.match_id).first()
        if existing:
            existing.score_data = score_data
            existing.updated_at = datetime.now(timezone.utc)
        else:
            db.add(LiveScore(match_id=self.match_id, score_data=score_data))

    # ── Player Stat Helpers ───────────────────────────────────────────────────

    def _update_batter_stats(self, db, batter_id, innings, runs, is_valid, is_wicket):
        match = db.query(Match).filter(Match.id == self.match_id).first()
        stats = self._get_or_create_stats(db, batter_id, innings, match, innings.batting_team_id)
        stats.runs_scored += runs
        if is_valid:
            stats.balls_faced += 1
        if runs == 4:
            stats.fours += 1
        elif runs == 6:
            stats.sixes += 1
        if is_wicket:
            stats.is_not_out = False

    def _update_bowler_stats(self, db, bowler_id, innings, runs, extra_runs, is_wicket, is_valid):
        match = db.query(Match).filter(Match.id == self.match_id).first()
        stats = self._get_or_create_stats(db, bowler_id, innings, match, innings.bowling_team_id)
        stats.runs_given += runs + extra_runs
        if is_wicket:
            stats.wickets_taken += 1
        if is_valid:
            stats.overs_bowled = round(stats.overs_bowled + (1/6), 2)

    def _get_or_create_stats(self, db, user_id, innings, match, team_id) -> PlayerStats:
        stats = (
            db.query(PlayerStats)
            .filter(PlayerStats.user_id == user_id, PlayerStats.match_id == self.match_id)
            .first()
        )
        if not stats:
            stats = PlayerStats(
                user_id=user_id,
                match_id=self.match_id,
                team_id=str(team_id),
                sport_id=str(match.sport_id),
                tournament_id=str(match.tournament_id),
            )
            db.add(stats)
            db.flush()
        return stats

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _describe_ball(runs, extra_type, extra_runs, is_wicket, dismissal):
        if is_wicket:
            return f"WICKET! {dismissal or 'out'}"
        if extra_type == "wide":
            return f"Wide +{extra_runs}"
        if extra_type == "no_ball":
            return f"No ball +{extra_runs}" + (f", {runs} runs" if runs else "")
        if runs == 0:
            return "Dot ball"
        if runs == 4:
            return "FOUR!"
        if runs == 6:
            return "SIX!"
        return f"{runs} run{'s' if runs > 1 else ''}"

    @staticmethod
    def _balls_to_overs(valid_balls: int) -> float:
        overs = valid_balls // 6
        balls = valid_balls % 6
        return float(f"{overs}.{balls}")

    def _calculate_overs_played(self, db, innings_id: str) -> float:
        valid_balls = (
            db.query(Delivery)
            .filter(Delivery.innings_id == innings_id, Delivery.is_valid_ball == True)
            .count()
        )
        return self._balls_to_overs(valid_balls)

    # ── Public Scorecard ──────────────────────────────────────────────────────

    @staticmethod
    def get_scorecard(match_id: str) -> Dict[str, Any]:
        with get_db() as db:
            live = db.query(LiveScore).filter(LiveScore.match_id == match_id).first()
            if not live:
                return {}
            return live.score_data
