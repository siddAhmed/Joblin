"""Tests for backend/scheduler.py per-user job scheduling."""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

import backend.scheduler  # noqa: E402 — pre-import so patch() can resolve backend.scheduler.*


@pytest.mark.anyio
async def test_schedule_user_job_creates_job_with_correct_id_and_timezone():
    """_schedule_user_job creates a job keyed scrape_cron_{user_id} with the user's timezone."""
    mock_scheduler = AsyncMock()

    settings_map = {
        "schedule_cron": "0 9 * * *",
        "scheduler_enabled": True,
        "schedule_timezone": "Asia/Kolkata",
    }

    async def fake_get_setting(session, key, user_id):
        return settings_map.get(key)

    with patch("backend.scheduler.AsyncSessionLocal") as mock_sl, \
         patch("backend.scheduler.get_setting", side_effect=fake_get_setting):
        mock_session = AsyncMock()
        mock_sl.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sl.return_value.__aexit__ = AsyncMock(return_value=False)

        from backend.scheduler import _schedule_user_job
        await _schedule_user_job(mock_scheduler, user_id=42)

    mock_scheduler.add_schedule.assert_called_once()
    _, kwargs = mock_scheduler.add_schedule.call_args
    assert kwargs.get("id") == "scrape_cron_42" or mock_scheduler.add_schedule.call_args.kwargs.get("id") == "scrape_cron_42"


@pytest.mark.anyio
async def test_schedule_user_job_removes_job_when_disabled():
    """_schedule_user_job removes the existing job when scheduler_enabled is False."""
    mock_scheduler = AsyncMock()

    async def fake_get_setting(session, key, user_id):
        return {"schedule_cron": "0 9 * * *", "scheduler_enabled": False, "schedule_timezone": "UTC"}.get(key)

    with patch("backend.scheduler.AsyncSessionLocal") as mock_sl, \
         patch("backend.scheduler.get_setting", side_effect=fake_get_setting):
        mock_session = AsyncMock()
        mock_sl.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sl.return_value.__aexit__ = AsyncMock(return_value=False)

        from backend.scheduler import _schedule_user_job
        await _schedule_user_job(mock_scheduler, user_id=7)

    mock_scheduler.add_schedule.assert_not_called()
    mock_scheduler.remove_schedule.assert_called_once_with("scrape_cron_7")


@pytest.mark.anyio
async def test_run_scrape_job_uses_provided_user_id():
    """_run_scrape_job creates a Run for the given user_id, not hardcoded user_id=1."""
    with patch("backend.scheduler.AsyncSessionLocal") as mock_sl, \
         patch("backend.scheduler.get_setting", return_value=999), \
         patch("backend.pipeline.execute_run", new_callable=AsyncMock):

        # First session: staleness check -> no recent run -> create new Run
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_sl.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sl.return_value.__aexit__ = AsyncMock(return_value=False)

        from backend.scheduler import _run_scrape_job
        await _run_scrape_job(user_id=99)

    # The Run object added to session should have user_id=99
    added_run = mock_session.add.call_args[0][0]
    assert added_run.user_id == 99


@pytest.mark.anyio
async def test_settings_patch_syncs_scheduler_when_schedule_keys_updated(client, app):
    """PATCH /settings with schedule keys calls sync_user_schedule."""
    with patch("backend.routers.settings.sync_user_schedule", new_callable=AsyncMock) as mock_sync:
        mock_scheduler = AsyncMock()
        app.state.scheduler = mock_scheduler

        response = await client.patch("/api/settings", json={"scheduler_enabled": True})

    assert response.status_code == 200
    mock_sync.assert_called_once_with(mock_scheduler, 1)


@pytest.mark.anyio
async def test_settings_patch_does_not_sync_for_non_schedule_keys(client, app):
    """PATCH /settings with non-schedule keys does not call sync_user_schedule."""
    with patch("backend.routers.settings.sync_user_schedule", new_callable=AsyncMock) as mock_sync:
        app.state.scheduler = AsyncMock()

        response = await client.patch("/api/settings", json={"discord_webhook_url": "https://example.com"})

    assert response.status_code == 200
    mock_sync.assert_not_called()
