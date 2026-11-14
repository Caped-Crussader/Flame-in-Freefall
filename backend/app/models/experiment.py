"""DB model for a microgravity combustion experiment record."""
from sqlalchemy import String, Float, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))          # e.g. FLEX, SoFIE, BASS, ACME, Saffire
    platform: Mapped[str | None] = mapped_column(String(100))  # ISS, drop tower, Cygnus...
    fuel: Mapped[str | None] = mapped_column(String(100))
    oxygen_pct: Mapped[float | None] = mapped_column(Float)
    pressure_kpa: Mapped[float | None] = mapped_column(Float)
    flow_velocity_cms: Mapped[float | None] = mapped_column(Float)
    flame_spread_rate: Mapped[float | None] = mapped_column(Float)
    extinction: Mapped[str | None] = mapped_column(String(50))
    summary: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(500))
