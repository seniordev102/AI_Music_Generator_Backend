#!/usr/bin/env python
"""
Script to run monthly credit allocations for yearly subscriptions.
This script is intended to be run as a cron job on the 1st of each month.

Usage:
    python scripts/run_monthly_allocations.py [--auto-fix] [--debug]

Options:
    --auto-fix    Enable automatic fixing of discrepancies
    --debug       Enable debug logging
"""

import argparse
import asyncio
import logging

# Add the project root to the Python path
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.api.credit_management.monthly_allocation.scheduler import (
    MonthlyAllocationScheduler,
)
from app.database import SessionLocal


async def run_allocations(auto_fix: bool = False, debug: bool = False):
    """Run the monthly allocation process."""
    # Ensure logs directory exists
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Configure logging
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                logs_dir
                / f"monthly_allocation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            ),
        ],
    )

    logger = logging.getLogger("monthly_allocation")
    logger.info(f"Starting monthly allocation process at {datetime.now(timezone.utc)}")
    logger.info(f"Auto-fix enabled: {auto_fix}")

    try:
        # Create a session directly
        session = SessionLocal()
        try:
            scheduler = MonthlyAllocationScheduler(session, auto_fix_enabled=auto_fix)
            results = await scheduler.run_monthly_allocations()

            # Update next allocation dates
            updated_next_dates = await scheduler.update_next_allocation_dates()
            results["updated_next_dates"] = updated_next_dates
            logger.info(
                f"Updated next allocation dates for {updated_next_dates} subscriptions"
            )

            # Log summary
            logger.info("Monthly allocation process completed")
            logger.info(f"Duration: {results['duration_seconds']:.2f} seconds")
            logger.info(
                f"Allocations: {results['allocations']['successful']} successful, "
                f"{results['allocations']['skipped']} skipped, "
                f"{results['allocations']['failed']} failed"
            )
            logger.info(
                f"Retries: {results['retries']['successful']} successful, "
                f"{results['retries']['scheduled']} scheduled, "
                f"{results['retries']['failed']} failed"
            )
            logger.info(
                f"Discrepancies: {results['discrepancies']['total']} detected, "
                f"{results['discrepancies']['fixed']} fixed"
            )

            return results
        finally:
            await session.close()

    except Exception as e:
        logger.error(f"Error running monthly allocations: {str(e)}", exc_info=True)
        raise


def main():
    """Parse arguments and run the allocation process."""
    parser = argparse.ArgumentParser(description="Run monthly credit allocations")
    parser.add_argument(
        "--auto-fix",
        action="store_true",
        help="Enable automatic fixing of discrepancies",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    try:
        results = asyncio.run(run_allocations(auto_fix=args.auto_fix, debug=args.debug))

        # Print summary to stdout
        print("\nMonthly Allocation Summary:")
        print(f"Duration: {results['duration_seconds']:.2f} seconds")
        print(
            f"Allocations: {results['allocations']['successful']} successful, "
            f"{results['allocations']['skipped']} skipped, "
            f"{results['allocations']['failed']} failed"
        )
        print(
            f"Retries: {results['retries']['successful']} successful, "
            f"{results['retries']['scheduled']} scheduled, "
            f"{results['retries']['failed']} failed"
        )
        print(
            f"Discrepancies: {results['discrepancies']['total']} detected, "
            f"{results['discrepancies']['fixed']} fixed"
        )
        print(
            f"Updated next allocation dates for {results['updated_next_dates']} subscriptions"
        )

        # Exit with success
        sys.exit(0)

    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
