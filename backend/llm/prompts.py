from backend.llm.protocol import CriteriaConfig, FeedbackExample


def build_filter_prompt(
    title: str,
    company_name: str,
    location: str | None,
    description: str,
    criteria: CriteriaConfig,
    negative_examples: list[FeedbackExample],
) -> tuple[str, str]:
    criteria_lines = []
    if criteria.profile_description:
        criteria_lines.append(f"Profile: {criteria.profile_description}")
    if criteria.title_allowlist:
        criteria_lines.append(f"Title must match: {criteria.title_allowlist}")
    if criteria.title_denylist:
        criteria_lines.append(f"Title must NOT match: {criteria.title_denylist}")
    if criteria.seniority_allowlist:
        criteria_lines.append(f"Seniority: {', '.join(criteria.seniority_allowlist)}")
    criteria_text = "\n".join(criteria_lines) or "No specific criteria set."

    neg_lines = ""
    if negative_examples:
        bullets = "\n".join(
            f"- {ex.normalized_title} at {ex.company_name}: {ex.summary[:100]}"
            for ex in negative_examples[:5]
        )
        neg_lines = f"\nJobs the candidate dismissed as not interested:\n{bullets}\n"

    system = (
        "You are a job relevance filter. Score the job 0.0-1.0 against the criteria. "
        'Return JSON only: {"score": <float>, "reasoning": "<one sentence>"}. '
        "Score >= 0.70 means strong match. 0.40-0.69 means borderline. < 0.40 means discard."
    )

    user = (
        f"Criteria:\n{criteria_text}\n"
        f"{neg_lines}"
        f"\nJob to score:\n"
        f"Title: {title}\n"
        f"Company: {company_name}\n"
        f"Location: {location or 'Not specified'}\n"
        f"Description:\n{description[:2000]}"
    )

    return system, user


def build_summarize_prompt(
    title: str,
    company_name: str,
    description: str,
    score: float,
) -> str:
    return (
        f"Summarize this job posting for a candidate deciding whether to apply. "
        f"Return exactly 4 labeled sections: Role snapshot, Key requirements, Why it matched, Red flags. "
        f"Be direct. Max 200 words total.\n\n"
        f"Job: {title} at {company_name} (relevance score: {score:.2f})\n"
        f"Description:\n{description[:3000]}"
    )


def build_skills_prompt(title: str, description: str) -> str:
    return (
        "Extract skills from this job description. Return a JSON array of canonical skill name strings only. "
        "Include: programming languages, frameworks, libraries, databases, cloud platforms, infrastructure tools, "
        "and specific technical domain skills such as 'system design', 'distributed systems', 'API design', "
        "'event-driven architecture', 'data modeling'. "
        "Exclude generic soft skills like communication, ownership, leadership, or collaboration. "
        "Use canonical names: 'PostgreSQL' not 'Postgres', 'React' not 'React.js', "
        "'Kubernetes' not 'k8s', 'TypeScript' not 'TS'. "
        "Return only the JSON array with no other text, markdown, or explanation.\n\n"
        f"Job title: {title}\n"
        f"Description:\n{description[:3000]}"
    )
