from __future__ import annotations
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, DateTime, Text, ForeignKey, UniqueConstraint
from datetime import datetime

db = SQLAlchemy()

class Partner(db.Model):
    __tablename__ = "partners"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    vehicles: Mapped[list['Vehicle']] = relationship('Vehicle', back_populates='partner', cascade='all, delete-orphan')

class Vehicle(db.Model):
    __tablename__ = "vehicles"
    __table_args__ = (
        # Enforce uniqueness per partner
        UniqueConstraint("partner_id", "vin", name="uq_vehicle_partner_vin"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    partner_id: Mapped[int] = mapped_column(ForeignKey("partners.id"), nullable=False)
    vin: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    make: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(64))
    year: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    partner: Mapped['Partner'] = relationship('Partner', back_populates='vehicles')
    reports: Mapped[list['VehicleReport']] = relationship('VehicleReport', back_populates='vehicle', cascade='all, delete-orphan')

class VehicleReport(db.Model):
    __tablename__ = "vehicle_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    raw_log_json: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text)
    vehicle: Mapped['Vehicle'] = relationship('Vehicle', back_populates='reports')
