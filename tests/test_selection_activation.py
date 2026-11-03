import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

import pytest

COMMIT = "a" * 40
ROOT = Path(__file__).resolve().parents[1]


def activate(tmp_path, *, fail_sync=False, scheduler="ENABLED", pending=False, script_name="activate_smart_selection.sh"):
    log = tmp_path / "calls.jsonl"
    fake = tmp_path / "gcloud"
    fake.write_text(
        f"#!{sys.executable}\n"
        """import json, os, sys
from pathlib import Path
args = sys.argv[1:]
log = Path(os.environ['SELECTION_TEST_LOG'])
previous = log.read_text().splitlines() if log.exists() else []
with log.open('a') as output:
    output.write(json.dumps(args) + '\\n')
if args[:3] == ['run', 'services', 'describe']:
    if '--format=json' in args:
        print(json.dumps({'spec': {'template': {'spec': {'containers': [{'env': []}]}}}}))
    else:
        print('scraping-new scraping-new europe-west1-docker.pkg.dev/scraping-505816/test/image:' + 'a' * 40)
elif args[:3] == ['run', 'jobs', 'describe']:
    print('sync')
elif args[:3] == ['scheduler', 'jobs', 'describe']:
    print(os.environ['SELECTION_TEST_SCHEDULER'])
elif args[:4] == ['run', 'jobs', 'executions', 'list']:
    already_waited = any(json.loads(line)[:4] == args[:4] for line in previous)
    if os.environ['SELECTION_TEST_PENDING'] == '1' and not already_waited:
        print(json.dumps([{'status': {'conditions': [{'type': 'Completed', 'status': 'Unknown'}]}}]))
    else:
        print('[]')
elif args[:3] == ['run', 'jobs', 'execute'] and os.environ['SELECTION_TEST_FAIL_SYNC'] == '1':
    sys.exit(7)
"""
    )
    fake.chmod(0o755)
    script = (ROOT / "scripts" / script_name).read_text()
    script = script.replace("gcloud ", shlex.quote(str(fake)) + " ")
    script = script.replace("sleep 5", ":").replace("sleep 10", ":")
    local = tmp_path / "activate.sh"
    local.write_text(script)
    result = subprocess.run(
        ["bash", str(local), COMMIT], capture_output=True, text=True,
        env=dict(os.environ, SELECTION_TEST_LOG=str(log), SELECTION_TEST_SCHEDULER=scheduler,
                 SELECTION_TEST_FAIL_SYNC=str(int(fail_sync)), SELECTION_TEST_PENDING=str(int(pending))),
        timeout=20,
    )
    return result, [json.loads(line) for line in log.read_text().splitlines()]


def test_activation_requires_successful_sync_and_restores_scheduler(tmp_path):
    result, calls = activate(tmp_path, fail_sync=True)
    assert result.returncode == 7
    assert not any(c[:3] == ["run", "services", "update"] for c in calls)
    assert calls[-1][:3] == ["scheduler", "jobs", "resume"]


@pytest.mark.parametrize("scheduler", ["ENABLED", "PAUSED"])
def test_activation_uses_deployed_image_preserves_args_and_scheduler_state(tmp_path, scheduler):
    result, calls = activate(tmp_path, scheduler=scheduler)
    assert result.returncode == 0, result.stderr
    job = next(c for c in calls if c[:3] == ["run", "jobs", "update"])
    execute = next(c for c in calls if c[:3] == ["run", "jobs", "execute"])
    service = next(c for c in calls if c[:3] == ["run", "services", "update"])
    assert any(arg.endswith(":" + COMMIT) for arg in job if arg.startswith("--image="))
    assert not any(arg.startswith("--args") for arg in job + execute)
    assert calls.index(job) < calls.index(execute) < calls.index(service)
    assert "--update-env-vars=SMART_SELECTION_ENABLED=True" in service
    scheduler_changes = [c[2] for c in calls if c[:2] == ["scheduler", "jobs"] and c[2] != "describe"]
    assert scheduler_changes == (["pause", "resume"] if scheduler == "ENABLED" else [])
    assert "PRIORITA_CONTATTI_ATTIVA" in result.stdout


def test_activation_waits_for_previous_sync_before_changing_job(tmp_path):
    result, calls = activate(tmp_path, pending=True)
    assert result.returncode == 0, result.stderr
    waits = [n for n, c in enumerate(calls) if c[:4] == ["run", "jobs", "executions", "list"]]
    job = next(n for n, c in enumerate(calls) if c[:3] == ["run", "jobs", "update"])
    assert len(waits) == 2 and max(waits) < job
