"""The triage watcher, end to end: what reaches a session's inbox, and when.

`.claude/wake-on-suggestions.sh` runs `.claude/watch-suggestions.sh` detached and posts each settle to
the session's inbox socket. Every test here runs the real wrapper, the real watcher and the real ledger
against a scratch suggestions file, with a fake inbox socket standing in for Claude Code's, and asserts
on the lines that reached it. The one thing it cannot show is Claude Code delivering what it received;
that was checked by hand on 2.1.285 (docs/CONSUMER_TRIAGE_LOOP.md § 1).

mtime has a one-second grain, so a test waits past the second the watcher started in before its first
edit — an edit inside that second is invisible to it, and the test would pass for the wrong reason.
"""

import json
import os
import pathlib
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
WRAPPER = REPO / ".claude" / "wake-on-suggestions.sh"
WATCHER = REPO / ".claude" / "watch-suggestions.sh"
TOKEN = "test-token-7f3a"

SUGGESTION = (
    '\n## S1 — a consumer asks for something\n\nThe consumer\'s text, with "quotes" and a \\ backslash.\n'
)


class FakeInbox:
    """A Unix socket that records every connection as the list of JSON lines it carried."""

    def __init__(self, path: pathlib.Path) -> None:
        self.path = path
        self.connections: list[list[dict]] = []
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(str(path))
        self.server.listen()
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self) -> None:
        while True:
            try:
                conn, _ = self.server.accept()
            except OSError:
                return
            with conn:
                data = b""
                while chunk := conn.recv(65536):
                    data += chunk
            self.connections.append([json.loads(line) for line in data.decode().splitlines() if line])

    def messages(self) -> list[str]:
        return [
            line["message"]["content"]
            for conn in self.connections
            for line in conn
            if line.get("type") == "user"
        ]

    def close(self) -> None:
        self.server.close()
        self.path.unlink(missing_ok=True)


