from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text, inspect, text

from extensions import db


class ContactLead(db.Model):
    __tablename__ = "contact_leads"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(50))
    subject = Column(String(255), nullable=False, default="New Contact Form")
    message = Column(Text, nullable=False)
    email_sent = Column(Boolean, nullable=False, default=False)
    email_error = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
    )

    __table_args__ = (
        Index("idx_contact_leads_created_at", "created_at"),
        Index("idx_contact_leads_email_sent", "email_sent"),
    )

    def __repr__(self):
        return f"<ContactLead {self.email}>"


def ensure_contact_leads_table():
    ContactLead.__table__.create(bind=db.engine, checkfirst=True)

    inspector = inspect(db.engine)
    existing_columns = {
        column["name"]
        for column in inspector.get_columns(ContactLead.__tablename__)
    }

    column_sql = {
        "name": "ALTER TABLE contact_leads ADD COLUMN IF NOT EXISTS name VARCHAR(120)",
        "email": "ALTER TABLE contact_leads ADD COLUMN IF NOT EXISTS email VARCHAR(255)",
        "phone": "ALTER TABLE contact_leads ADD COLUMN IF NOT EXISTS phone VARCHAR(50)",
        "subject": "ALTER TABLE contact_leads ADD COLUMN IF NOT EXISTS subject VARCHAR(255) DEFAULT 'New Contact Form'",
        "message": "ALTER TABLE contact_leads ADD COLUMN IF NOT EXISTS message TEXT",
        "email_sent": "ALTER TABLE contact_leads ADD COLUMN IF NOT EXISTS email_sent BOOLEAN NOT NULL DEFAULT FALSE",
        "email_error": "ALTER TABLE contact_leads ADD COLUMN IF NOT EXISTS email_error TEXT",
        "created_at": "ALTER TABLE contact_leads ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "ALTER TABLE contact_leads ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
    }
    missing_columns = set(column_sql) - existing_columns

    if not missing_columns:
        return

    with db.engine.begin() as connection:
        for column_name in column_sql:
            if column_name not in missing_columns:
                continue
            connection.execute(text(column_sql[column_name]))
