"""shared_catalog_v1

Revision ID: 1e82ee71e62b
Revises: e5d40512ca38
Create Date: 2026-06-18 16:53:47.376985

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1e82ee71e62b'
down_revision: Union[str, Sequence[str], None] = 'e5d40512ca38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from sqlalchemy import text

    # Create company_catalog
    op.create_table(
        "company_catalog",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("careers_url", sa.String(), nullable=False),
        sa.Column("ats_type", sa.String(), nullable=True),
        sa.Column("ats_identifier", sa.String(), nullable=True),
        sa.Column("custom_api_url", sa.String(), nullable=True),
        sa.Column("css_selector", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("quarantine_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quarantined_at", sa.DateTime(), nullable=True),
        sa.Column("quarantine_reason", sa.String(), nullable=True),
        sa.Column("discovery_status", sa.String(), nullable=False, server_default="none"),
        sa.Column("discovery_message", sa.Text(), nullable=True),
        sa.Column("source", sa.String(), nullable=False, server_default="default"),
        sa.Column("last_scraped_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("careers_url"),
    )

    op.create_table(
        "user_companies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("catalog_id", sa.Integer(), sa.ForeignKey("company_catalog.id"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "catalog_id", name="uq_user_catalog"),
    )

    op.create_table(
        "raw_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("catalog_company_id", sa.Integer(), sa.ForeignKey("company_catalog.id"), nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("raw_description", sa.Text(), nullable=False, server_default=""),
        sa.Column("normalized_title", sa.String(), nullable=False, server_default=""),
        sa.Column("normalized_location", sa.String(), nullable=True),
        sa.Column("seniority", sa.String(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("catalog_company_id", "job_id", name="uq_catalog_job"),
    )

    op.create_table(
        "user_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("raw_job_id", sa.Integer(), sa.ForeignKey("raw_jobs.id"), nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("runs.id"), nullable=True),
        sa.Column("passed_heuristic", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("preview_only", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "raw_job_id", name="uq_user_raw_job"),
    )

    # Data migration
    conn = op.get_bind()

    from backend.data.default_companies import DEFAULT_COMPANIES
    default_names = {c["name"].lower() for c in DEFAULT_COMPANIES}

    # Load all companies, most recently updated first
    all_companies = conn.execute(text("SELECT * FROM companies ORDER BY updated_at DESC")).fetchall()

    # Deduplicate by careers_url; first row per URL is the most recent
    url_to_canonical = {}
    for row in all_companies:
        if row.careers_url not in url_to_canonical:
            url_to_canonical[row.careers_url] = row

    # Insert into company_catalog; track old company.id -> catalog.id
    old_company_id_to_catalog_id: dict[int, int] = {}

    for url, row in url_to_canonical.items():
        source = "default" if row.name.lower() in default_names else "user_submitted"
        result = conn.execute(text("""
            INSERT INTO company_catalog
              (name, careers_url, ats_type, ats_identifier, custom_api_url, css_selector,
               is_active, quarantine_count, quarantined_at, quarantine_reason,
               discovery_status, discovery_message, source, created_at, updated_at)
            VALUES
              (:name, :careers_url, :ats_type, :ats_identifier, :custom_api_url, :css_selector,
               :is_active, :quarantine_count, :quarantined_at, :quarantine_reason,
               :discovery_status, :discovery_message, :source, :created_at, :updated_at)
        """), {
            "name": row.name, "careers_url": row.careers_url,
            "ats_type": row.ats_type, "ats_identifier": row.ats_identifier,
            "custom_api_url": row.custom_api_url, "css_selector": row.css_selector,
            "is_active": row.is_active, "quarantine_count": row.quarantine_count,
            "quarantined_at": row.quarantined_at, "quarantine_reason": row.quarantine_reason,
            "discovery_status": row.discovery_status, "discovery_message": row.discovery_message,
            "source": source, "created_at": row.created_at, "updated_at": row.updated_at,
        })
        catalog_id = result.lastrowid
        for c in all_companies:
            if c.careers_url == url:
                old_company_id_to_catalog_id[c.id] = catalog_id

    # Insert user_companies (deduplicated by user_id + catalog_id)
    seen_user_catalog: set[tuple[int, int]] = set()
    for row in all_companies:
        catalog_id = old_company_id_to_catalog_id.get(row.id)
        if not catalog_id:
            continue
        key = (row.user_id, catalog_id)
        if key in seen_user_catalog:
            continue
        seen_user_catalog.add(key)
        conn.execute(text("""
            INSERT INTO user_companies (user_id, catalog_id, is_active, created_at)
            VALUES (:user_id, :catalog_id, :is_active, :created_at)
        """), {"user_id": row.user_id, "catalog_id": catalog_id,
               "is_active": row.is_active, "created_at": row.created_at})

    # Load all jobs, most recently seen first
    all_jobs = conn.execute(text("SELECT * FROM jobs ORDER BY last_seen_at DESC")).fetchall()

    # Insert raw_jobs (deduplicated by catalog_company_id + job_id)
    raw_job_key_to_id: dict[tuple[int, str], int] = {}
    for job in all_jobs:
        catalog_id = old_company_id_to_catalog_id.get(job.company_id)
        if not catalog_id:
            continue
        key = (catalog_id, job.job_id)
        if key not in raw_job_key_to_id:
            result = conn.execute(text("""
                INSERT INTO raw_jobs
                  (catalog_company_id, job_id, title, location, url, raw_description,
                   normalized_title, normalized_location, seniority,
                   first_seen_at, last_seen_at, is_active)
                VALUES
                  (:catalog_company_id, :job_id, :title, :location, :url, :raw_description,
                   :normalized_title, :normalized_location, :seniority,
                   :first_seen_at, :last_seen_at, :is_active)
            """), {
                "catalog_company_id": catalog_id, "job_id": job.job_id,
                "title": job.title, "location": job.location, "url": job.url,
                "raw_description": job.raw_description or "",
                "normalized_title": job.normalized_title or "",
                "normalized_location": job.normalized_location,
                "seniority": job.seniority,
                "first_seen_at": job.first_seen_at, "last_seen_at": job.last_seen_at,
                "is_active": job.is_active,
            })
            raw_job_key_to_id[key] = result.lastrowid
        else:
            # Keep the earliest first_seen_at
            conn.execute(text("""
                UPDATE raw_jobs SET first_seen_at = MIN(first_seen_at, :fsa) WHERE id = :id
            """), {"fsa": job.first_seen_at, "id": raw_job_key_to_id[key]})

    # Insert user_jobs; map old job.id -> user_job.id for FK updates
    old_job_id_to_user_job_id: dict[int, int] = {}
    seen_user_raw: dict[tuple[int, int], int] = {}
    for job in sorted(all_jobs, key=lambda r: r.id):
        catalog_id = old_company_id_to_catalog_id.get(job.company_id)
        if not catalog_id:
            continue
        raw_job_id = raw_job_key_to_id.get((catalog_id, job.job_id))
        if not raw_job_id:
            continue
        ur_key = (job.user_id, raw_job_id)
        if ur_key in seen_user_raw:
            old_job_id_to_user_job_id[job.id] = seen_user_raw[ur_key]
        else:
            result = conn.execute(text("""
                INSERT INTO user_jobs
                  (user_id, raw_job_id, run_id, passed_heuristic, preview_only, first_seen_at)
                VALUES (:user_id, :raw_job_id, NULL, 1, :preview_only, :first_seen_at)
            """), {"user_id": job.user_id, "raw_job_id": raw_job_id,
                   "preview_only": job.preview_only, "first_seen_at": job.first_seen_at})
            uj_id = result.lastrowid
            seen_user_raw[ur_key] = uj_id
            old_job_id_to_user_job_id[job.id] = uj_id

    # Update matches.job_id -> user_jobs.id
    for row in conn.execute(text("SELECT id, job_id FROM matches")).fetchall():
        uj_id = old_job_id_to_user_job_id.get(row.job_id)
        if uj_id:
            conn.execute(text("UPDATE matches SET job_id = :uj WHERE id = :id"),
                         {"uj": uj_id, "id": row.id})

    # Update feedback_examples.job_id -> user_jobs.id
    for row in conn.execute(text("SELECT id, job_id FROM feedback_examples")).fetchall():
        uj_id = old_job_id_to_user_job_id.get(row.job_id)
        if uj_id:
            conn.execute(text("UPDATE feedback_examples SET job_id = :uj WHERE id = :id"),
                         {"uj": uj_id, "id": row.id})

    # Update application_tracking.job_id -> user_jobs.id
    for row in conn.execute(text("SELECT id, job_id FROM application_tracking")).fetchall():
        uj_id = old_job_id_to_user_job_id.get(row.job_id)
        if uj_id:
            conn.execute(text("UPDATE application_tracking SET job_id = :uj WHERE id = :id"),
                         {"uj": uj_id, "id": row.id})

    # Update run_company_results.company_id -> company_catalog.id
    for row in conn.execute(text("SELECT id, company_id FROM run_company_results")).fetchall():
        cat_id = old_company_id_to_catalog_id.get(row.company_id)
        if cat_id:
            conn.execute(text("UPDATE run_company_results SET company_id = :cat WHERE id = :id"),
                         {"cat": cat_id, "id": row.id})

    # Update run.company_ids JSON (stores list of company IDs) to user_company IDs
    # Load user_companies to build catalog_id -> user_company.id per user
    uc_rows = conn.execute(text("SELECT id, user_id, catalog_id FROM user_companies")).fetchall()
    # (user_id, catalog_id) -> user_company.id
    uc_lookup: dict[tuple[int, int], int] = {(r.user_id, r.catalog_id): r.id for r in uc_rows}

    import json
    for row in conn.execute(text("SELECT id, user_id, company_ids FROM runs WHERE company_ids IS NOT NULL")).fetchall():
        try:
            old_ids = json.loads(row.company_ids) if isinstance(row.company_ids, str) else row.company_ids
            if not old_ids:
                continue
            new_ids = []
            for old_cid in old_ids:
                cat_id = old_company_id_to_catalog_id.get(old_cid)
                if cat_id:
                    uc_id = uc_lookup.get((row.user_id, cat_id))
                    if uc_id:
                        new_ids.append(uc_id)
            conn.execute(text("UPDATE runs SET company_ids = :ids WHERE id = :id"),
                         {"ids": json.dumps(new_ids), "id": row.id})
        except Exception:
            pass


def downgrade() -> None:
    op.drop_table("user_jobs")
    op.drop_table("raw_jobs")
    op.drop_table("user_companies")
    op.drop_table("company_catalog")
    # Note: FK value updates to matches/feedback/application/run_company_results are not reversed
    # Restore from backup if needed
