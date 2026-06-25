"""
Scheduler - APScheduler wrapper for posting cycle scheduling
"""
import logging
import random
from datetime import datetime
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self):
        """Initialize AsyncIOScheduler"""
        self._scheduler = AsyncIOScheduler()
        self._mode = None
        self._running = False
        self._config = {}
        self._cycle_function = None
        logger.info("Scheduler initialized")
    
    def start(self, mode: str, config: dict, cycle_function):
        """
        Start scheduler with specified mode
        
        Args:
            mode: "interval", "fixed", or "random"
            config: Configuration dict for the mode
            cycle_function: Async function to call on each cycle
        """
        if self._running:
            logger.warning("Scheduler already running. Stopping first.")
            self.stop()
        
        self._mode = mode
        self._config = config
        self._cycle_function = cycle_function
        
        # Recreate scheduler (APScheduler cannot restart after shutdown)
        self._scheduler = AsyncIOScheduler()
        
        try:
            self._scheduler.start()
            
            if mode == "interval":
                self._start_interval_mode(config)
            elif mode == "fixed":
                self._start_fixed_mode(config)
            elif mode == "random":
                self._start_random_mode(config)
            else:
                raise ValueError(f"Invalid mode: {mode}")
            
            self._running = True
            logger.info(f"Scheduler started in {mode} mode")
            
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}")
            raise
    
    def _start_interval_mode(self, config: dict):
        """Start interval mode - execute every N minutes"""
        interval_minutes = config.get("interval_minutes", 30)
        
        self._scheduler.add_job(
            self._cycle_function,
            IntervalTrigger(minutes=interval_minutes),
            id="posting_cycle"
        )
        
        logger.info(f"Interval mode: Every {interval_minutes} minutes")
    
    def _start_fixed_mode(self, config: dict):
        """Start fixed times mode - execute at specific times daily"""
        times = config.get("times", [])
        
        if not times:
            raise ValueError("Fixed mode requires 'times' array")
        
        for time_str in times:
            try:
                hour, minute = map(int, time_str.split(":"))
                
                self._scheduler.add_job(
                    self._cycle_function,
                    CronTrigger(hour=hour, minute=minute),
                    id=f"posting_cycle_{time_str}"
                )
                
                logger.info(f"Fixed mode: Added job for {time_str}")
                
            except ValueError:
                logger.warning(f"Invalid time format: {time_str}, skipping")
    
    def _start_random_mode(self, config: dict):
        """Start random delay mode - randomize interval after each run"""
        min_minutes = config.get("min_minutes", 20)
        max_minutes = config.get("max_minutes", 60)
        
        async def wrapped_cycle():
            """Wrapper that reschedules after each execution"""
            try:
                await self._cycle_function()
            except Exception as e:
                logger.error(f"Cycle function raised exception: {e}")
            finally:
                # Reschedule with new random interval
                self._reschedule_random(min_minutes, max_minutes)
        
        # Initial schedule with random delay
        delay = random.uniform(min_minutes, max_minutes)
        
        self._scheduler.add_job(
            wrapped_cycle,
            IntervalTrigger(minutes=delay),
            id="posting_cycle"
        )
        
        logger.info(f"Random mode: First run in {delay:.1f} minutes (range: {min_minutes}-{max_minutes})")
    
    def _reschedule_random(self, min_minutes: int, max_minutes: int):
        """Reschedule with new random interval"""
        if not self._running:
            return
        
        delay = random.uniform(min_minutes, max_minutes)
        
        # Remove old job
        self._scheduler.remove_job("posting_cycle")
        
        # Add new job with new delay
        async def wrapped_cycle():
            try:
                await self._cycle_function()
            except Exception as e:
                logger.error(f"Cycle function raised exception: {e}")
            finally:
                self._reschedule_random(min_minutes, max_minutes)
        
        self._scheduler.add_job(
            wrapped_cycle,
            IntervalTrigger(minutes=delay),
            id="posting_cycle"
        )
        
        logger.info(f"Random mode: Next run in {delay:.1f} minutes")
    
    def stop(self):
        """Shutdown all scheduled jobs"""
        if not self._running:
            logger.warning("Scheduler not running")
            return
        
        try:
            self._scheduler.shutdown(wait=False)
            self._running = False
            logger.info("Scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")
    
    def get_next_run(self) -> Optional[str]:
        """Get ISO 8601 timestamp of next scheduled run"""
        try:
            jobs = self._scheduler.get_jobs()
            if not jobs:
                return None
            
            next_runs = [job.next_run_time for job in jobs if job.next_run_time]
            if not next_runs:
                return None
            
            next_run = min(next_runs)
            return next_run.isoformat()
            
        except Exception as e:
            logger.error(f"Error getting next run: {e}")
            return None
    
    def is_running(self) -> bool:
        """Check if scheduler is running"""
        return self._running
    
    def get_status(self) -> dict:
        """Get scheduler status"""
        return {
            "running": self._running,
            "mode": self._mode,
            "next_run": self.get_next_run()
        }
