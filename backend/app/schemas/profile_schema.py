from typing import Optional
from pydantic import BaseModel, field_validator

import re

MATRI_ID_PATTERN = re.compile(r"^[A-Za-z0-9]+$")
_IMAGE_URL_PREFIXES = ("http://", "https://", "data:image/")

MAX_NAME_LENGTH = 100
MAX_IMAGE_LENGTH = 2048
MAX_MATRI_ID_LENGTH = 15
MAX_FILTER_COUNT = 100
MAX_FILTER_KEY_LENGTH = 64
MAX_FILTER_VALUE_LENGTH = 500


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    profile_image: Optional[str] = None
    matri_id: Optional[str] = None

    @field_validator("name")
    @classmethod
    def check_name(cls, v):
        if v is not None:
            v = v.strip()
            if len(v) < 2:
                raise ValueError("Name must be at least 2 characters")
            if len(v) > MAX_NAME_LENGTH:
                raise ValueError(f"Name must be at most {MAX_NAME_LENGTH} characters")
        return v

    @field_validator("profile_image")
    @classmethod
    def check_profile_image(cls, v):
        if v is not None:
            v = v.strip()
            if v and len(v) > MAX_IMAGE_LENGTH:
                raise ValueError(f"Profile image URL must be at most {MAX_IMAGE_LENGTH} characters")
            if v and not v.startswith(_IMAGE_URL_PREFIXES):
                raise ValueError("Profile image must be a valid http(s) or data image URL")
        return v

    @field_validator("matri_id")
    @classmethod
    def check_matri_id(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("MatriID cannot be empty")
            if len(v) > MAX_MATRI_ID_LENGTH:
                raise ValueError(f"MatriID must be at most {MAX_MATRI_ID_LENGTH} characters")
            if not MATRI_ID_PATTERN.match(v):
                raise ValueError("MatriID can contain only letters and numbers")
        return v


class LinkMatriRequest(BaseModel):
    matri_id: str

    @field_validator("matri_id")
    @classmethod
    def check_matri_id(cls, v):
        v = (v or "").strip()
        if not v:
            raise ValueError("MatriID is required")
        if len(v) > MAX_MATRI_ID_LENGTH:
            raise ValueError(f"MatriID must be at most {MAX_MATRI_ID_LENGTH} characters")
        if not MATRI_ID_PATTERN.match(v):
            raise ValueError("MatriID can contain only letters and numbers")
        return v


class QuestionnaireAnswer(BaseModel):
    node_id: str
    option_id: str
    value: Optional[str] = None

    @field_validator("node_id")
    @classmethod
    def check_node_id(cls, v):
        v = (v or "").strip()
        if not v or len(v) > 64:
            raise ValueError("node_id must be between 1 and 64 characters")
        return v

    @field_validator("option_id")
    @classmethod
    def check_option_id(cls, v):
        v = (v or "").strip()
        if not v or len(v) > 64:
            raise ValueError("option_id must be between 1 and 64 characters")
        return v

    @field_validator("value")
    @classmethod
    def check_value(cls, v):
        if v is not None:
            v = v.strip()
            if len(v) > 500:
                raise ValueError("value must be at most 500 characters")
        return v


class QuestionnaireNextRequest(BaseModel):
    answers: list[QuestionnaireAnswer]

    @field_validator("answers")
    @classmethod
    def check_answer_count(cls, v):
        if len(v) > 30:
            raise ValueError("Too many answers submitted at once")
        return v


class SavePreferenceRequest(BaseModel):
    filters: dict[str, str]

    @field_validator("filters")
    @classmethod
    def check_filters(cls, v):
        if len(v) > MAX_FILTER_COUNT:
            raise ValueError(f"Too many filters (max {MAX_FILTER_COUNT})")
        for key, value in v.items():
            if len(key) > MAX_FILTER_KEY_LENGTH:
                raise ValueError(f"Filter key {key!r} is too long")
            if len(value) > MAX_FILTER_VALUE_LENGTH:
                raise ValueError(f"Value for filter {key!r} is too long")
        return v
