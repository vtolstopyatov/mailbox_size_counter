from enum import Enum
from typing import Optional

from .config import BaseSchema


class SignPosition(Enum):
    bottom = 'bottom'
    under = 'under'


class Sign(BaseSchema):
    emails: list[str]
    is_default: bool
    lang: str
    text: str


class SenderInfo(BaseSchema):
    default_from: str
    from_name: str = ''
    sign_position: SignPosition = SignPosition.bottom
    signs: Optional[list[Sign]] = None
