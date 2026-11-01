"""Runtime settings read from the environment (.env)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ANALYST_MODEL = "claude-sonnet-5-5"
JUDGE_MODEL = "claude-opus-5-5"


@dataclass(frozen=True)
class Settings:
    sec_user_agent: str
    data_dir: Path
    reports_dir: Path

    @classmethod
    def from_env(cls, root: Path | None = None) -> Settings:
        root = root or Path.cwd()
        load_dotenv(root / ".env")
        user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
        if not user_agent:
            raise RuntimeError(
                "SEC_USER_AGENT is not set. Add it to .env (see .env.example); "
                "SEC requires contact details in the User-Agent header."
            )
        return cls(
            sec_user_agent=user_agent,
            data_dir=root / "data",
            reports_dir=root / "reports",
        )
