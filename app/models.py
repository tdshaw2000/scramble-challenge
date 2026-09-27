import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Enum, ForeignKey, String, Text, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


def utcnow() -> datetime:
    return datetime.now(UTC)


def enum_column(enum_cls: type[enum.Enum]) -> Enum:
    # Store the lowercase values from SPEC.md, as plain strings (no native enum in SQLite).
    return Enum(
        enum_cls,
        native_enum=False,
        values_callable=lambda cls: [member.value for member in cls],
        length=20,
    )


class ChallengeStatus(enum.StrEnum):
    WAITING = "waiting"
    ROUND_ACTIVE = "round_active"
    ROUND_RESULTS = "round_results"
    ENDED = "ended"  # the CO ended it, or has gone for good


class RoundStatus(enum.StrEnum):
    ACTIVE = "active"
    COMPLETE = "complete"


class SolveResult(enum.StrEnum):
    OK = "ok"
    DNF = "dnf"


class Challenge(db.Model):
    __tablename__ = "challenges"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(32), unique=True)
    # Nullable because the CO Player row can only exist once the Challenge does.
    co_player_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("players.id", use_alter=True, name="fk_challenges_co_player_id")
    )
    status: Mapped[ChallengeStatus] = mapped_column(
        enum_column(ChallengeStatus), default=ChallengeStatus.WAITING
    )
    current_round_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rounds.id", use_alter=True, name="fk_challenges_current_round_id")
    )
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    # When the CO's last connection closed; cleared when they come back.
    co_left_at: Mapped[datetime | None]

    players: Mapped[list["Player"]] = relationship(
        back_populates="challenge", foreign_keys="Player.challenge_id", order_by="Player.joined_at"
    )
    co_player: Mapped["Player | None"] = relationship(foreign_keys=[co_player_id], post_update=True)
    rounds: Mapped[list["Round"]] = relationship(
        back_populates="challenge", foreign_keys="Round.challenge_id", order_by="Round.round_number"
    )
    current_round: Mapped["Round | None"] = relationship(
        foreign_keys=[current_round_id], post_update=True
    )


class Player(db.Model):
    __tablename__ = "players"
    __table_args__ = (UniqueConstraint("challenge_id", "cookie_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    challenge_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("challenges.id"))
    cookie_id: Mapped[str] = mapped_column(String(64))
    display_name: Mapped[str] = mapped_column(String(50))
    is_co: Mapped[bool] = mapped_column(default=False)
    connected: Mapped[bool] = mapped_column(default=False)
    joined_at: Mapped[datetime] = mapped_column(default=utcnow)

    challenge: Mapped[Challenge] = relationship(
        back_populates="players", foreign_keys=[challenge_id]
    )


class Round(db.Model):
    __tablename__ = "rounds"
    __table_args__ = (UniqueConstraint("challenge_id", "round_number"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    challenge_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("challenges.id"))
    round_number: Mapped[int]
    puzzle: Mapped[str] = mapped_column(String(20))
    scramble_text: Mapped[str] = mapped_column(Text)
    scramble_svg: Mapped[str] = mapped_column(Text)
    status: Mapped[RoundStatus] = mapped_column(
        enum_column(RoundStatus), default=RoundStatus.ACTIVE
    )
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    ended_at: Mapped[datetime | None]

    challenge: Mapped[Challenge] = relationship(
        back_populates="rounds", foreign_keys=[challenge_id]
    )
    solves: Mapped[list["Solve"]] = relationship(back_populates="round")


class Solve(db.Model):
    __tablename__ = "solves"
    __table_args__ = (UniqueConstraint("round_id", "player_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    round_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rounds.id"))
    player_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("players.id"))
    time_ms: Mapped[int | None]
    # None while the solve is in progress; set to ok or dnf once it has an outcome.
    result: Mapped[SolveResult | None] = mapped_column(enum_column(SolveResult))
    # WCA inspection: the solve started between 15 and 17 seconds in, so 2 seconds are added
    # when it counts. time_ms stays the time as timed.
    plus_two: Mapped[bool] = mapped_column(default=False, server_default=false())
    started_inspection_at: Mapped[datetime | None]
    started_solve_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]

    round: Mapped[Round] = relationship(back_populates="solves")
    player: Mapped[Player] = relationship()
