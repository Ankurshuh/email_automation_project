"""
Milestone 2 prototype: schedule ONE email and watch it actually get sent.

Runs a local, throwaway SMTP server (no real credentials needed) so the
whole pipeline -- compose -> schedule -> fire -> send -> deliver -- is
proven end to end in a single run.
"""

import logging
import time
from datetime import datetime, timedelta

from aiosmtpd.controller import Controller

from email_composer import compose_email
from scheduler_engine import SchedulerEngine
from smtp_client import SMTPClient, SMTPConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("prototype")

received_messages = []


class CapturingHandler:
    """A minimal aiosmtpd handler that just records what it receives."""

    async def handle_DATA(self, server, session, envelope):
        received_messages.append({
            "mail_from": envelope.mail_from,
            "rcpt_tos": envelope.rcpt_tos,
            "content": envelope.content.decode("utf-8", errors="replace"),
        })
        logger.info("Test SMTP server received a message for %s", envelope.rcpt_tos)
        return "250 Message accepted for delivery"


def send_prototype_email():
    """The job the scheduler calls when the due time arrives."""
    email = compose_email(
        sender="automation@example.com",
        sender_name="Automation Platform",
        recipients=["stakeholder@example.com"],
        subject="Milestone 2 prototype -- single scheduled email",
        body="This message was composed, scheduled, and delivered by the Milestone 2 prototype.",
    )
    config = SMTPConfig(host="127.0.0.1", port=1025, use_tls=False)
    with SMTPClient(config) as client:
        client.send(email)


def main():
    # 1. Start a local test SMTP server -- stands in for a real mail relay
    controller = Controller(CapturingHandler(), hostname="127.0.0.1", port=1025)
    controller.start()
    logger.info("Test SMTP server listening on 127.0.0.1:1025")

    # 2. Start the scheduling engine and schedule exactly ONE email, 5s out
    engine = SchedulerEngine()
    engine.start()
    run_at = datetime.now() + timedelta(seconds=5)
    engine.schedule_once("prototype-email", run_at, send_prototype_email)
    logger.info("Scheduled prototype email for %s", run_at.strftime("%H:%M:%S"))

    # 3. Wait for it to fire (next_run_time goes to None once a one-time job runs)
    waited = 0.0
    while engine.next_run_time("prototype-email") is not None and waited < 15:
        time.sleep(0.5)
        waited += 0.5
    time.sleep(0.5)  # let the job function finish sending

    # 4. Verify delivery
    if received_messages:
        msg = received_messages[0]
        logger.info("SUCCESS -- email delivered to %s", msg["rcpt_tos"])
        print("\n--- Message received by the test SMTP server ---")
        print(msg["content"])
    else:
        logger.error("FAILED -- no message was received by the test SMTP server")

    engine.shutdown()
    controller.stop()


if __name__ == "__main__":
    main()
