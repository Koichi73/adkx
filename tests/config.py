import os
from dataclasses import dataclass


@dataclass
class TestConfiguration:

    model: str = "gemini-2.5-flash"

config = TestConfiguration()
