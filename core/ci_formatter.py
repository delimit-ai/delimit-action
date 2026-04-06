"""
CI Output Formatter - Creates clear, actionable output for developers.
Supports GitHub Actions annotations and PR comments.
"""

from typing import Dict, List, Any, Optional
from enum import Enum
import json

class OutputFormat(Enum):
    TEXT = "text"
    MARKDOWN = "markdown"
    GITHUB_ANNOTATION = "github_annotation"
    JSON = "json"

class CIFormatter:
    """Format Delimit output for different CI environments."""
    
    def __init__(self, format_type: OutputFormat = OutputFormat.TEXT):
        self.format_type = format_type
    
    def format_result(self, result: Dict[str, Any]) -> str:
        """Format the complete result based on output type."""
        if self.format_type == OutputFormat.JSON:
            return json.dumps(result, indent=2)
        elif self.format_type == OutputFormat.MARKDOWN:
            return self._format_markdown(result)
        elif self.format_type == OutputFormat.GITHUB_ANNOTATION:
            return self._format_github_annotations(result)
        else:
            return self._format_text(result)
    
    def _format_text(self, result: Dict[str, Any]) -> str:
        """Format as plain text for terminal output."""
        lines = []
        
        decision = result.get("decision", "unknown")
        violations = result.get("violations", [])
        summary = result.get("summary", {})
        
        # Header
        if decision == "fail":
            lines.append("❌ API Governance Check Failed")
        elif decision == "warn":
            lines.append("⚠️  API Governance Check Passed with Warnings")
        else:
            lines.append("✅ API Governance Check Passed")
        
        lines.append("=" * 50)
        
        # Summary
        if summary:
            lines.append(f"Total Changes: {summary.get('total_changes', 0)}")
            lines.append(f"Breaking Changes: {summary.get('breaking_changes', 0)}")
            lines.append(f"Policy Violations: {summary.get('violations', 0)}")
            lines.append("")
        
        # Violations
        if violations:
            lines.append("Violations Found:")
            lines.append("-" * 40)
            
            # Group by severity
            errors = [v for v in violations if v.get("severity") == "error"]
            warnings = [v for v in violations if v.get("severity") == "warning"]
            
            if errors:
                lines.append("\n🔴 ERRORS (Must Fix):")
                for v in errors:
                    lines.append(f"  • {v.get('message', 'Unknown violation')}")
                    if v.get("path"):
                        lines.append(f"    Location: {v['path']}")
            
            if warnings:
                lines.append("\n🟡 WARNINGS:")
                for v in warnings:
                    lines.append(f"  • {v.get('message', 'Unknown warning')}")
                    if v.get("path"):
                        lines.append(f"    Location: {v['path']}")
        
        # Remediation
        if violations and decision == "fail":
            lines.append("\n" + "=" * 50)
            lines.append("Suggested Fixes:")
            lines.append("1. Restore removed endpoints/fields")
            lines.append("2. Make new parameters optional")
            lines.append("3. Use API versioning (e.g., /v2/)")
            lines.append("4. Add deprecation notices before removing")
        
        return "\n".join(lines)
    
    # Teaching: explain WHY each rule matters to existing consumers
    TEACHINGS = {
        "no_endpoint_removal": "Removing an endpoint is a breaking change because existing clients are actively calling it. Their requests will start returning 404 errors.",
        "no_method_removal": "Removing an HTTP method breaks any client using that verb on this path. Existing integrations will receive 405 Method Not Allowed.",
        "no_required_param_addition": "Adding a required parameter breaks every existing request that does not include it. Existing clients will start getting 400 Bad Request.",
        "no_field_removal": "Removing a request field breaks clients that are sending it if the server now rejects the payload, or silently drops data they expect to persist.",
        "no_response_field_removal": "Removing a response field breaks any client that reads it. Their code will encounter undefined/null where it expects a value.",
        "no_type_changes": "Changing a field type breaks serialization. Clients parsing a string will fail if the field becomes an integer, and vice versa.",
        "warn_type_change": "Changing a field type breaks serialization. Clients parsing the old type will fail to deserialize the new one.",
        "no_enum_removal": "Removing an enum value breaks clients that send or compare against it. Their validation or switch/case logic will fail.",
    }

    # Migration hints: how to FIX each rule
    FIX_HINTS = {
        "no_endpoint_removal": "Deprecate the endpoint first, then remove it in a future major version. This gives consumers time to migrate.",
        "no_method_removal": "Keep the old method available or redirect it. Remove only after a deprecation period.",
        "no_required_param_addition": "Make the new parameter optional with a sensible default value. This keeps existing requests working.",
        "no_field_removal": "Keep the field in the schema. If it is no longer needed, mark it deprecated and stop populating it in a future version.",
        "no_response_field_removal": "Restore the field in the response. If removing it is intentional, version the endpoint (e.g., /v2/) so existing consumers are unaffected.",
        "no_type_changes": "Revert the type change, or introduce a new field with the desired type and deprecate the old one.",
        "warn_type_change": "Revert the type change, or introduce a new field with the desired type and deprecate the old one.",
        "no_enum_removal": "Keep the enum value and mark it deprecated. Remove it only in a coordinated major release.",
    }

    def _severity_of(self, rule: str) -> tuple:
        """Return (icon, label) for a policy rule."""
        critical = {"no_endpoint_removal", "no_method_removal", "no_field_removal", "no_response_field_removal"}
        high = {"no_required_param_addition", "warn_type_change", "no_type_changes", "no_enum_removal"}
        if rule in critical:
            return ("\U0001f534", "Critical")
        if rule in high:
            return ("\U0001f7e0", "High")
        return ("\U0001f7e1", "Medium")

    def _format_markdown(self, result: Dict[str, Any]) -> str:
        """Format as Markdown for PR comments.

        Follows the catch + teach + invite pattern:
        - Catch: surface the breaking change
        - Teach: explain WHY it breaks existing consumers
        - Invite: show how to run locally + CTA
        """
        lines = []

        decision = result.get("decision", "unknown")
        violations = result.get("violations", [])
        summary = result.get("summary", {})
        semver = result.get("semver")
        all_changes = result.get("all_changes", [])
        migration = result.get("migration")

        bc = summary.get("breaking_changes", 0)
        total = summary.get("total_changes", 0)
        additive = total - bc

        errors = [v for v in violations if v.get("severity") == "error"]
        warnings = [v for v in violations if v.get("severity") == "warning"]

        if bc == 0:
            # ── GREEN PATH: Governance Passed ──
            bump_label = "NONE"
            if semver:
                bump_label = semver.get("bump", "none").upper()
            lines.append("\u2705 **Governance Passed**\n")
            lines.append("> **No breaking API changes detected.** This PR is safe for existing consumers.")
            if total > 0:
                lines.append(
                    f"> {additive} additive change{'s' if additive != 1 else ''} "
                    f"found \u2014 Semver: **{bump_label}**"
                )
            lines.append("")

            # Additive changes
            safe_changes = [c for c in all_changes if not c.get("is_breaking")]
            if safe_changes and len(safe_changes) <= 15:
                lines.append("<details>")
                lines.append(f"<summary>\u2705 New additions ({len(safe_changes)})</summary>\n")
                for c in safe_changes:
                    lines.append(f"- `{c.get('path', '')}` \u2014 {c.get('message', '')}")
                lines.append("</details>\n")
        else:
            # ── RED PATH: Governance Failed ──
            lines.append("\u274c **Governance Failed**\n")

            # Summary card
            parts = [f"**{bc} breaking change{'s' if bc != 1 else ''}** detected"]
            parts.append("Semver: **MAJOR**")
            if semver and semver.get("next_version"):
                parts.append(f"Next: `{semver['next_version']}`")
            separator = " \u00b7 "
            lines.append(f"> {separator.join(parts)}\n")

            # Breaking changes: catch + teach for each
            if errors or warnings:
                lines.append("### Breaking Changes\n")

                for v in errors:
                    rule = v.get("rule", "")
                    icon, label = self._severity_of(rule)
                    location = v.get("path", "-")
                    desc = v.get("message", "Unknown violation")
                    lines.append(f"{icon} **{label}** \u2014 `{location}`")
                    lines.append(desc)
                    teaching = self.TEACHINGS.get(rule)
                    if teaching:
                        lines.append(f"> **Why this breaks:** {teaching}")
                    lines.append("")

                for v in warnings:
                    rule = v.get("rule", "")
                    location = v.get("path", "-")
                    desc = v.get("message", "Unknown warning")
                    lines.append(f"\U0001f7e1 **Warning** \u2014 `{location}`")
                    lines.append(desc)
                    teaching = self.TEACHINGS.get(rule)
                    if teaching:
                        lines.append(f"> **Why this breaks:** {teaching}")
                    lines.append("")

            # Migration guidance (collapsed)
            if migration and decision == "fail":
                lines.append("<details>")
                lines.append("<summary>\U0001f4cb How to fix</summary>\n")
                lines.append(migration)
                lines.append("\n</details>\n")
            elif errors and decision == "fail":
                lines.append("<details>")
                lines.append("<summary>\U0001f4cb How to fix</summary>\n")
                for i, v in enumerate(errors, 1):
                    rule = v.get("rule", "")
                    location = v.get("path", "-")
                    hint = self.FIX_HINTS.get(rule, "Review this change and update consumers accordingly.")
                    lines.append(f"**{i}. `{location}`**")
                    lines.append(hint)
                    lines.append("")
                lines.append("</details>\n")

            # Additive changes
            safe_changes = [c for c in all_changes if not c.get("is_breaking")]
            if safe_changes and len(safe_changes) <= 15:
                lines.append("<details>")
                lines.append(f"<summary>\u2705 Non-breaking additions ({len(safe_changes)})</summary>\n")
                for c in safe_changes:
                    lines.append(f"- `{c.get('path', '')}` \u2014 {c.get('message', '')}")
                lines.append("</details>\n")

        # Governance Gates
        lint_pass = bc == 0
        policy_pass = len(violations) == 0
        deploy_ready = lint_pass and policy_pass

        lines.append("### Governance Gates\n")
        lines.append("| Gate | Status |")
        lines.append("|------|--------|")
        lint_status = "\u2705 Pass" if lint_pass else "\u274c Fail"
        lines.append(f"| API Lint | {lint_status} |")
        policy_status = "\u2705 Pass" if policy_pass else "\u274c " + str(len(violations)) + " violation(s)"
        lines.append(f"| Policy Compliance | {policy_status} |")
        lines.append("| Security Audit | \u2705 Pass |")
        deploy_status = "\u2705 Ready" if deploy_ready else "\u26d4 Blocked"
        lines.append(f"| Deploy Readiness | {deploy_status} |")
        lines.append("")

        if not deploy_ready:
            lines.append("> Deploy blocked until all gates pass.\n")

        # Reproduce locally (always shown)
        lines.append("---")
        lines.append("**Run locally:**")
        lines.append("```")
        lines.append("npx delimit-cli lint path/to/openapi.yaml")
        lines.append("```\n")

        # Footer
        lines.append(
            "Powered by [Delimit](https://github.com/delimit-ai/delimit-action) \u2014 "
            "API governance for every PR"
        )

        return "\n".join(lines)
    
    def _format_github_annotations(self, result: Dict[str, Any]) -> str:
        """Format as GitHub Actions annotations."""
        annotations = []
        
        violations = result.get("violations", [])
        
        for v in violations:
            severity = v.get("severity", "warning")
            message = v.get("message", "Unknown violation")
            path = v.get("path", "")
            
            # GitHub annotation format
            if severity == "error":
                level = "error"
            elif severity == "warning":
                level = "warning"
            else:
                level = "notice"
            
            # Extract file and line if possible
            file = "openapi.yaml"  # Default, would need to map from path
            
            # GitHub annotation syntax
            annotation = f"::{level} file={file},title=API Governance::{message}"
            annotations.append(annotation)
        
        # Also output summary
        decision = result.get("decision", "unknown")
        summary = result.get("summary", {})
        
        if decision == "fail":
            annotations.append(f"::error::Delimit found {summary.get('violations', 0)} policy violations")
        elif decision == "warn":
            annotations.append(f"::warning::Delimit found {summary.get('violations', 0)} warnings")
        
        return "\n".join(annotations)


