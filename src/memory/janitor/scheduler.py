# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Janitor scheduling logic.

Handles scheduling for nightly janitor runs.

Related GitHub Issues:
- #102: Janitor Process Framework

ADR Reference: ADR-003 Memory Architecture, Phase 1d (Janitor Process)
"""

from datetime import datetime, timedelta, timezone
from typing import Optional


class JanitorScheduler:
    """Scheduler for janitor process runs.

    Determines when the janitor should run based on
    configurable intervals.

    Attributes:
        schedule_interval_hours: Hours between janitor runs.

    Example:
        >>> scheduler = JanitorScheduler(schedule_interval_hours=24)
        >>> if scheduler.should_run(last_run):
        ...     await janitor.run_all()
    """

    def __init__(self, schedule_interval_hours: int = 24):
        """Initialize the scheduler.

        Args:
            schedule_interval_hours: Hours between runs (default 24).
        """
        self.schedule_interval_hours = schedule_interval_hours

    def should_run(self, last_run: Optional[datetime] = None) -> bool:
        """Determine if janitor should run now.

        Args:
            last_run: Timestamp of last janitor run.

        Returns:
            True if janitor should run.
        """
        if last_run is None:
            return True

        now = datetime.now(timezone.utc)

        # Ensure timezone aware comparison
        if last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=timezone.utc)

        time_since_last = now - last_run
        interval = timedelta(hours=self.schedule_interval_hours)

        return time_since_last >= interval

    def get_next_run(self, last_run: Optional[datetime] = None) -> datetime:
        """Calculate the next scheduled run time.

        Args:
            last_run: Timestamp of last janitor run.

        Returns:
            Datetime of next scheduled run.
        """
        now = datetime.now(timezone.utc)

        if last_run is None:
            return now

        # Ensure timezone aware
        if last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=timezone.utc)

        next_run = last_run + timedelta(hours=self.schedule_interval_hours)

        # If next run is in the past, schedule for now
        if next_run < now:
            return now

        return next_run
