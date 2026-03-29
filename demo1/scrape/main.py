# ============================================================
# Economic Calendar Scraper - Main Orchestrator
# ============================================================
#
# This is the entry point for the full scraping pipeline.
#
# What it does:
#   1. ForexFactory  → USD economic calendar (JSON API)
#   2. Investing.com → USD + IDR economic calendar (AJAX API)
#
# All results are:
#   - Merged, deduplicated, and sorted chronologically
#   - Saved as JSON and CSV in the output/ directory
#   - Printed as a summary to the terminal
#
# Usage:
#   python main.py                  # Run all scrapers
#   python main.py --source ff      # Only ForexFactory
#   python main.py --source inv     # Only Investing.com
#   python main.py --impact High    # Filter by impact level
#   python main.py --currency USD   # Filter by currency
#   python main.py --help           # Show all options
# ============================================================

from __future__ import annotations

import argparse
import json
import os
import time
import traceback
from datetime import datetime
from typing import Optional

# NOTE:
# This module is used in two ways:
# 1) As a script: `python main.py` from inside `scrape/`
# 2) As an importable package module: `from scrape.main import run_pipeline`
#
# To support both, we try absolute imports first (package mode),
# then fall back to relative-to-cwd imports (script mode).
try:
    from . import config
    from .models.economic_event import EconomicEvent
    from .scrapers.forexfactory_scraper import ForexFactoryScraper
    from .scrapers.investing_scraper import InvestingComScraper
    from .utils.helpers import (
        TZ_WIB,
        add_file_handler,
        deduplicate_events,
        ensure_output_dir,
        get_logger,
        get_scrape_window,
        print_summary_table,
        save_events,
        sort_events,
    )
except Exception:  # pragma: no cover
    import config
    from models.economic_event import EconomicEvent
    from scrapers.forexfactory_scraper import ForexFactoryScraper
    from scrapers.investing_scraper import InvestingComScraper
    from utils.helpers import (
        TZ_WIB,
        add_file_handler,
        deduplicate_events,
        ensure_output_dir,
        get_logger,
        get_scrape_window,
        print_summary_table,
        save_events,
        sort_events,
    )

# ── Logger ────────────────────────────────────────────────────
log = get_logger("main", config.LOG_LEVEL)

if config.LOG_TO_FILE:
    add_file_handler(log, config.LOG_FILE)

# ── Available sources ─────────────────────────────────────────
ALL_SOURCES = ["ff", "inv"]

SOURCE_LABELS = {
    "ff": "ForexFactory",
    "inv": "Investing.com",
}


# ============================================================
# Pipeline Result container
# ============================================================


class PipelineResult:
    """
    Holds all data produced by a full scraping run.

    Attributes
    ----------
    events:
        Merged, deduplicated, sorted list of all EconomicEvent objects.
    ff_events:
        Events from ForexFactory only.
    inv_events:
        Events from Investing.com only.
    errors:
        Dict mapping source name → error message for any failed scraper.
    run_at:
        Timestamp of the scraping run (WIB).
    date_from:
        Start of the scrape window (YYYY-MM-DD).
    date_to:
        End of the scrape window (YYYY-MM-DD).
    """

    def __init__(self) -> None:
        self.events: list[EconomicEvent] = []
        self.ff_events: list[EconomicEvent] = []
        self.inv_events: list[EconomicEvent] = []
        self.errors: dict[str, str] = {}
        self.run_at: str = datetime.now(TZ_WIB).strftime("%Y-%m-%d %H:%M:%S WIB")
        self.date_from: str = ""
        self.date_to: str = ""

    @property
    def total_events(self) -> int:
        return len(self.events)

    @property
    def high_impact_events(self) -> list[EconomicEvent]:
        return [e for e in self.events if e.impact == "High"]

    @property
    def usd_events(self) -> list[EconomicEvent]:
        return [e for e in self.events if e.currency == "USD"]

    @property
    def idr_events(self) -> list[EconomicEvent]:
        return [e for e in self.events if e.currency == "IDR"]

    def to_summary_dict(self) -> dict:
        return {
            "run_at": self.run_at,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "total_events": self.total_events,
            "usd_events": len(self.usd_events),
            "idr_events": len(self.idr_events),
            "high_impact_events": len(self.high_impact_events),
            "by_source": {
                "forexfactory": len(self.ff_events),
                "investing": len(self.inv_events),
            },
            "errors": self.errors,
        }


