from datetime import datetime
from typing import Optional

from pydantic import Field

from .config import BaseSchema


class UserName(BaseSchema):
    first: str = ''
    last: str = ''
    middle: str = ''


class UserContact(BaseSchema):
    type: str
    label: Optional[str] = None
    value: str
    main: bool
    alias: bool
    synthetic: bool


class User(BaseSchema):
    id: int
    nickname: str
    department_id: int
    email: str
    name: UserName
    gender: str
    position: str
    avatar_id: str
    about: str
    birthday: str
    contacts: list[UserContact]
    aliases: list[str]
    groups: list[int]
    external_id: str
    is_admin: bool
    is_robot: bool
    is_dismissed: bool
    is_enabled: bool
    timezone: str
    language: str
    created_at: datetime
    updated_at: datetime


class Users(BaseSchema):
    users: list[User]
    page: int
    pages: int
    per_page: int
    total: int


class TwoFAStatus(BaseSchema):
    has_2fa: bool = Field(alias="has2fa")
    has_security_phone: bool
    user_id: int
