"""
Strict Request schemas for Delimit Gateway V12 - Pydantic v2
Fixed for Pydantic v2 compatibility
"""

from typing import List, Optional, Dict, Literal
from pydantic import BaseModel, Field, field_validator
from pathlib import Path


class BaseTaskRequest(BaseModel):
    """Base request for all tasks"""
    task: str = Field(..., description="Task identifier")
    version: Optional[str] = Field(None, description="Explicit task version")
    correlation_id: Optional[str] = Field(None, description="Request tracking ID")
    
    model_config = {"extra": "forbid"}  # Pydantic v2 config


class ValidateAPIRequest(BaseTaskRequest):
    """Request for validate-api task"""
    task: Literal["validate-api"] = "validate-api"
    old_spec: str = Field(..., description="Path to old API specification")
    new_spec: str = Field(..., description="Path to new API specification")
    
    @field_validator("old_spec", "new_spec")
    @classmethod
    def validate_file_exists(cls, v: str) -> str:
        if not Path(v).exists():
            raise ValueError(f"File not found: {v}")
        return v


class CheckPolicyRequest(BaseTaskRequest):
    """Request for check-policy task"""
    task: Literal["check-policy"] = "check-policy"
    spec_files: List[str] = Field(..., min_length=1, description="API spec files to check")
    policy_file: Optional[str] = Field(None, description="Path to policy file")
    policy_inline: Optional[Dict[str, Dict]] = Field(None, description="Inline policy definition")
    
    @field_validator("spec_files")
    @classmethod
    def validate_spec_files(cls, v: List[str]) -> List[str]:
        for file in v:
            if not Path(file).exists():
                raise ValueError(f"File not found: {file}")
        return v
    
    @field_validator("policy_file")
    @classmethod
    def validate_policy_file(cls, v: Optional[str]) -> Optional[str]:
        if v and not Path(v).exists():
            raise ValueError(f"Policy file not found: {v}")
        return v


class ExplainDiffRequest(BaseTaskRequest):
    """Request for explain-diff task"""
    task: Literal["explain-diff"] = "explain-diff"
    old_spec: str = Field(..., description="Path to old API specification")
    new_spec: str = Field(..., description="Path to new API specification")
    detail_level: Literal["summary", "medium", "detailed"] = Field(
        "medium", 
        description="Level of detail in explanation"
    )
    
    @field_validator("old_spec", "new_spec")
    @classmethod
    def validate_file_exists(cls, v: str) -> str:
        if not Path(v).exists():
            raise ValueError(f"File not found: {v}")
        return v


# Union type for all requests
from typing import Union

TaskRequest = Union[ValidateAPIRequest, CheckPolicyRequest, ExplainDiffRequest]