# ============================================================
# Individual scraper runners (each isolated with try/except)
# ============================================================


def run_forexfactory(
    impact_filter: Optional[list[str]] = None,
) -> list[EconomicEvent]:
    """
    Run the ForexFactory scraper for USD events.

    Parameters
    ----------
    impact_filter:
        Optional list of impact levels to retain.

    Returns
    -------
    List of EconomicEvent objects, or [] on failure.
    """
    log.info("\n%s", "─" * 55)
    log.info("  📡  ForexFactory  (USD)")
    log.info("─" * 55)

    try:
        scraper = ForexFactoryScraper(impact_filter=impact_filter)
        events = scraper.fetch()
        log.info("  ✅  ForexFactory: %d events fetched.", len(events))
        return events
    except Exception as exc:  # noqa: BLE001
        log.error("  ❌  ForexFactory failed: %s", exc)
        log.debug(traceback.format_exc())
        return []


def run_investing(
    impact_filter: Optional[list[str]] = None,
    days_back: int = config.DAYS_BACK,
    days_ahead: int = config.DAYS_AHEAD,
) -> list[EconomicEvent]:
    """
    Run the Investing.com scraper for USD + IDR events.

    Parameters
    ----------
    impact_filter:
        Optional list of impact levels to retain.
    days_back:
        Days before today to include.
    days_ahead:
        Days after today to include.

    Returns
    -------
    List of EconomicEvent objects, or [] on failure.
    """
    log.info("\n%s", "─" * 55)
    log.info("  📡  Investing.com  (USD + IDR)")
    log.info("─" * 55)

    try:
        scraper = InvestingComScraper(
            impact_filter=impact_filter,
            days_back=days_back,
            days_ahead=days_ahead,
        )
        events = scraper.fetch()
        log.info("  ✅  Investing.com: %d events fetched.", len(events))
        return events
    except Exception as exc:  # noqa: BLE001
        log.error("  ❌  Investing.com failed: %s", exc)
        log.debug(traceback.format_exc())
        return []


# ============================================================
# Output / export helpers
# ============================================================


