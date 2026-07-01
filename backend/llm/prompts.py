import json
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
        "Score >= 0.70 means strong match. 0.40-0.69 means borderline. < 0.40 means discard. "
        "If the candidate's profile specifies a location or work authorization constraint, "
        "score any job < 0.40 that is not in the candidate's country, not fully remote, "
        "and does not explicitly mention visa sponsorship or work permit support."
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


def build_job_analysis_prompt(job_description: str) -> tuple[str, str]:
    system = (
        "You are a job requirements analyst. Extract the key requirements from a job description. "
        "Return JSON only, no other text: "
        '{"required_skills": [...], "preferred_skills": [...], "key_themes": [...], '
        '"seniority_signals": [...], "keywords": [...]}'
    )
    user = f"Job description:\n\n{job_description[:3000]}"
    return system, user


def build_activity_selection_prompt(
    requirements: dict,
    tex_content: str,
    activities_content: str | None,
) -> tuple[str, str]:
    system = (
        "You are a career coach selecting content for a resume tailoring task. "
        "Given job requirements, a reference resume, and optionally an activities bank, "
        "select the 6-8 most relevant items to emphasize in the final resume. "
        "Return a plain-text numbered list. Be selective - only items that genuinely strengthen this application. "
        "Do not reproduce LaTeX syntax. For items from the resume, quote or paraphrase the key phrase. "
        "For items from the activities bank, copy the relevant text verbatim."
    )
    req_text = json.dumps(requirements, indent=2)
    activities_section = (
        f"\n\nActivities bank:\n{activities_content}" if activities_content else ""
    )
    user = (
        f"Job requirements:\n{req_text}\n\n"
        f"Reference resume (LaTeX):\n{tex_content}"
        f"{activities_section}\n\n"
        "Select the 6-8 most relevant items from the resume"
        + (" and activities bank" if activities_content else "")
        + " for this role."
    )
    return system, user


def build_tailor_prompt(tex_content: str, selected_items: str) -> tuple[str, str]:
    system = (
        "You are a resume tailoring expert. Given a LaTeX resume and a curated list of items to emphasize, "
        "return ONLY the modified LaTeX source code. No explanation, no markdown code fences, "
        "no commentary of any kind - just the raw .tex content. "
        "Critical LaTeX rules: always escape special characters in text -- use \\& not &, "
        "\\% not %, \\$ not $, \\# not #, \\_ not _ (outside math/commands). "
        "Never introduce these characters unescaped inside \\textbf{}, \\textit{}, or any text context."
    )
    user = (
        f"Here is my LaTeX resume:\n\n{tex_content}\n\n"
        f"Items to emphasize in this tailored version:\n\n{selected_items}\n\n"
        "Please modify the resume to incorporate and highlight these items. "
        "Adjust bullet points, reorder sections if beneficial, and ensure the selected items are prominent. "
        "Preserve the original LaTeX template structure and commands exactly."
    )
    return system, user
