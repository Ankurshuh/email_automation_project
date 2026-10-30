"""
Minimal sanity tests for the Milestone 2 core modules.
Run directly: python3 tests.py
"""

from datetime import datetime, timedelta

from email_composer import Attachment, EmailCompositionError, compose_email
from scheduler_engine import SchedulerEngine


def test_compose_basic_email():
    email = compose_email(
        sender="a@example.com", recipients=["b@example.com"],
        subject="Hi", body="Hello there",
    )
    assert email.sender == "a@example.com"
    assert email.recipients == ["b@example.com"]
    assert "Hello there" in email.as_string()
    print("PASS: test_compose_basic_email")


def test_compose_rejects_empty_recipients():
    try:
        compose_email(sender="a@example.com", recipients=[], subject="Hi", body="Hi")
    except EmailCompositionError:
        print("PASS: test_compose_rejects_empty_recipients")
        return
    raise AssertionError("Expected EmailCompositionError")


def test_compose_rejects_empty_subject():
    try:
        compose_email(sender="a@example.com", recipients=["b@example.com"], subject="  ", body="Hi")
    except EmailCompositionError:
        print("PASS: test_compose_rejects_empty_subject")
        return
    raise AssertionError("Expected EmailCompositionError")


def test_compose_with_attachment():
    att = Attachment(filename="note.txt", content=b"hello", mime_subtype="plain")
    email = compose_email(
        sender="a@example.com", recipients=["b@example.com"],
        subject="Hi", body="See attached", attachments=[att],
    )
    assert "note.txt" in email.as_string()
    print("PASS: test_compose_with_attachment")


def test_scheduler_registers_and_reports_next_run():
    engine = SchedulerEngine()
    engine.start()
    run_at = datetime.now() + timedelta(minutes=5)
    engine.schedule_once("t1", run_at, lambda: None)
    next_run = engine.next_run_time("t1")
    assert next_run is not None
    assert abs((next_run - run_at).total_seconds()) < 2
    engine.cancel("t1")
    assert engine.next_run_time("t1") is None
    engine.shutdown()
    print("PASS: test_scheduler_registers_and_reports_next_run")


if __name__ == "__main__":
    test_compose_basic_email()
    test_compose_rejects_empty_recipients()
    test_compose_rejects_empty_subject()
    test_compose_with_attachment()
    test_scheduler_registers_and_reports_next_run()
    print("\nAll tests passed.")