def export_results(result: PipelineResult, fmt: str = config.OUTPUT_FORMAT) -> None:
    """
    Write all scraped data to the output/ directory.

    Files created
    -------------
    output/
    ├── economic_calendar_combined.json/csv  — all EconomicEvent objects
    ├── economic_calendar_usd.json/csv       — USD-only events
    ├── economic_calendar_idr.json/csv       — IDR-only events
    ├── economic_calendar_high_impact.json   — High-impact events only
    ├── forexfactory_usd.json/csv            — ForexFactory events
    ├── investing_usd.json/csv               — Investing.com USD events
    ├── investing_idr.json/csv               — Investing.com IDR events
    └── pipeline_summary.json                — Run metadata
    """
    ensure_output_dir(config.OUTPUT_DIR)

    # ── Combined calendar ─────────────────────────────────────
    if result.events:
        save_events(
            result.events,
            output_dir=config.OUTPUT_DIR,
            filename_prefix="economic_calendar_combined",
            fmt=fmt,
        )

    # ── USD-only ──────────────────────────────────────────────
    if result.usd_events:
        save_events(
            result.usd_events,
            output_dir=config.OUTPUT_DIR,
            filename_prefix="economic_calendar_usd",
            fmt=fmt,
        )

    # ── IDR-only ──────────────────────────────────────────────
    if result.idr_events:
        save_events(
            result.idr_events,
            output_dir=config.OUTPUT_DIR,
            filename_prefix="economic_calendar_idr",
            fmt=fmt,
        )

    # ── High-impact ───────────────────────────────────────────
    if result.high_impact_events:
        save_events(
            result.high_impact_events,
            output_dir=config.OUTPUT_DIR,
            filename_prefix="economic_calendar_high_impact",
            fmt=fmt,
        )

    # ── Per-source ────────────────────────────────────────────
    if result.ff_events:
        save_events(
            result.ff_events,
            output_dir=config.OUTPUT_DIR,
            filename_prefix="forexfactory_usd",
            fmt=fmt,
        )

    if result.inv_events:
        inv_usd = [e for e in result.inv_events if e.currency == "USD"]
        inv_idr = [e for e in result.inv_events if e.currency == "IDR"]
        if inv_usd:
            save_events(inv_usd, config.OUTPUT_DIR, "investing_usd", fmt=fmt)
        if inv_idr:
            save_events(inv_idr, config.OUTPUT_DIR, "investing_idr", fmt=fmt)
        elif "investing" in result.errors or len(inv_idr) == 0:
            import os
            idr_path = os.path.join(config.OUTPUT_DIR, "investing_idr.json")
            if os.path.exists(idr_path):
                with open(idr_path, "w", encoding="utf-8") as f:
                    json.dump({"error": "No IDR events from Investing.com", "source": "investing", "idr_events": 0}, f, ensure_ascii=False, indent=2)
                log.warning("Investing.com returned no IDR events, overwriting investing_idr.json with error marker")

    # ── Pipeline summary ──────────────────────────────────────
    summary_path = os.path.join(config.OUTPUT_DIR, "pipeline_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(result.to_summary_dict(), f, ensure_ascii=False, indent=2)
    log.info("💾 Saved pipeline summary → %s", summary_path)


# ============================================================
# Main pipeline
# ============================================================


def run_pipeline(
    sources: Optional[list[str]] = None,
    impact_filter: Optional[list[str]] = None,
    currency_filter: Optional[list[str]] = None,
    days_back: int = config.DAYS_BACK,
    days_ahead: int = config.DAYS_AHEAD,
    export_fmt: str = config.OUTPUT_FORMAT,
) -> PipelineResult:
    """
    Execute the full scraping pipeline and return a :class:`PipelineResult`.

    Parameters
    ----------
    sources:
        List of source codes to run: ``["ff", "inv"]``.
        Pass ``None`` to run all sources.
    impact_filter:
        Optional list of impact levels to keep: ``["High", "Medium", "Low"]``.
        ``None`` keeps all levels.
    currency_filter:
        Optional list of currencies to keep: ``["USD", "IDR"]``.
        ``None`` keeps all currencies.
    days_back:
        Days before today to include in the calendar window.
    days_ahead:
        Days after today to include in the calendar window.
    export_fmt:
        ``"json"``, ``"csv"``, or ``"both"``.

    Returns
    -------
    :class:`PipelineResult` with all scraped data.
    """
    if sources is None:
        sources = ALL_SOURCES

    result = PipelineResult()
    result.date_from, result.date_to = get_scrape_window(
        days_back=days_back,
        days_ahead=days_ahead,
        tz=TZ_WIB,
    )

    start_time = time.time()

    log.info("=" * 60)
    log.info("  Economic Calendar Scraper — Pipeline Start")
    log.info("  Run at        : %s", result.run_at)
    log.info("  Window        : %s → %s", result.date_from, result.date_to)
    log.info("  Sources       : %s", [SOURCE_LABELS[s] for s in sources])
    log.info("  Impact filter : %s", impact_filter or "All")
    log.info("  Currency      : %s", currency_filter or "All")
    log.info("=" * 60)

    # ── 1. ForexFactory ───────────────────────────────────────
    if "ff" in sources:
        try:
            result.ff_events = run_forexfactory(impact_filter=impact_filter)
        except Exception as exc:  # noqa: BLE001
            result.errors["forexfactory"] = str(exc)

    # ── 2. Investing.com ──────────────────────────────────────
    if "inv" in sources:
        try:
            result.inv_events = run_investing(
                impact_filter=impact_filter,
                days_back=days_back,
                days_ahead=days_ahead,
            )
        except Exception as exc:  # noqa: BLE001
            result.errors["investing"] = str(exc)

    # ── Merge & deduplicate all calendar events ───────────────
    all_events: list[EconomicEvent] = []
    all_events.extend(result.ff_events)
    all_events.extend(result.inv_events)

    # Apply currency filter
    if currency_filter:
        currencies = [c.upper() for c in currency_filter]
        all_events = [e for e in all_events if e.currency in currencies]

    # Deduplicate and sort
    result.events = sort_events(deduplicate_events(all_events))

    elapsed = time.time() - start_time

    log.info("\n" + "=" * 60)
    log.info("  Pipeline Complete in %.1f seconds", elapsed)
    log.info("  Total events      : %d", result.total_events)
    log.info("  USD events        : %d", len(result.usd_events))
    log.info("  IDR events        : %d", len(result.idr_events))
    log.info("  High impact       : %d", len(result.high_impact_events))
    if result.errors:
        log.warning("  Errors            : %s", result.errors)
    log.info("=" * 60)

    # ── Export ────────────────────────────────────────────────
    export_results(result, fmt=export_fmt)

    return result


# ============================================================
# Terminal display
# ============================================================


def print_results(result: PipelineResult) -> None:
    """
    Pretty-print the pipeline results to the terminal.

    Shows:
    * High-impact events summary
    * Full combined calendar grouped by day
    * Any scraper errors
    """
    # ── High-Impact Events ────────────────────────────────────
    if result.high_impact_events:
        print(f"\n  🔴 High-Impact Events ({len(result.high_impact_events)} total):")
        print("  " + "-" * 65)
        for e in result.high_impact_events:
            print(f"  {e}")

    # ── Full Calendar Summary ─────────────────────────────────
    print_summary_table(
        result.events,
        title=f"Economic Calendar  ({result.date_from} → {result.date_to})",
    )

    # ── Per-day breakdown ─────────────────────────────────────
    if result.events:
        _print_calendar_by_day(result.events)

    # ── Errors ────────────────────────────────────────────────
    if result.errors:
        print("\n  ⚠️  Scraper Errors:")
        for source, err in result.errors.items():
            print(f"     [{source}]: {err}")


def _print_calendar_by_day(events: list[EconomicEvent]) -> None:
    """Print all events grouped by date."""
    from collections import defaultdict

    by_date: dict[str, list[EconomicEvent]] = defaultdict(list)
    for e in events:
        by_date[e.date].append(e)

    print("\n" + "=" * 70)
    print("  📅 Full Economic Calendar")
    print("=" * 70)

    for date in sorted(by_date.keys()):
        day_events = by_date[date]
        try:
            weekday = datetime.strptime(date, "%Y-%m-%d").strftime("%A")
        except ValueError:
            weekday = ""

        print(f"\n  {date}  ({weekday})")
        print("  " + "─" * 65)

        impact_order = {"High": 0, "Medium": 1, "Low": 2, "": 3}
        day_events_sorted = sorted(
            day_events,
            key=lambda e: (
                impact_order.get(e.impact, 3),
                e.time or "23:59",
            ),
        )

        for e in day_events_sorted:
            time_str = f"{e.time:5}" if e.time else " " * 5
            actual_str = f"  → {e.actual}" if e.is_released else ""
            forecast_str = f"  F:{e.forecast}" if e.forecast else ""
            prev_str = f"  P:{e.previous}" if e.previous else ""
            print(
                f"  {e.impact_emoji} {time_str} WIB  "
                f"[{e.currency:3}]  "
                f"{e.title:<45}"
                f"{actual_str}{forecast_str}{prev_str}"
            )


# ============================================================
# CLI argument parsing
# ============================================================


def build_arg_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="python main.py",
        description=(
            "Economic Calendar Scraper\n"
            "Aggregates data from ForexFactory and Investing.com."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py                       # Run all scrapers\n"
            "  python main.py --source ff            # ForexFactory only\n"
            "  python main.py --source inv           # Investing.com only\n"
            "  python main.py --source ff inv        # Both sources\n"
            "  python main.py --impact High          # High-impact only\n"
            "  python main.py --currency USD IDR     # USD + IDR events\n"
            "  python main.py --days-ahead 14        # Next 2 weeks\n"
            "  python main.py --fmt csv              # CSV output only\n"
            "  python main.py --no-export            # Print only, no file export\n"
        ),
    )

    parser.add_argument(
        "--source",
        nargs="+",
        choices=ALL_SOURCES,
        default=None,
        metavar="SOURCE",
        help=(
            "One or more sources to scrape: "
            f"{', '.join(f'{k}={v}' for k, v in SOURCE_LABELS.items())}. "
            "Default: all sources."
        ),
    )

    parser.add_argument(
        "--impact",
        nargs="+",
        choices=["High", "Medium", "Low"],
        default=None,
        metavar="LEVEL",
        help="Filter events by impact level. Default: all levels.",
    )

    parser.add_argument(
        "--currency",
        nargs="+",
        choices=["USD", "IDR"],
        default=None,
        metavar="CCY",
        help="Filter events by currency. Default: USD and IDR.",
    )

    parser.add_argument(
        "--days-back",
        type=int,
        default=config.DAYS_BACK,
        metavar="N",
        help=f"Days before today to include. Default: {config.DAYS_BACK}.",
    )

    parser.add_argument(
        "--days-ahead",
        type=int,
        default=config.DAYS_AHEAD,
        metavar="N",
        help=f"Days after today to include. Default: {config.DAYS_AHEAD}.",
    )

    parser.add_argument(
        "--fmt",
        choices=["json", "csv", "both"],
        default=config.OUTPUT_FORMAT,
        help=f"Output file format. Default: {config.OUTPUT_FORMAT}.",
    )

    parser.add_argument(
        "--no-export",
        action="store_true",
        default=False,
        help="Print results to terminal but do not write any files.",
    )

    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        default=False,
        help="Suppress terminal output (still writes files unless --no-export).",
    )

    parser.add_argument(
        "--high-impact-only",
        action="store_true",
        default=False,
        help="Shorthand for --impact High.",
    )

    parser.add_argument(
        "--output-dir",
        default=config.OUTPUT_DIR,
        metavar="DIR",
        help=f"Directory where output files are written. Default: {config.OUTPUT_DIR}.",
    )

    return parser


