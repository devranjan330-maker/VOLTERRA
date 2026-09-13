"""
VOLTERRA - Database Persistence Layer
=====================================
Conforms strictly to the VOLTERRA — Database Design Document (Version 1.0, September 2026).

Implements the normalized relational schema spanning 9 distinct tables:
1. system_states
2. predictions
3. decision_cycles
4. candidate_actions
5. simulation_outcomes
6. optimization_results
7. explanations
8. executions
9. measurements

Supports both SQLite file-based and in-memory databases with foreign keys enabled,
thread-safety, connection pooling/locking, schema initialization, recommended indexing,
and Section 6 query patterns:
- Full audit of one decision cycle
- Forecast accuracy tracking
- Historical improvement trend
- Candidate strategy performance
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Dict, Any, List, Optional, Tuple, Union


class DatabaseManager:
    """
    Manages SQLite relational persistence for VOLTERRA decision cycles.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or ":memory:"
        self._lock = Lock()
        self._in_memory_conn: Optional[sqlite3.Connection] = None

        if self.db_path == ":memory:":
            # Maintain an open connection for in-memory SQLite across transactions
            self._in_memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._in_memory_conn.execute("PRAGMA foreign_keys = ON;")
            self._init_schema(self._in_memory_conn)
        else:
            # Ensure parent directory exists for file-based DB
            path = Path(self.db_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with self._get_connection() as conn:
                self._init_schema(conn)

    def _get_connection(self) -> sqlite3.Connection:
        """Get an active SQLite connection with foreign keys enabled."""
        if self._in_memory_conn is not None:
            return self._in_memory_conn
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self, conn: sqlite3.Connection):
        """Create all 9 tables and recommended indexes per Sections 4 & 7."""
        cursor = conn.cursor()
        cursor.executescript("""
            PRAGMA foreign_keys = ON;

            -- 4.1 system_states
            CREATE TABLE IF NOT EXISTS system_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                demand_kw REAL NOT NULL,
                solar_generation_kw REAL NOT NULL,
                battery_level_pct REAL NOT NULL,
                temperature_c REAL NOT NULL,
                occupancy TEXT NOT NULL,
                source TEXT NOT NULL, -- 'observed', 'predicted', 'post_execution'
                created_at TEXT NOT NULL
            );

            -- 4.2 predictions
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                based_on_state_id INTEGER NOT NULL,
                forecasted_state_id INTEGER NOT NULL,
                horizon_minutes INTEGER NOT NULL,
                risk_classification TEXT NOT NULL, -- 'normal', 'at_risk', 'critical'
                notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (based_on_state_id) REFERENCES system_states(id) ON DELETE RESTRICT,
                FOREIGN KEY (forecasted_state_id) REFERENCES system_states(id) ON DELETE RESTRICT
            );

            -- 4.3 decision_cycles
            CREATE TABLE IF NOT EXISTS decision_cycles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_id INTEGER NOT NULL,
                status TEXT NOT NULL, -- 'pending', 'completed', 'no_action_needed', 'failed'
                created_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY (prediction_id) REFERENCES predictions(id) ON DELETE RESTRICT
            );

            -- 4.4 candidate_actions
            CREATE TABLE IF NOT EXISTS candidate_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_cycle_id INTEGER NOT NULL,
                candidate_key TEXT NOT NULL, -- 'A', 'B', 'C', 'D'
                label TEXT NOT NULL,
                description TEXT,
                FOREIGN KEY (decision_cycle_id) REFERENCES decision_cycles(id) ON DELETE CASCADE
            );

            -- 4.5 simulation_outcomes
            CREATE TABLE IF NOT EXISTS simulation_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_cycle_id INTEGER NOT NULL,
                candidate_action_id INTEGER NOT NULL,
                projected_state_id INTEGER NOT NULL,
                peak_demand_kw REAL NOT NULL,
                cost REAL NOT NULL,
                battery_reserve_pct REAL NOT NULL,
                renewable_utilization_pct REAL NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (decision_cycle_id) REFERENCES decision_cycles(id) ON DELETE CASCADE,
                FOREIGN KEY (candidate_action_id) REFERENCES candidate_actions(id) ON DELETE CASCADE,
                FOREIGN KEY (projected_state_id) REFERENCES system_states(id) ON DELETE RESTRICT
            );

            -- 4.6 optimization_results
            CREATE TABLE IF NOT EXISTS optimization_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_cycle_id INTEGER NOT NULL,
                selected_candidate_action_id INTEGER NOT NULL,
                objectives TEXT NOT NULL, -- JSON
                constraints TEXT NOT NULL, -- JSON
                scores TEXT NOT NULL, -- JSON
                created_at TEXT NOT NULL,
                FOREIGN KEY (decision_cycle_id) REFERENCES decision_cycles(id) ON DELETE CASCADE,
                FOREIGN KEY (selected_candidate_action_id) REFERENCES candidate_actions(id) ON DELETE RESTRICT
            );

            -- 4.7 explanations
            CREATE TABLE IF NOT EXISTS explanations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_cycle_id INTEGER NOT NULL,
                rationale TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (decision_cycle_id) REFERENCES decision_cycles(id) ON DELETE CASCADE
            );

            -- 4.8 executions
            CREATE TABLE IF NOT EXISTS executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_cycle_id INTEGER NOT NULL,
                mode TEXT NOT NULL, -- 'virtual' or 'physical'
                resulting_state_id INTEGER NOT NULL,
                status TEXT NOT NULL, -- 'executed', 'failed'
                created_at TEXT NOT NULL,
                FOREIGN KEY (decision_cycle_id) REFERENCES decision_cycles(id) ON DELETE CASCADE,
                FOREIGN KEY (resulting_state_id) REFERENCES system_states(id) ON DELETE RESTRICT
            );

            -- 4.9 measurements
            CREATE TABLE IF NOT EXISTS measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_cycle_id INTEGER NOT NULL,
                before_state_id INTEGER NOT NULL,
                after_state_id INTEGER NOT NULL,
                before_peak_kw REAL NOT NULL,
                after_peak_kw REAL NOT NULL,
                improvement_pct REAL NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (decision_cycle_id) REFERENCES decision_cycles(id) ON DELETE CASCADE,
                FOREIGN KEY (before_state_id) REFERENCES system_states(id) ON DELETE RESTRICT,
                FOREIGN KEY (after_state_id) REFERENCES system_states(id) ON DELETE RESTRICT
            );

            -- Section 7: Indexing Recommendations
            CREATE INDEX IF NOT EXISTS idx_system_states_ts ON system_states(timestamp);
            CREATE INDEX IF NOT EXISTS idx_decision_cycles_created ON decision_cycles(created_at);
            CREATE INDEX IF NOT EXISTS idx_candidate_actions_cycle ON candidate_actions(decision_cycle_id);
            CREATE INDEX IF NOT EXISTS idx_simulation_outcomes_cycle ON simulation_outcomes(decision_cycle_id);
            CREATE INDEX IF NOT EXISTS idx_measurements_cycle ON measurements(decision_cycle_id);
        """)
        conn.commit()

    # =========================================================================
    # ATOMIC WRITE OPERATIONS
    # =========================================================================

    def insert_system_state(
        self,
        timestamp: str,
        demand_kw: float,
        solar_generation_kw: float,
        battery_level_pct: float,
        temperature_c: float,
        occupancy: str,
        source: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        """Insert a state into system_states."""
        created_at = datetime.now(timezone.utc).isoformat()
        sql = """
            INSERT INTO system_states (
                timestamp, demand_kw, solar_generation_kw, battery_level_pct,
                temperature_c, occupancy, source, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            str(timestamp),
            float(demand_kw),
            float(solar_generation_kw),
            float(battery_level_pct),
            float(temperature_c),
            str(occupancy),
            str(source),
            created_at,
        )
        if conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.lastrowid

        with self._lock:
            c = self._get_connection()
            cursor = c.cursor()
            cursor.execute(sql, params)
            c.commit()
            if self._in_memory_conn is None:
                c.close()
            return cursor.lastrowid

    def record_full_cycle(
        self,
        observed_state: Dict[str, Any],
        forecast_result: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        sim_outcomes: List[Dict[str, Any]],
        optimization_result: Dict[str, Any],
        rationale: str,
        execution: Optional[Dict[str, Any]] = None,
        measurement: Optional[Dict[str, Any]] = None,
        cycle_status: str = "completed",
    ) -> int:
        """
        Atomically records all 9 entities of one complete decision cycle into the relational database.
        Returns the decision_cycle_id.
        """
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                now_str = datetime.now(timezone.utc).isoformat()

                # 1. Observed system_state
                obs_ts = observed_state.get("timestamp") or now_str
                obs_state_id = self.insert_system_state(
                    timestamp=obs_ts,
                    demand_kw=observed_state.get("demand_kw", 0.0),
                    solar_generation_kw=observed_state.get("solar_generation_kw", observed_state.get("supply_kw", 0.0)),
                    battery_level_pct=observed_state.get("battery_level_pct", observed_state.get("battery_percent", 0.0)),
                    temperature_c=observed_state.get("temperature_c", 25.0),
                    occupancy=observed_state.get("occupancy", "medium"),
                    source="observed",
                    conn=conn,
                )

                # 2. Forecasted system_state
                fc_demand = forecast_result.get("forecasted_demand_kw", observed_state.get("demand_kw", 0.0))
                fc_solar = forecast_result.get("forecasted_supply_kw", observed_state.get("solar_generation_kw", 0.0))
                fc_state_id = self.insert_system_state(
                    timestamp=forecast_result.get("timestamp") or obs_ts,
                    demand_kw=fc_demand,
                    solar_generation_kw=fc_solar,
                    battery_level_pct=observed_state.get("battery_level_pct", 0.0),
                    temperature_c=observed_state.get("temperature_c", 25.0),
                    occupancy=observed_state.get("occupancy", "medium"),
                    source="predicted",
                    conn=conn,
                )

                # 3. Prediction record
                cursor.execute(
                    """
                    INSERT INTO predictions (
                        based_on_state_id, forecasted_state_id, horizon_minutes,
                        risk_classification, notes, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        obs_state_id,
                        fc_state_id,
                        forecast_result.get("horizon_minutes", 30),
                        forecast_result.get("risk_classification", "normal"),
                        forecast_result.get("notes", ""),
                        now_str,
                    ),
                )
                prediction_id = cursor.lastrowid

                # 4. Decision Cycle record
                completed_at = now_str if cycle_status in ("completed", "executed") else None
                cursor.execute(
                    """
                    INSERT INTO decision_cycles (prediction_id, status, created_at, completed_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (prediction_id, cycle_status, now_str, completed_at),
                )
                cycle_id = cursor.lastrowid

                # 5. Candidate Actions records
                candidate_id_map: Dict[str, int] = {}
                for cand in candidates:
                    key = cand.get("id") or cand.get("candidate_key", "A")
                    label = cand.get("label", f"Candidate {key}")
                    desc = cand.get("description", "")
                    cursor.execute(
                        """
                        INSERT INTO candidate_actions (decision_cycle_id, candidate_key, label, description)
                        VALUES (?, ?, ?, ?)
                        """,
                        (cycle_id, key, label, desc),
                    )
                    candidate_id_map[key] = cursor.lastrowid

                # 6. Simulation Outcomes records
                for outcome in sim_outcomes:
                    cand_key = outcome.get("candidate_id") or outcome.get("candidate_key")
                    cand_db_id = candidate_id_map.get(cand_key)
                    if not cand_db_id and candidate_id_map:
                        cand_db_id = list(candidate_id_map.values())[0]

                    # Insert projected system_state
                    proj_state = outcome.get("projected_state") or {}
                    proj_ts = proj_state.get("timestamp") or obs_ts
                    proj_state_id = self.insert_system_state(
                        timestamp=proj_ts,
                        demand_kw=proj_state.get("demand_kw", outcome.get("peak_demand_kw", 0.0)),
                        solar_generation_kw=proj_state.get("solar_generation_kw", 0.0),
                        battery_level_pct=proj_state.get("battery_level_pct", outcome.get("battery_reserve_pct", 0.0)),
                        temperature_c=proj_state.get("temperature_c", 25.0),
                        occupancy=proj_state.get("occupancy", "medium"),
                        source="predicted",
                        conn=conn,
                    )

                    metrics = outcome.get("metrics") or outcome
                    cursor.execute(
                        """
                        INSERT INTO simulation_outcomes (
                            decision_cycle_id, candidate_action_id, projected_state_id,
                            peak_demand_kw, cost, battery_reserve_pct,
                            renewable_utilization_pct, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            cycle_id,
                            cand_db_id,
                            proj_state_id,
                            float(metrics.get("peak_demand_kw", 0.0)),
                            float(metrics.get("cost", 0.0)),
                            float(metrics.get("battery_reserve_pct", 0.0)),
                            float(metrics.get("renewable_utilization_pct", 0.0)),
                            now_str,
                        ),
                    )

                # 7. Optimization Result record
                selected_key = optimization_result.get("selected_candidate_id", "A")
                selected_db_id = candidate_id_map.get(selected_key)
                if not selected_db_id and candidate_id_map:
                    selected_db_id = list(candidate_id_map.values())[0]

                cursor.execute(
                    """
                    INSERT INTO optimization_results (
                        decision_cycle_id, selected_candidate_action_id,
                        objectives, constraints, scores, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cycle_id,
                        selected_db_id,
                        json.dumps(optimization_result.get("objectives", {})),
                        json.dumps(optimization_result.get("constraints", {})),
                        json.dumps(optimization_result.get("scores", {})),
                        now_str,
                    ),
                )

                # 8. Explanation record
                cursor.execute(
                    """
                    INSERT INTO explanations (decision_cycle_id, rationale, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (cycle_id, rationale, now_str),
                )

                # 9. Optional Execution record
                if execution:
                    res_state = execution.get("resulting_state") or {}
                    res_ts = res_state.get("timestamp") or now_str
                    res_state_id = self.insert_system_state(
                        timestamp=res_ts,
                        demand_kw=res_state.get("demand_kw", 0.0),
                        solar_generation_kw=res_state.get("solar_generation_kw", 0.0),
                        battery_level_pct=res_state.get("battery_level_pct", 0.0),
                        temperature_c=res_state.get("temperature_c", 25.0),
                        occupancy=res_state.get("occupancy", "medium"),
                        source="post_execution",
                        conn=conn,
                    )
                    cursor.execute(
                        """
                        INSERT INTO executions (
                            decision_cycle_id, mode, resulting_state_id, status, created_at
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            cycle_id,
                            execution.get("mode", "virtual"),
                            res_state_id,
                            execution.get("status", "executed"),
                            now_str,
                        ),
                    )

                # 10. Optional Measurement record
                if measurement:
                    bef_state_id = obs_state_id
                    aft_state_id = res_state_id if execution else obs_state_id
                    cursor.execute(
                        """
                        INSERT INTO measurements (
                            decision_cycle_id, before_state_id, after_state_id,
                            before_peak_kw, after_peak_kw, improvement_pct, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            cycle_id,
                            bef_state_id,
                            aft_state_id,
                            float(measurement.get("before_peak_kw", 0.0)),
                            float(measurement.get("after_peak_kw", 0.0)),
                            float(measurement.get("improvement_pct", 0.0)),
                            now_str,
                        ),
                    )

                conn.commit()
                return cycle_id
            except Exception:
                conn.rollback()
                raise
            finally:
                if self._in_memory_conn is None:
                    conn.close()

    def update_latest_execution_and_measurement(
        self,
        cycle_id: Optional[int] = None,
        execution_data: Optional[Dict[str, Any]] = None,
        measurement_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Updates the execution and/or measurement records of a cycle (or latest cycle).
        """
        with self._lock:
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                now_str = datetime.now(timezone.utc).isoformat()

                if cycle_id is None:
                    cursor.execute("SELECT id FROM decision_cycles ORDER BY id DESC LIMIT 1")
                    row = cursor.fetchone()
                    if not row:
                        return False
                    cycle_id = row[0]

                # Update Execution if provided
                res_state_id = None
                if execution_data:
                    res_state = execution_data.get("resulting_state") or {}
                    res_state_id = self.insert_system_state(
                        timestamp=res_state.get("timestamp") or now_str,
                        demand_kw=res_state.get("demand_kw", 0.0),
                        solar_generation_kw=res_state.get("solar_generation_kw", 0.0),
                        battery_level_pct=res_state.get("battery_level_pct", 0.0),
                        temperature_c=res_state.get("temperature_c", 25.0),
                        occupancy=res_state.get("occupancy", "medium"),
                        source="post_execution",
                        conn=conn,
                    )
                    cursor.execute(
                        """
                        INSERT INTO executions (decision_cycle_id, mode, resulting_state_id, status, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            cycle_id,
                            execution_data.get("mode", "virtual"),
                            res_state_id,
                            execution_data.get("status", "executed"),
                            now_str,
                        ),
                    )

                # Update Measurement if provided
                if measurement_data:
                    # Find pre-execution state for this cycle
                    cursor.execute(
                        """
                        SELECT p.based_on_state_id
                        FROM decision_cycles dc
                        JOIN predictions p ON dc.prediction_id = p.id
                        WHERE dc.id = ?
                        """,
                        (cycle_id,),
                    )
                    p_row = cursor.fetchone()
                    before_state_id = p_row[0] if p_row else 1

                    if res_state_id is None:
                        # Check if executions exists
                        cursor.execute(
                            "SELECT resulting_state_id FROM executions WHERE decision_cycle_id = ? ORDER BY id DESC LIMIT 1",
                            (cycle_id,),
                        )
                        ex_row = cursor.fetchone()
                        after_state_id = ex_row[0] if ex_row else before_state_id
                    else:
                        after_state_id = res_state_id

                    cursor.execute(
                        """
                        INSERT INTO measurements (
                            decision_cycle_id, before_state_id, after_state_id,
                            before_peak_kw, after_peak_kw, improvement_pct, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            cycle_id,
                            before_state_id,
                            after_state_id,
                            float(measurement_data.get("before_peak_kw", 0.0)),
                            float(measurement_data.get("after_peak_kw", 0.0)),
                            float(measurement_data.get("improvement_pct", 0.0)),
                            now_str,
                        ),
                    )

                # Mark cycle completed
                cursor.execute(
                    "UPDATE decision_cycles SET status = 'completed', completed_at = ? WHERE id = ?",
                    (now_str, cycle_id),
                )
                conn.commit()
                return True
            except Exception:
                conn.rollback()
                raise
            finally:
                if self._in_memory_conn is None:
                    conn.close()

    # =========================================================================
    # SECTION 6 QUERY PATTERNS
    # =========================================================================

    def get_full_audit(self, cycle_id: int) -> Optional[Dict[str, Any]]:
        """
        Pattern 1: Full audit of one decision cycle.
        Join decision_cycles -> predictions -> candidate_actions -> simulation_outcomes ->
             optimization_results -> explanations -> executions -> measurements
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Cycle & Prediction
            cursor.execute(
                """
                SELECT 
                    dc.id AS cycle_id, dc.status, dc.created_at, dc.completed_at,
                    p.id AS pred_id, p.horizon_minutes, p.risk_classification, p.notes,
                    s_base.id AS base_id, s_base.timestamp AS base_ts, s_base.demand_kw AS base_demand,
                    s_base.solar_generation_kw AS base_solar, s_base.battery_level_pct AS base_battery,
                    s_base.temperature_c AS base_temp, s_base.occupancy AS base_occ,
                    s_fc.id AS fc_id, s_fc.timestamp AS fc_ts, s_fc.demand_kw AS fc_demand,
                    s_fc.solar_generation_kw AS fc_solar, s_fc.battery_level_pct AS fc_battery
                FROM decision_cycles dc
                JOIN predictions p ON dc.prediction_id = p.id
                JOIN system_states s_base ON p.based_on_state_id = s_base.id
                JOIN system_states s_fc ON p.forecasted_state_id = s_fc.id
                WHERE dc.id = ?
                """,
                (cycle_id,),
            )
            row = cursor.fetchone()
            if not row:
                if self._in_memory_conn is None:
                    conn.close()
                return None

            audit: Dict[str, Any] = {
                "decision_cycle": {
                    "id": row[0],
                    "status": row[1],
                    "created_at": row[2],
                    "completed_at": row[3],
                },
                "prediction": {
                    "id": row[4],
                    "horizon_minutes": row[5],
                    "risk_classification": row[6],
                    "notes": row[7],
                    "based_on_state": {
                        "id": row[8],
                        "timestamp": row[9],
                        "demand_kw": row[10],
                        "solar_generation_kw": row[11],
                        "battery_level_pct": row[12],
                        "temperature_c": row[13],
                        "occupancy": row[14],
                        "source": "observed",
                    },
                    "forecasted_state": {
                        "id": row[15],
                        "timestamp": row[16],
                        "demand_kw": row[17],
                        "solar_generation_kw": row[18],
                        "battery_level_pct": row[19],
                        "source": "predicted",
                    },
                },
                "candidate_actions": [],
                "simulation_outcomes": [],
                "optimization_result": None,
                "explanation": None,
                "execution": None,
                "measurement": None,
            }

            # Candidate Actions
            cursor.execute(
                """
                SELECT id, candidate_key, label, description
                FROM candidate_actions
                WHERE decision_cycle_id = ?
                ORDER BY candidate_key ASC
                """,
                (cycle_id,),
            )
            for cand_row in cursor.fetchall():
                audit["candidate_actions"].append({
                    "id": cand_row[0],
                    "candidate_key": cand_row[1],
                    "label": cand_row[2],
                    "description": cand_row[3],
                })

            # Simulation Outcomes
            cursor.execute(
                """
                SELECT 
                    so.id, so.candidate_action_id, ca.candidate_key,
                    so.peak_demand_kw, so.cost, so.battery_reserve_pct,
                    so.renewable_utilization_pct, so.created_at,
                    st.id, st.demand_kw, st.battery_level_pct
                FROM simulation_outcomes so
                JOIN candidate_actions ca ON so.candidate_action_id = ca.id
                JOIN system_states st ON so.projected_state_id = st.id
                WHERE so.decision_cycle_id = ?
                ORDER BY ca.candidate_key ASC
                """,
                (cycle_id,),
            )
            for sim_row in cursor.fetchall():
                audit["simulation_outcomes"].append({
                    "id": sim_row[0],
                    "candidate_action_id": sim_row[1],
                    "candidate_key": sim_row[2],
                    "peak_demand_kw": sim_row[3],
                    "cost": sim_row[4],
                    "battery_reserve_pct": sim_row[5],
                    "renewable_utilization_pct": sim_row[6],
                    "created_at": sim_row[7],
                    "projected_state": {
                        "id": sim_row[8],
                        "demand_kw": sim_row[9],
                        "battery_level_pct": sim_row[10],
                        "source": "predicted",
                    },
                })

            # Optimization Result
            cursor.execute(
                """
                SELECT 
                    opt.id, opt.selected_candidate_action_id, ca.candidate_key,
                    opt.objectives, opt.constraints, opt.scores, opt.created_at
                FROM optimization_results opt
                JOIN candidate_actions ca ON opt.selected_candidate_action_id = ca.id
                WHERE opt.decision_cycle_id = ?
                """,
                (cycle_id,),
            )
            opt_row = cursor.fetchone()
            if opt_row:
                audit["optimization_result"] = {
                    "id": opt_row[0],
                    "selected_candidate_action_id": opt_row[1],
                    "selected_candidate_key": opt_row[2],
                    "objectives": json.loads(opt_row[3]) if opt_row[3] else {},
                    "constraints": json.loads(opt_row[4]) if opt_row[4] else {},
                    "scores": json.loads(opt_row[5]) if opt_row[5] else {},
                    "created_at": opt_row[6],
                }

            # Explanation
            cursor.execute(
                """
                SELECT id, rationale, created_at
                FROM explanations
                WHERE decision_cycle_id = ?
                """,
                (cycle_id,),
            )
            exp_row = cursor.fetchone()
            if exp_row:
                audit["explanation"] = {
                    "id": exp_row[0],
                    "rationale": exp_row[1],
                    "created_at": exp_row[2],
                }

            # Execution
            cursor.execute(
                """
                SELECT ex.id, ex.mode, ex.status, ex.created_at,
                       st.id, st.demand_kw, st.battery_level_pct
                FROM executions ex
                JOIN system_states st ON ex.resulting_state_id = st.id
                WHERE ex.decision_cycle_id = ?
                ORDER BY ex.id DESC LIMIT 1
                """,
                (cycle_id,),
            )
            ex_row = cursor.fetchone()
            if ex_row:
                audit["execution"] = {
                    "id": ex_row[0],
                    "mode": ex_row[1],
                    "status": ex_row[2],
                    "created_at": ex_row[3],
                    "resulting_state": {
                        "id": ex_row[4],
                        "demand_kw": ex_row[5],
                        "battery_level_pct": ex_row[6],
                        "source": "post_execution",
                    },
                }

            # Measurement
            cursor.execute(
                """
                SELECT m.id, m.before_peak_kw, m.after_peak_kw, m.improvement_pct, m.created_at,
                       sb.id, sb.demand_kw, sa.id, sa.demand_kw
                FROM measurements m
                JOIN system_states sb ON m.before_state_id = sb.id
                JOIN system_states sa ON m.after_state_id = sa.id
                WHERE m.decision_cycle_id = ?
                ORDER BY m.id DESC LIMIT 1
                """,
                (cycle_id,),
            )
            m_row = cursor.fetchone()
            if m_row:
                audit["measurement"] = {
                    "id": m_row[0],
                    "before_peak_kw": m_row[1],
                    "after_peak_kw": m_row[2],
                    "improvement_pct": m_row[3],
                    "created_at": m_row[4],
                    "before_state_id": m_row[5],
                    "after_state_id": m_row[7],
                }

            if self._in_memory_conn is None:
                conn.close()

            return audit

    def get_forecast_accuracy(self) -> Dict[str, Any]:
        """
        Pattern 2: Forecast accuracy tracking.
        Compare predictions.forecasted_state_id values against later system_states
        with source = 'observed' at matching timestamps.
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Join predicted state with later observed state at matching timestamp
            cursor.execute("""
                SELECT 
                    p.id AS prediction_id,
                    p.created_at AS predicted_at,
                    p.horizon_minutes,
                    s_pred.timestamp AS target_timestamp,
                    s_pred.demand_kw AS forecasted_demand,
                    s_obs.demand_kw AS observed_demand,
                    abs(s_pred.demand_kw - s_obs.demand_kw) AS error_kw
                FROM predictions p
                JOIN system_states s_pred ON p.forecasted_state_id = s_pred.id
                JOIN system_states s_obs ON s_pred.timestamp = s_obs.timestamp AND s_obs.source = 'observed'
                WHERE s_pred.id != s_obs.id
                ORDER BY p.id ASC
            """)
            rows = cursor.fetchall()

            comparisons = []
            errors = []
            for r in rows:
                fc_val = r[4]
                obs_val = r[5]
                err = abs(fc_val - obs_val)
                errors.append(err)
                pct_err = round((err / obs_val * 100.0), 2) if obs_val > 0 else 0.0
                comparisons.append({
                    "prediction_id": r[0],
                    "predicted_at": r[1],
                    "horizon_minutes": r[2],
                    "target_timestamp": r[3],
                    "forecasted_demand_kw": round(fc_val, 2),
                    "observed_demand_kw": round(obs_val, 2),
                    "error_kw": round(err, 2),
                    "error_pct": pct_err,
                })

            mae = round(sum(errors) / len(errors), 3) if errors else 0.0
            avg_accuracy_pct = round(max(0.0, 100.0 - (sum(c["error_pct"] for c in comparisons) / len(comparisons))), 1) if comparisons else 100.0

            result = {
                "total_evaluations": len(comparisons),
                "mean_absolute_error_kw": mae,
                "average_accuracy_pct": avg_accuracy_pct,
                "evaluations": comparisons,
            }

            if self._in_memory_conn is None:
                conn.close()

            return result

    def get_historical_improvement_trend(self) -> Dict[str, Any]:
        """
        Pattern 3: Historical improvement trend.
        Aggregate measurements.improvement_pct over time.
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT 
                    m.decision_cycle_id,
                    m.created_at,
                    m.before_peak_kw,
                    m.after_peak_kw,
                    m.improvement_pct
                FROM measurements m
                ORDER BY m.created_at ASC, m.id ASC
            """)
            rows = cursor.fetchall()

            datapoints = []
            improvements = []
            for r in rows:
                imp = r[4]
                improvements.append(imp)
                datapoints.append({
                    "cycle_id": r[0],
                    "timestamp": r[1],
                    "before_peak_kw": round(r[2], 2),
                    "after_peak_kw": round(r[3], 2),
                    "improvement_pct": round(imp, 2),
                })

            count = len(improvements)
            avg_imp = round(sum(improvements) / count, 2) if count > 0 else 0.0
            max_imp = round(max(improvements), 2) if count > 0 else 0.0
            min_imp = round(min(improvements), 2) if count > 0 else 0.0

            result = {
                "total_cycles_measured": count,
                "average_improvement_pct": avg_imp,
                "max_improvement_pct": max_imp,
                "min_improvement_pct": min_imp,
                "trend": datapoints,
            }

            if self._in_memory_conn is None:
                conn.close()

            return result

    def get_candidate_strategy_performance(self) -> Dict[str, Any]:
        """
        Pattern 4: Candidate strategy performance.
        Aggregate optimization_results.selected_candidate_action_id frequency
        and associated measurements.improvement_pct.
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT 
                    ca.candidate_key,
                    ca.label,
                    COUNT(opt.id) AS selection_count,
                    AVG(m.improvement_pct) AS avg_improvement_pct,
                    MIN(m.improvement_pct) AS min_improvement_pct,
                    MAX(m.improvement_pct) AS max_improvement_pct
                FROM optimization_results opt
                JOIN candidate_actions ca ON opt.selected_candidate_action_id = ca.id
                LEFT JOIN measurements m ON opt.decision_cycle_id = m.decision_cycle_id
                GROUP BY ca.candidate_key, ca.label
                ORDER BY selection_count DESC
            """)
            rows = cursor.fetchall()

            strategies = []
            total_selections = 0
            for r in rows:
                cnt = r[2]
                total_selections += cnt
                strategies.append({
                    "candidate_key": r[0],
                    "label": r[1],
                    "selection_count": cnt,
                    "avg_improvement_pct": round(r[3], 2) if r[3] is not None else 0.0,
                    "min_improvement_pct": round(r[4], 2) if r[4] is not None else 0.0,
                    "max_improvement_pct": round(r[5], 2) if r[5] is not None else 0.0,
                })

            for s in strategies:
                s["selection_share_pct"] = round((s["selection_count"] / total_selections * 100.0), 1) if total_selections > 0 else 0.0

            result = {
                "total_decisions": total_selections,
                "strategies": strategies,
            }

            if self._in_memory_conn is None:
                conn.close()

            return result

    def query_history_summary(
        self,
        from_time: Optional[str] = None,
        to_time: Optional[str] = None,
        limit: Optional[int] = 50,
    ) -> List[Dict[str, Any]]:
        """
        Reconstructs the canonical decision cycle summary format expected by GET /v1/history.
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()

            query_sql = """
                SELECT 
                    dc.id AS cycle_id,
                    dc.created_at AS cycle_ts,
                    p.risk_classification,
                    s_base.timestamp AS base_ts,
                    s_base.demand_kw AS base_demand,
                    s_base.solar_generation_kw AS base_solar,
                    s_base.battery_level_pct AS base_battery,
                    s_base.temperature_c AS base_temp,
                    s_base.occupancy AS base_occ,
                    ca.candidate_key,
                    exp.rationale,
                    opt.scores,
                    ex.status AS exec_status,
                    m.before_peak_kw,
                    m.after_peak_kw,
                    m.improvement_pct
                FROM decision_cycles dc
                JOIN predictions p ON dc.prediction_id = p.id
                JOIN system_states s_base ON p.based_on_state_id = s_base.id
                LEFT JOIN optimization_results opt ON dc.id = opt.decision_cycle_id
                LEFT JOIN candidate_actions ca ON opt.selected_candidate_action_id = ca.id
                LEFT JOIN explanations exp ON dc.id = exp.decision_cycle_id
                LEFT JOIN executions ex ON dc.id = ex.decision_cycle_id
                LEFT JOIN measurements m ON dc.id = m.decision_cycle_id
                WHERE 1=1
            """
            params = []
            if from_time:
                query_sql += " AND dc.created_at >= ?"
                params.append(from_time)
            if to_time:
                query_sql += " AND dc.created_at <= ?"
                params.append(to_time)

            query_sql += " ORDER BY dc.id ASC"
            if limit and limit > 0:
                query_sql += f" LIMIT {limit}"

            cursor.execute(query_sql, params)
            rows = cursor.fetchall()

            cycles = []
            for r in rows:
                outcome = None
                if r[13] is not None or r[12] is not None:
                    outcome = {
                        "status": r[12] or "executed",
                        "before_peak_kw": r[13] if r[13] is not None else r[4],
                        "after_peak_kw": r[14] if r[14] is not None else r[4],
                        "improvement_pct": r[15] if r[15] is not None else 0.0,
                    }

                cycle_item = {
                    "cycle_id": r[0],
                    "timestamp": r[1],
                    "system_state": {
                        "timestamp": r[3],
                        "demand_kw": r[4],
                        "solar_generation_kw": r[5],
                        "battery_level_pct": r[6],
                        "temperature_c": r[7],
                        "occupancy": r[8],
                    },
                    "risk_classification": r[2],
                    "decision": {
                        "selected_candidate_id": r[9] or "A",
                        "rationale": r[10] or "",
                        "scores": json.loads(r[11]) if r[11] else {},
                    },
                    "outcome": outcome,
                }
                cycles.append(cycle_item)

            if self._in_memory_conn is None:
                conn.close()

            return cycles
