
from enum import Enum
from pydantic import BaseModel, EmailStr, Field, JsonValue, model_validator, ConfigDict
from datetime import datetime
from decimal import Decimal


class UserRole(str, Enum):
    employer = "employer"
    candidate = "candidate"


class UserRegister(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    # Public Sprint 1 registration supports both defined account roles.
    role: UserRole = UserRole.candidate

class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class AssessmentDifficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class AssessmentStatus(str, Enum):
    draft = "draft"
    published = "published"
    closed = "closed"


class AssessmentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    difficulty: AssessmentDifficulty
    duration: int = Field(gt=0)


class AssessmentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    difficulty: AssessmentDifficulty | None = None
    duration: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_update_fields(self):
        if not self.model_fields_set:
            raise ValueError("At least one assessment field must be provided")
        for field in ("title", "difficulty", "duration"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class AssessmentResponse(BaseModel):
    id: int
    title: str
    description: str | None
    difficulty: AssessmentDifficulty
    duration: int
    created_by: int
    status: AssessmentStatus
    created_at: datetime


class SubmissionStatus(str, Enum):
    in_progress = "in_progress"
    submitted = "submitted"
    evaluated = "evaluated"


class SubmissionStart(BaseModel):
    assessment_id: int = Field(gt=0)


class SubmissionAnswersUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: dict[str, JsonValue]

    @model_validator(mode="after")
    def validate_answer_keys(self):
        if any(not key.strip() for key in self.answers):
            raise ValueError("Answer keys must contain a question or task ID")
        return self


class SubmissionResponse(BaseModel):
    id: int
    candidate_id: int
    assessment_id: int
    answers: dict[str, JsonValue]
    score: Decimal | None
    status: SubmissionStatus
    started_at: datetime
    submitted_at: datetime | None


class InvitationCreate(BaseModel):
    candidate_email: EmailStr = Field(max_length=254)


class InvitationCreatedResponse(BaseModel):
    id: int
    assessment_id: int
    candidate_email: EmailStr
    expires_at: datetime
    invitation_url: str


class InvitationTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=32, max_length=128)


class InvitationValidationResponse(BaseModel):
    invitation_id: int
    assessment_id: int
    assessment_title: str
    description: str | None
    difficulty: AssessmentDifficulty
    duration: int
    expires_at: datetime
    claimed: bool


class InvitationClaimResponse(BaseModel):
    invitation_id: int
    assessment_id: int
    submission: SubmissionResponse