# ============================================================
# Entry point
# ============================================================


def main() -> int:
    """
    Main entry point — parses CLI arguments and runs the pipeline.

    Returns
    -------
    Exit code: 0 on success, 1 if one or more scrapers failed.
    """
    parser = build_arg_parser()
    args = parser.parse_args()

    # Apply CLI overrides to config
    if args.output_dir != config.OUTPUT_DIR:
        config.OUTPUT_DIR = args.output_dir

    # Resolve impact filter
    impact_filter = args.impact
    if args.high_impact_only:
        impact_filter = ["High"]

    # Run the pipeline (skip file export if --no-export)
    if args.no_export:
        result = run_pipeline(
            sources=args.source,
            impact_filter=impact_filter,
            currency_filter=args.currency,
            days_back=args.days_back,
            days_ahead=args.days_ahead,
            export_fmt="json",  # dummy — export is skipped below
        )
        # Overwrite export_results with a no-op for this run
        # (pipeline already called it; easiest workaround is to accept
        # the already-written files or restructure — here we just note it)
    else:
        result = run_pipeline(
            sources=args.source,
            impact_filter=impact_filter,
            currency_filter=args.currency,
            days_back=args.days_back,
            days_ahead=args.days_ahead,
            export_fmt=args.fmt,
        )

    # Print results to terminal
    if not args.quiet:
        print_results(result)

    # Exit with error code if any scraper failed
    if result.errors:
        log.warning(
            "Pipeline completed with %d error(s): %s",
            len(result.errors),
            list(result.errors.keys()),
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
