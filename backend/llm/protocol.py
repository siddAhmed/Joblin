from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class FeedbackExample:
    company_name: str
    normalized_title: str
    normalized_location: str | None
    summary: str


@dataclass
class CriteriaConfig:
    title_allowlist: str = ""
    title_denylist: str = ""
    location_allowlist: str = ""
    location_denylist: str = ""
    seniority_allowlist: list[str] = field(default_factory=list)
    exclusion_keywords: list[str] = field(default_factory=list)
    profile_description: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "CriteriaConfig":
        return cls(
            title_allowlist=d.get("title_allowlist", ""),
            title_denylist=d.get("title_denylist", ""),
            location_allowlist=d.get("location_allowlist", ""),
            location_denylist=d.get("location_denylist", ""),
            seniority_allowlist=d.get("seniority_allowlist", []),
            exclusion_keywords=d.get("exclusion_keywords", []),
            profile_description=d.get("profile_description", ""),
        )


@dataclass
class FilterResult:
    score: float
    reasoning: str


@runtime_checkable
class LLMProvider(Protocol):
    async def filter(
        self,
        title: str,
        company_name: str,
        location: str | None,
        description: str,
        criteria: CriteriaConfig,
        negative_examples: list[FeedbackExample],
    ) -> FilterResult: ...

    async def summarize(
        self,
        title: str,
        company_name: str,
        description: str,
        score: float,
    ) -> str: ...

    async def extract_skills(self, title: str, description: str) -> list[str]: ...

    async def tailor_resume(self, tex_content: str, job_description: str) -> str: ...
