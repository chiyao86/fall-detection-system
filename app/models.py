from datetime import datetime

import pytz

from app.extensions import db

TZ = pytz.timezone("Asia/Taipei")


class FallEvent(db.Model):
    """跌倒事件紀錄"""

    __tablename__ = "fall_events"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(TZ))
    filename = db.Column(db.String(512), nullable=False)
    image_path = db.Column(db.String(1024), nullable=False)
    fall_detected = db.Column(db.Boolean, default=False)
    confidence = db.Column(db.String(20), default="low")  # low / medium / high
    description = db.Column(db.Text, default="")
    needs_immediate_attention = db.Column(db.Boolean, default=False)
    notified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(TZ))

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.timestamp else None,
            "filename": self.filename,
            "image_path": self.image_path,
            "fall_detected": self.fall_detected,
            "confidence": self.confidence,
            "description": self.description,
            "needs_immediate_attention": self.needs_immediate_attention,
            "notified": self.notified,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }
