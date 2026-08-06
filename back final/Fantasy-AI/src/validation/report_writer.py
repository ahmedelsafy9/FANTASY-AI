"""Writer that renders a :class:`~src.validation.models.ValidationReport`
as a human-readable Markdown document.
"""

from __future__ import annotations

from pathlib import Path

from src.common.file_utils import ensure_directory
from src.config.logging_config import get_logger
from src.validation.models import ValidationReport

logger = get_logger(__name__)


def write_markdown_report(report: ValidationReport, report_path: Path) -> None:
    """Render a validation report as Markdown and write it to disk.

    Args:
        report: The report to render.
        report_path: Destination file path.
    """
    ensure_directory(report_path.parent)

    overall = "PASSED ✅" if report.overall_passed else "FAILED ❌"
    lines: list[str] = [
        "# Fantasy-AI — Dataset Validation Report",
        "",
        f"Generated: {report.generated_at.isoformat()}",
        f"Overall result: **{overall}**",
        "",
        "## Summary",
        "",
        f"- Rows validated: **{report.row_count}**",
        f"- Columns validated: **{report.column_count}**",
        f"- Checks run: **{len(report.results)}**",
        f"- Total issues found: **{report.total_issue_count}**",
        "",
        "## Check Results",
        "",
        "| Check | Result | Issues Found | Summary |",
        "|-------|--------|---------------|---------|",
    ]
    for result in report.results:
        status = "✅ Pass" if result.passed else "❌ Fail"
        lines.append(
            f"| {result.check_name} | {status} | {result.total_issue_count} | {result.summary} |"
        )

    lines += ["", "## Issue Details", ""]
    for result in report.results:
        if not result.issues:
            continue
        lines.append(f"### {result.check_name}")
        lines.append("")
        shown = len(result.issues)
        if result.total_issue_count > shown:
            lines.append(
                f"_Showing {shown} of {result.total_issue_count} issue(s)._"
            )
            lines.append("")
        lines.append("| Row | Column | Description |")
        lines.append("|-----|--------|-------------|")
        for issue in result.issues:
            row = issue.row_index if issue.row_index is not None else "-"
            column = issue.column if issue.column is not None else "-"
            lines.append(f"| {row} | {column} | {issue.description} |")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote validation report to %s.", report_path)
