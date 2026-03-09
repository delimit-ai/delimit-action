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
    
    def _format_markdown(self, result: Dict[str, Any]) -> str:
        """Format as Markdown for PR comments."""
        lines = []
        
        decision = result.get("decision", "unknown")
        violations = result.get("violations", [])
        summary = result.get("summary", {})
        
        # Header
        if decision == "fail":
            lines.append("## 🚨 Delimit Found Breaking Changes\n")
        elif decision == "warn":
            lines.append("## ⚠️ Delimit Found Potential Issues\n")
        else:
            lines.append("## ✅ API Changes Look Good\n")
        
        # Summary table
        if summary.get("violations", 0) > 0:
            lines.append("### Summary\n")
            lines.append("| Metric | Count |")
            lines.append("|--------|-------|")
            lines.append(f"| Total Changes | {summary.get('total_changes', 0)} |")
            lines.append(f"| Breaking Changes | {summary.get('breaking_changes', 0)} |")
            lines.append(f"| Policy Violations | {summary.get('violations', 0)} |")
            lines.append("")
        
        # Violations table
        if violations:
            errors = [v for v in violations if v.get("severity") == "error"]
            warnings = [v for v in violations if v.get("severity") == "warning"]
            
            if errors or warnings:
                lines.append("### Violations\n")
                lines.append("| Severity | Rule | Description | Location |")
                lines.append("|----------|------|-------------|----------|")
                
                for v in errors:
                    severity = "🔴 **Error**"
                    rule = v.get("name", v.get("rule", "Unknown"))
                    desc = v.get("message", "Unknown violation")
                    location = v.get("path", "-")
                    lines.append(f"| {severity} | {rule} | {desc} | `{location}` |")
                
                for v in warnings:
                    severity = "🟡 Warning"
                    rule = v.get("name", v.get("rule", "Unknown"))
                    desc = v.get("message", "Unknown warning")
                    location = v.get("path", "-")
                    lines.append(f"| {severity} | {rule} | {desc} | `{location}` |")
                
                lines.append("")
        
        # Detailed changes
        all_changes = result.get("all_changes", [])
        if all_changes and len(all_changes) <= 10:
            lines.append("### All Changes\n")
            lines.append("<details>")
            lines.append("<summary>Click to expand</summary>\n")
            lines.append("```")
            for change in all_changes:
                breaking = "BREAKING" if change.get("is_breaking") else "safe"
                lines.append(f"[{breaking}] {change.get('message', 'Unknown change')}")
            lines.append("```")
            lines.append("</details>\n")
        
        # Remediation
        if violations and decision == "fail":
            lines.append("### 💡 How to Fix\n")
            lines.append("These changes will break existing API consumers. Consider:")
            lines.append("")
            lines.append("1. **Restore removed endpoints** - Keep them with deprecation notices")
            lines.append("2. **Make parameters optional** - Don't add required parameters")
            lines.append("3. **Use versioning** - Create `/v2/` endpoints for breaking changes")
            lines.append("4. **Gradual migration** - Provide migration guides and time")
            lines.append("")
            lines.append("---")
            lines.append("*Generated by [Delimit](https://github.com/delimit-ai/delimit) - API Governance for CI/CD*")
        
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