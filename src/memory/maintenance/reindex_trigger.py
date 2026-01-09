# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Auto-reindex trigger for HNSW recall degradation.

Monitors recall health and triggers reindexing when thresholds are breached.
Supports periodic scheduled checks and on-demand health checks.

Related ADR: ADR-003 Memory Architecture, Phase 0 (HNSW Recall Health Monitoring)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable

from src.memory.evaluation.recall_health import RecallHealthMonitor, RecallHealthResult

logger = logging.getLogger(__name__)


@dataclass
class ReindexEvent:
    """Record of a reindex event.

    Attributes:
        timestamp: When the reindex was triggered.
        reason: Why reindex was triggered.
        health_result: The health check result that triggered reindex.
        completed: Whether reindex completed successfully.
        error: Error message if reindex failed.
    """

    timestamp: datetime
    reason: str
    health_result: RecallHealthResult
    completed: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason,
            "recall_at_k": self.health_result.recall_at_k,
            "passed_absolute": self.health_result.passed_absolute,
            "passed_drift": self.health_result.passed_drift,
            "drift_pct": self.health_result.drift_pct,
            "completed": self.completed,
            "error": self.error,
        }


class ReindexTrigger:
    """Trigger reindex when recall drops below threshold.

    This class monitors HNSW recall health and automatically triggers
    reindexing when recall degrades below thresholds. It can run
    periodic checks and also supports on-demand health checks.

    Example:
        >>> trigger = ReindexTrigger(
        ...     recall_monitor=monitor,
        ...     reindex_callback=reindex_function,
        ...     alert_callback=send_alert,
        ... )
        >>> triggered = await trigger.check_and_trigger(golden_queries)
        >>> if triggered:
        ...     print("Reindex was triggered due to recall degradation")
    """

    def __init__(
        self,
        recall_monitor: RecallHealthMonitor,
        reindex_callback: Callable[[], Awaitable[None]] | Callable[[], None],
        alert_callback: Callable[[str, RecallHealthResult], None] | None = None,
        cooldown_hours: float = 24.0,
    ):
        """Initialize the reindex trigger.

        Args:
            recall_monitor: Monitor for recall health checks.
            reindex_callback: Async or sync function to call for reindex.
            alert_callback: Optional callback for alerts.
                           Signature: (message: str, result: RecallHealthResult) -> None
            cooldown_hours: Minimum hours between reindex triggers.
        """
        self._monitor = recall_monitor
        self._reindex_callback = reindex_callback
        self._alert_callback = alert_callback
        self._cooldown_hours = cooldown_hours
        self._last_reindex: datetime | None = None
        self._history: list[ReindexEvent] = []
        self._scheduled_task: asyncio.Task[None] | None = None

    @property
    def last_reindex(self) -> datetime | None:
        """Return timestamp of last reindex trigger."""
        return self._last_reindex

    @property
    def history(self) -> list[ReindexEvent]:
        """Return history of reindex events."""
        return self._history.copy()

    def _is_in_cooldown(self) -> bool:
        """Check if we're within the cooldown period."""
        if self._last_reindex is None:
            return False

        elapsed = (datetime.now() - self._last_reindex).total_seconds() / 3600
        return elapsed < self._cooldown_hours

    async def check_and_trigger(
        self,
        queries: list[str],
        k: int = 10,
        force: bool = False,
    ) -> bool:
        """Run health check and trigger reindex if needed.

        Args:
            queries: List of query strings (golden query set).
            k: Number of results to consider.
            force: If True, ignore cooldown period.

        Returns:
            True if reindex was triggered.
        """
        # Check cooldown unless forced
        if not force and self._is_in_cooldown():
            logger.info(
                "Skipping reindex check - in cooldown period "
                f"(last reindex: {self._last_reindex})"
            )
            return False

        # Run health check
        result = self._monitor.check_health(queries, k)

        # Log result
        logger.info(
            f"Recall health check: recall={result.recall_at_k:.2%}, "
            f"passed_absolute={result.passed_absolute}, "
            f"passed_drift={result.passed_drift}"
        )

        # Check if reindex is needed
        if self._monitor.should_reindex(result):
            return await self._trigger_reindex(result)

        return False

    async def _trigger_reindex(self, result: RecallHealthResult) -> bool:
        """Trigger reindex and record event.

        Args:
            result: The health check result that triggered reindex.

        Returns:
            True if reindex was triggered successfully.
        """
        # Determine reason
        reasons = []
        if not result.passed_absolute:
            reasons.append(
                f"recall {result.recall_at_k:.2%} below threshold "
                f"{RecallHealthMonitor.ABSOLUTE_THRESHOLD:.2%}"
            )
        if not result.passed_drift:
            reasons.append(
                f"drift {result.drift_pct:.2%} exceeds threshold "
                f"{RecallHealthMonitor.DRIFT_THRESHOLD:.2%}"
            )
        reason = "; ".join(reasons) if reasons else "unknown"

        # Create event
        event = ReindexEvent(
            timestamp=datetime.now(),
            reason=reason,
            health_result=result,
        )

        # Send alert
        if self._alert_callback:
            alert_msg = f"HNSW recall degradation detected: {reason}"
            try:
                self._alert_callback(alert_msg, result)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

        # Trigger reindex
        try:
            logger.warning(f"Triggering reindex: {reason}")

            # Handle both sync and async callbacks
            # Run sync callbacks in thread pool to avoid blocking event loop
            if asyncio.iscoroutinefunction(self._reindex_callback):
                await self._reindex_callback()
            else:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self._reindex_callback)

            event.completed = True
            self._last_reindex = datetime.now()
            logger.info("Reindex completed successfully")

        except Exception as e:
            event.error = str(e)
            logger.error(f"Reindex failed: {e}")
            raise

        finally:
            self._history.append(event)

        return event.completed

    async def check_filtered_and_trigger(
        self,
        queries: list[str],
        filter_fn: Callable,
        hnsw_filter: Callable,
        filter_name: str,
        k: int = 10,
        force: bool = False,
    ) -> bool:
        """Run filtered health check and trigger reindex if needed.

        Args:
            queries: List of query strings.
            filter_fn: Filter function for brute-force search.
            hnsw_filter: Filtered HNSW search function.
            filter_name: Name for the filter.
            k: Number of results to consider.
            force: If True, ignore cooldown period.

        Returns:
            True if reindex was triggered.
        """
        if not force and self._is_in_cooldown():
            logger.info("Skipping filtered reindex check - in cooldown period")
            return False

        result = self._monitor.check_filtered_health(
            queries, filter_fn, hnsw_filter, filter_name, k
        )

        logger.info(
            f"Filtered recall health check ({filter_name}): "
            f"recall={result.recall_at_k:.2%}, "
            f"passed_absolute={result.passed_absolute}"
        )

        if self._monitor.should_reindex(result):
            return await self._trigger_reindex(result)

        return False

    def schedule_periodic_check(
        self,
        queries: list[str],
        interval_hours: float = 24.0,
        k: int = 10,
    ) -> None:
        """Schedule periodic recall health checks.

        Args:
            queries: List of query strings (golden query set).
            interval_hours: Hours between checks.
            k: Number of results to consider.
        """
        if self._scheduled_task is not None and not self._scheduled_task.done():
            self._scheduled_task.cancel()

        async def periodic_check() -> None:
            while True:
                try:
                    await asyncio.sleep(interval_hours * 3600)
                    await self.check_and_trigger(queries, k)
                except asyncio.CancelledError:
                    logger.info("Periodic recall check cancelled")
                    break
                except Exception as e:
                    logger.error(f"Periodic recall check failed: {e}")

        self._scheduled_task = asyncio.create_task(periodic_check())
        logger.info(f"Scheduled periodic recall checks every {interval_hours} hours")

    def cancel_scheduled_check(self) -> None:
        """Cancel any scheduled periodic check."""
        if self._scheduled_task is not None:
            self._scheduled_task.cancel()
            self._scheduled_task = None

    def get_status(self) -> dict[str, Any]:
        """Get current trigger status.

        Returns:
            Dictionary with trigger status information.
        """
        return {
            "last_reindex": (
                self._last_reindex.isoformat() if self._last_reindex else None
            ),
            "in_cooldown": self._is_in_cooldown(),
            "cooldown_hours": self._cooldown_hours,
            "history_count": len(self._history),
            "scheduled_check_active": (
                self._scheduled_task is not None
                and not self._scheduled_task.done()
            ),
        }