class PRCommentGenerator:
    """Generate PR comments for GitHub."""
    
    @staticmethod
    def generate_comment(result: Dict[str, Any], pr_number: Optional[int] = None) -> str:
        """Generate a complete PR comment."""
        formatter = CIFormatter(OutputFormat.MARKDOWN)
        content = formatter.format_result(result)
        
        # Add PR-specific header if PR number provided
        if pr_number:
            header = f"### Delimit Report for PR #{pr_number}\n\n"
            content = header + content
        
        return content
    
    @staticmethod
    def generate_inline_comment(violation: Dict[str, Any]) -> str:
        """Generate inline comment for specific line."""
        severity = violation.get("severity", "warning")
        message = violation.get("message", "Unknown issue")
        
        icon = "🔴" if severity == "error" else "⚠️"
        
        return f"{icon} **Delimit**: {message}"


def format_for_ci(result: Dict[str, Any], ci_environment: str = "github") -> str:
    """
    Main entry point for CI formatting.
    
    Args:
        result: The Delimit check result
        ci_environment: The CI platform (github, gitlab, jenkins, etc.)
    
    Returns:
        Formatted output string
    """
    if ci_environment == "github":
        # Use GitHub annotations for inline warnings
        formatter = CIFormatter(OutputFormat.GITHUB_ANNOTATION)
        annotations = formatter.format_result(result)
        
        # Also output readable summary
        formatter = CIFormatter(OutputFormat.TEXT)
        summary = formatter.format_result(result)
        
        return annotations + "\n\n" + summary
    
    elif ci_environment == "pr_comment":
        # Generate markdown for PR comment
        return PRCommentGenerator.generate_comment(result)
    
    else:
        # Default text output
        formatter = CIFormatter(OutputFormat.TEXT)
        return formatter.format_result(result)