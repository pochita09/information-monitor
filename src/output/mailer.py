import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"


def _time_label(hour: int) -> str:
    if 5 <= hour < 11:
        return "朝"
    if 11 <= hour < 17:
        return "昼"
    return "夜"


def send_email(theme_results: list[dict]) -> None:
    """選別済み記事をまとめてHTML形式でGmail送信する。"""
    now = datetime.now()
    total = sum(len(r["articles"]) for r in theme_results)
    high_count = sum(
        sum(1 for a in r["articles"] if a.get("importance") == "高")
        for r in theme_results
    )

    subject = (
        f"【AI情報】{now.month}/{now.day} {_time_label(now.hour)} "
        f"新着{total}件（重要度・高{high_count}件）"
    )

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    template = env.get_template("email.html")
    html_body = template.render(
        theme_results=theme_results,
        generated_at=now.strftime("%Y-%m-%d %H:%M"),
        total=total,
        high_count=high_count,
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = os.environ["MAIL_FROM"]
    msg["To"] = os.environ["MAIL_TO"]
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(os.environ["MAIL_FROM"], os.environ["MAIL_APP_PASSWORD"])
        server.send_message(msg)
