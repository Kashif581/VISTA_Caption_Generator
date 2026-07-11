"""
schemas.py

Pydantic models for the hackathon I/O contract and the FastAPI demo API.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from config import STYLES


class Task(BaseModel):
    task_id: str
    video_url: str
    styles: List[str] = Field(default_factory=lambda: list(STYLES))


class TaskResult(BaseModel):
    task_id: str
    captions: Dict[str, str]


class CaptionRequest(BaseModel):
    video_url: str
    styles: Optional[List[str]] = None


class CaptionResponse(BaseModel):
    task_id: str
    captions: Dict[str, str]
