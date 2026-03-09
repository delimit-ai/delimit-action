from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class TaskStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"

class TaskRequest(BaseModel):
    task: str = Field(..., description="Task identifier (e.g., 'validate-api')")
    files: List[str] = Field(default_factory=list, description="List of file paths")
    config: Dict[str, Any] = Field(default_factory=dict, description="Task-specific configuration")
    correlation_id: Optional[str] = Field(None, description="Request tracking ID")
    version: str = Field("v1", description="Task version")

class ErrorDetails(BaseModel):
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error context")
    retryable: bool = Field(False, description="Whether the operation can be retried")

class TaskResponse(BaseModel):
    status: TaskStatus
    task: str
    result: Optional[Any] = None
    errors: List[ErrorDetails] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    duration_ms: Optional[int] = None
    correlation_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ErrorResponse(BaseModel):
    status: TaskStatus = TaskStatus.ERROR
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    available_tasks: Optional[List[str]] = None