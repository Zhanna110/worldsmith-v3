from pydantic import BaseModel, Field
from typing import List, Optional


class A2ATask(BaseModel):
    """
    Represents a status update or sub-task within the agent's execution.
    """

    id: str = Field(..., description="Unique identifier for the task")
    status: str = Field(
        ..., description="Current status: pending, in_progress, completed, failed"
    )
    description: str = Field(..., description="Human-readable description of the task")


class A2AArtifact(BaseModel):
    """
    Represents a generated file or output artifact.
    """

    path: str = Field(..., description="Relative or absolute path to the artifact")
    type: str = Field(..., description="Type of artifact: file, diff, etc.")
    content: Optional[str] = Field(
        None, description="Content of the artifact if applicable"
    )


class AgentResponse(BaseModel):
    """
    Top-level response object compliant with Agent2Agent protocol.
    """

    thought_process: List[str] = Field(
        default_factory=list, description="Internal reasoning steps (hidden from user)"
    )
    tasks: List[A2ATask] = Field(
        default_factory=list, description="List of tasks and their statuses"
    )
    artifacts: List[A2AArtifact] = Field(
        default_factory=list, description="List of generated artifacts"
    )
