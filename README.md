# Sports Score Tracker & Management System

A data-driven management dashboard designed for university sports coaches and athletic departments to monitor player performance, manage team rosters, and track historical tournament statistics.

---

## Core Features

* **Performance Analytics** Tracks specific player performance metrics over consecutive match cycles, helping coaches make data-backed selection decisions.

* **Roster & Squad Management** Streamlines student-athlete registration, team assignments, and tournament lineups in a single relational schema.

* **Historical Data Querying** Built-in optimized queries to pull historical tournament data, medal tallies, and past player statistics.

## Tech Stack

* **Language:** Python
* **Database:** PostgreSQL
* **Core Logic:** Relational data schemas, complex indexing, and structured analytical queries

## Database Architecture

The system's core relies on a highly structured relational database. Below is the mapping that drives the backend tracking logic:

| Table | Key Responsibility | Core Attributes |
| :--- | :--- | :--- |
| **Players** | Stores unique student-athlete records | `PlayerID`, `Name`, `Branch`, `Year`, `PrimarySport` |
| **Teams** | Manages distinct sports rosters and squads | `TeamID`, `SportName`, `CurrentRosterSize` |
| **MatchPerformance** | Tracks individual player statistics per game | `PerformanceID`, `PlayerID`, `MatchID`, `StatsJSON` |
| **Tournaments** | Stores tournament metadata and results | `TournamentID`, `Name`, `Venue`, `Result` |

## Query Optimization

To help coaches quickly identify top-performing players under pressure, the backend executes an optimized aggregation query.

```sql
SELECT 
    p.Name, 
    p.PrimarySport, 
    COUNT(m.MatchID) AS TotalMatchesPlayed,
    AVG(m.PerformanceRating) AS SeasonFormFactor
FROM Players p
JOIN MatchPerformance m ON p.PlayerID = m.PlayerID
GROUP BY p.PlayerID, p.Name, p.PrimarySport
HAVING AVG(m.PerformanceRating) >= 7.5
ORDER BY SeasonFormFactor DESC;
