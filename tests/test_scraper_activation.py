from test_selection_activation import activate


def test_scraper_activation_checks_sheet_before_resuming_and_preserves_sync_args(tmp_path):
    result, calls = activate(tmp_path, scheduler="PAUSED", script_name="activate_scraper.sh")
    assert result.returncode == 0, result.stderr
    execute = next(c for c in calls if c[:3] == ["run", "jobs", "execute"])
    assert "--args=scripts/campaign_admin.py,scraper-check" in execute
    job = next(c for c in calls if c[:3] == ["run", "jobs", "update"])
    assert not any(arg.startswith("--args") for arg in job)
    update = next(c for c in calls if c[:4] == ["scheduler", "jobs", "update", "http"])
    resume = next(c for c in calls if c[:3] == ["scheduler", "jobs", "resume"])
    assert "Scraper" in update and "--location=europe-west8" in update
    assert "--schedule=*/20 9-18 * * *" in update
    assert calls.index(execute) < calls.index(update) < calls.index(resume)
    assert not any(c[:3] == ["run", "services", "update"] for c in calls)
    assert "SCRAPER_RIATTIVATO" in result.stdout


def test_failed_scraper_check_does_not_resume_or_reschedule(tmp_path):
    result, calls = activate(tmp_path, scheduler="PAUSED", fail_sync=True, script_name="activate_scraper.sh")
    assert result.returncode == 7
    assert not any(c[:3] == ["scheduler", "jobs", "resume"] for c in calls)
    assert not any(c[:4] == ["scheduler", "jobs", "update", "http"] for c in calls)


def test_running_scraper_must_be_paused_before_migrating_profile(tmp_path):
    result, calls = activate(tmp_path, scheduler="ENABLED", script_name="activate_scraper.sh")
    assert result.returncode == 1
    assert "Scraper in pausa" in result.stderr
    assert len(calls) == 1 and calls[0][:3] == ["scheduler", "jobs", "describe"]
