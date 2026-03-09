"""
Strict Evidence Contract for Delimit Gateway V12
All tasks MUST return TaskEvidence structure
"""

from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from datetime import datetime


class Decision(str, Enum):
    """Task decision outcomes"""
    PASS = "pass"
    FAIL = "fail" 
    WARN = "warn"


class ViolationSeverity(str, Enum):
    """Violation severity levels"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Violation(BaseModel):
    """Structured violation information"""
    rule: str = Field(..., description="Rule identifier that was violated")
    severity: ViolationSeverity = Field(..., description="Severity of violation")
    path: Optional[str] = Field(None, description="API path or location of violation")
    message: str = Field(..., description="Human-readable violation message")
    details: Optional[Dict[str, str]] = Field(default_factory=dict, description="Additional context")


class Evidence(BaseModel):
    """Structured evidence for a specific check"""
    rule: str = Field(..., description="Rule that was checked")
    passed: bool = Field(..., description="Whether the rule check passed")
    details: Dict[str, str] = Field(default_factory=dict, description="Evidence details")


class Remediation(BaseModel):
    """Actionable remediation guidance"""
    summary: str = Field(..., description="Brief remediation summary")
    steps: List[str] = Field(default_factory=list, description="Step-by-step remediation")
    examples: Optional[List[str]] = Field(None, description="Example fixes")
    documentation: Optional[str] = Field(None, description="Link to documentation")


class TaskEvidence(BaseModel):
    """
    Strict Evidence Contract - ALL tasks must return this structure
    This is the shared contract between CLI, MCP, and GitHub Action
    """
    # Identity
    task: str = Field(..., description="Task name")
    task_version: str = Field(..., description="Task version (e.g., '1.0')")
    
    # Core decision
    decision: Decision = Field(..., description="Overall decision: pass, fail, or warn")
    exit_code: int = Field(..., description="Process exit code: 0=pass, 1=fail")
    
    # Violations and evidence
    violations: List[Violation] = Field(default_factory=list, description="List of violations found")
    evidence: List[Evidence] = Field(default_factory=list, description="Structured evidence collected")
    
    # Guidance
    remediation: Optional[Remediation] = Field(None, description="Remediation guidance if failed")
    
    # Metadata
    summary: str = Field(..., description="Human-readable summary")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Evidence timestamp")
    correlation_id: Optional[str] = Field(None, description="Request correlation ID")
    
    # Metrics
    metrics: Dict[str, int] = Field(default_factory=dict, description="Task-specific metrics")
    
    def model_post_init(self, __context):
        """Ensure exit_code aligns with decision"""
        if self.decision == Decision.FAIL and self.exit_code == 0:
            raise ValueError("Decision 'fail' must have non-zero exit_code")
        if self.decision == Decision.PASS and self.exit_code != 0:
            raise ValueError("Decision 'pass' must have exit_code 0")


# Task-specific evidence extensions

class APIChangeEvidence(TaskEvidence):
    """Evidence for validate-api task"""
    breaking_changes: List[Dict[str, str]] = Field(default_factory=list)
    non_breaking_changes: List[Dict[str, str]] = Field(default_factory=list)
    risk_score: int = Field(0, ge=0, le=100)


class PolicyComplianceEvidence(TaskEvidence):
    """Evidence for check-policy task"""
    compliance_score: int = Field(100, ge=0, le=100)
    policy_version: str = Field(..., description="Policy version applied")
    checks_performed: int = Field(0, description="Total checks performed")
    checks_passed: int = Field(0, description="Checks that passed")


class DiffExplanationEvidence(TaskEvidence):
    """Evidence for explain-diff task"""
    changes_summary: Dict[str, List[str]] = Field(default_factory=dict)
    migration_required: bool = Field(False)
    impact_level: str = Field("none", pattern="^(none|low|medium|high)$")