def wait_for(predicate, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return predicate()


@pytest.fixture
def scratch():
    # AF_UNIX paths are capped near 108 bytes, and pytest's tmp_path can exceed that.
    root = pathlib.Path(tempfile.mkdtemp(prefix="tw-"))
    yield root
    shutil.rmtree(root, ignore_errors=True)


@pytest.fixture
def inbox(scratch):
    box = FakeInbox(scratch / "inbox.sock")
    yield box
    box.close()


@pytest.fixture
def suggestions(scratch):
    doc = scratch / "CONSUMER_SUGGESTIONS.md"
    doc.write_text("# Consumer suggestions\n\nThe open inbox.\n")
    return doc


@pytest.fixture
def arm(scratch, inbox, suggestions):
    started: list[subprocess.Popen] = []

    def _arm(**overrides: str) -> subprocess.Popen:
        env = {
            **os.environ,
            "CLAUDE_CODE_MESSAGING_SOCKET": str(inbox.path),
            "CLAUDE_CODE_MESSAGING_TOKEN": TOKEN,
            "FILE": str(suggestions),
            "PIDFILE": str(scratch / "watch.pid"),
            "COOLDOWN": "2",
            "POLL": "0.3",
            "READ_TIMEOUT": "1",
            "BRANCH": "",
            **overrides,
        }
        proc = subprocess.Popen(
            [str(WRAPPER)], env=env, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        started.append(proc)
        # Past the second the watcher seeded its mtime in; see the module docstring.
        time.sleep(1.2)
        return proc

    yield _arm
    for proc in started:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=10)


def append(doc: pathlib.Path, text: str) -> None:
    with doc.open("a") as fh:
        fh.write(text)


def watcher_pid(scratch: pathlib.Path) -> int:
    return int((scratch / "watch.pid").read_text())


def test_a_new_suggestion_wakes_the_session_once(arm, inbox, suggestions):
    arm()
    append(suggestions, SUGGESTION)
    assert wait_for(lambda: inbox.messages(), 10)
    time.sleep(3)  # a second settle would land inside this window
    assert len(inbox.messages()) == 1
    [conn] = inbox.connections
    assert conn[0] == {"type": "auth", "token": TOKEN}
    assert conn[1]["type"] == "user" and conn[1]["message"]["role"] == "user"
    body = conn[1]["message"]["content"]
    assert "S1(new)" in body
    assert "docs/CONSUMER_TRIAGE_LOOP.md" in body


def test_a_burst_of_edits_is_one_wake(arm, inbox, suggestions):
    arm()
    append(suggestions, SUGGESTION)
    for n in range(4):  # each edit lands inside the 2 s cooldown the previous one restarted
        time.sleep(0.7)
        append(suggestions, f"\nMore from the consumer, part {n}.\n")
    assert wait_for(lambda: inbox.messages(), 10)
    time.sleep(3)
    assert len(inbox.messages()) == 1


def test_an_edit_with_nothing_pending_stays_quiet(arm, inbox, suggestions):
    proc = arm()
    append(suggestions, "\nA preamble edit, no section.\n")
    time.sleep(5)  # cooldown plus polls: the settle has happened, and said "nothing pending"
    assert inbox.messages() == []
    assert proc.poll() is None


def test_pending_work_older_than_the_arming_does_not_fire(arm, inbox, suggestions):
    append(suggestions, SUGGESTION)
    time.sleep(1.1)
    arm()
    time.sleep(4)
    assert inbox.messages() == []


def test_two_settles_are_two_wakes(arm, inbox, suggestions):
    arm()
    append(suggestions, SUGGESTION)
    assert wait_for(lambda: len(inbox.messages()) == 1, 10)
    append(suggestions, SUGGESTION.replace("S1", "S2"))
    assert wait_for(lambda: len(inbox.messages()) == 2, 10)
    first, second = inbox.messages()
    assert "S1(new)" in first and "S1(new)" in second and "S2(new)" in second
    assert first != second


def test_a_newer_arming_supersedes_the_older(arm, inbox, suggestions, scratch):
    old = arm()
    old_watcher = watcher_pid(scratch)
    new = arm()
    assert watcher_pid(scratch) != old_watcher
    assert wait_for(lambda: old.poll() is not None, 5), "the replaced wrapper is still running"
    append(suggestions, SUGGESTION)
    assert wait_for(lambda: inbox.messages(), 10)
    time.sleep(3)
    assert len(inbox.messages()) == 1
    assert new.poll() is None


def test_the_wrapper_exits_when_its_watcher_dies(arm, scratch):
    proc = arm()
    os.kill(watcher_pid(scratch), signal.SIGTERM)
    assert wait_for(lambda: proc.poll() is not None, 5)


def test_the_wrapper_exits_when_the_session_socket_goes(arm, inbox):
    proc = arm()
    inbox.close()
    assert wait_for(lambda: proc.poll() is not None, 5)


def test_a_quiet_wrapper_outlives_its_read_timeout(arm):
    # A read timeout once read as a dead watcher (`$?` after `if ! read` is the negation's 0), and
    # every quiet minute killed a healthy one.
    proc = arm(READ_TIMEOUT="1")
    time.sleep(4)
    assert proc.poll() is None


def test_an_empty_branch_never_pauses(scratch, suggestions):
    env = {
        **os.environ,
        "FILE": str(suggestions),
        "PIDFILE": str(scratch / "watch.pid"),
        "POLL": "0.3",
        "BRANCH": "",
    }
    proc = subprocess.Popen(
        [str(WATCHER)], env=env, start_new_session=True, stdout=subprocess.PIPE, text=True
    )
    time.sleep(1.5)
    os.killpg(proc.pid, signal.SIGTERM)
    out, _ = proc.communicate(timeout=10)
    assert "paused" not in out


def test_a_paused_watcher_wakes_nobody(arm, inbox, suggestions):
    proc = arm(BRANCH="no-such-branch-here", BRANCH_PAUSE="1")
    append(suggestions, SUGGESTION)
    time.sleep(5)
    assert inbox.messages() == []
    assert proc.poll() is None


def test_outside_a_session_it_refuses_to_start(suggestions, scratch):
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_CODE_MESSAGING")}
    env |= {"FILE": str(suggestions), "PIDFILE": str(scratch / "watch.pid")}
    result = subprocess.run([str(WRAPPER)], env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert "inside a Claude Code session" in result.stderr
    assert not (scratch / "watch.pid").exists()


def test_an_armed_notice_is_the_first_post_and_the_only_one(arm, inbox):
    arm(ARMED_NOTICE="1")
    assert wait_for(lambda: inbox.messages(), 5)
    time.sleep(2)
    [notice] = inbox.messages()
    assert "armed on" in notice


HOOK = REPO / ".claude" / "hooks" / "arm_triage_watcher.py"


def run_hook(prompt: str, env: dict[str, str]) -> str:
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": prompt}),
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    return result.stdout


@pytest.fixture
def hook_env(scratch, inbox, suggestions):
    env = {
        **os.environ,
        "CLAUDE_CODE_MESSAGING_SOCKET": str(inbox.path),
        "CLAUDE_CODE_MESSAGING_TOKEN": TOKEN,
        "FILE": str(suggestions),
        "PIDFILE": str(scratch / "watch.pid"),
        "COOLDOWN": "2",
        "POLL": "0.3",
        "READ_TIMEOUT": "1",
        "BRANCH": "",
    }
    yield env
    pidfile = scratch / "watch.pid"
    if pidfile.exists():
        os.kill(int(pidfile.read_text()), signal.SIGTERM)
        time.sleep(1.5)  # the detached wrapper notices within READ_TIMEOUT and exits


def test_a_prompt_naming_the_runbook_arms_a_watcher_that_wakes(hook_env, inbox, suggestions):
    out = run_hook("@docs/CONSUMER_TRIAGE_LOOP.md rearm", hook_env)
    assert "armed on" in out
    assert wait_for(lambda: inbox.messages(), 5), "no armed notice: the hook did not start the wrapper"
    time.sleep(1.2)
    append(suggestions, SUGGESTION)
    assert wait_for(lambda: len(inbox.messages()) == 2, 10)
    assert "S1(new)" in inbox.messages()[1]


@pytest.mark.parametrize(
    "prompt",
    [
        "@docs/CONSUMER_TRIAGE_LOOP.md Arm",
        "@docs/CONSUMER_TRIAGE_LOOP.md",
        "start triage per docs/CONSUMER_TRIAGE_LOOP.md please",
        "Arm\n@docs/CONSUMER_TRIAGE_LOOP.md",
    ],
)
def test_the_doc_citation_is_the_only_invariant(hook_env, inbox, prompt):
    # The seat is the session pointed at the runbook; the verb around the citation is free.
    assert "armed on" in run_hook(prompt, hook_env)
    assert wait_for(lambda: inbox.messages(), 5)


def test_any_other_prompt_arms_nothing(hook_env, inbox, scratch):
    assert run_hook("fix the compiler warning in resolve.py", hook_env) == ""
    time.sleep(2)
    assert inbox.messages() == []
    assert not (scratch / "watch.pid").exists()


def test_the_hook_says_so_when_the_session_has_no_inbox(hook_env, scratch):
    env = {k: v for k, v in hook_env.items() if not k.startswith("CLAUDE_CODE_MESSAGING")}
    assert "NOT armed" in run_hook("@docs/CONSUMER_TRIAGE_LOOP.md rearm", env)
    assert not (scratch / "watch.pid").exists()


def test_the_hook_ignores_input_that_is_not_json(hook_env):
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input="not json",
        env=hook_env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert (result.returncode, result.stdout) == (0, "")
