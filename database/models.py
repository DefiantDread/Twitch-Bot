# database/models.py
from sqlalchemy import Float, create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Index, func
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    twitch_id = Column(String, unique=True, nullable=False)
    username = Column(String, nullable=False)
    is_mod = Column(Boolean, default=False)
    is_subscriber = Column(Boolean, default=False)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_users_twitch_id', twitch_id),
        Index('idx_users_status', is_mod, is_subscriber),
        Index('idx_users_activity', last_seen, username),
    )

class CustomCommand(Base):
    __tablename__ = 'custom_commands'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    response = Column(String, nullable=False)
    permission_level = Column(String, default='everyone')
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_commands_lookup', name, enabled),
        Index('idx_commands_permission', permission_level, enabled),
    )

class StreamStats(Base):
    __tablename__ = 'stream_stats'
    
    id = Column(Integer, primary_key=True)
    stream_date = Column(DateTime, default=datetime.utcnow)
    peak_viewers = Column(Integer, default=0)
    stream_duration = Column(Integer, default=0)
    messages_sent = Column(Integer, default=0)
    
    __table_args__ = (
        Index('idx_stats_date', stream_date),
        Index('idx_stats_metrics', stream_date, peak_viewers, messages_sent),
    )

class BannedPhrase(Base):
    __tablename__ = 'banned_phrases'
    
    id = Column(Integer, primary_key=True)
    phrase = Column(String, nullable=False, unique=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String)
    
    __table_args__ = (
        Index('idx_banned_phrases_lookup', phrase, enabled),
    )

class Command(Base):
    __tablename__ = 'commands'

    name = Column(String, primary_key=True)
    response = Column(String, nullable=False)

class UserPoints(Base):
    __tablename__ = 'user_points'
    
    user_id = Column(String, primary_key=True)
    points = Column(Integer, default=0)
    total_earned = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)
    streak_days = Column(Integer, default=0)
    last_daily = Column(DateTime)

    __table_args__ = (
        Index('idx_points_leaderboard', points.desc()),
    )

class RaidHistory(Base):
    __tablename__ = 'raid_history'
    
    id = Column(Integer, primary_key=True)
    start_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_time = Column(DateTime)
    ship_type = Column(String, nullable=False)
    viewer_count = Column(Integer, nullable=False)
    required_crew = Column(Integer, nullable=False)
    final_crew = Column(Integer, nullable=False)
    final_multiplier = Column(Float, nullable=False)
    total_plunder = Column(Integer, nullable=False)
    
    __table_args__ = (
        Index('idx_raid_history_time', 'start_time'),
    )

class RaidParticipant(Base):
    __tablename__ = 'raid_participants'
    
    raid_id = Column(Integer, ForeignKey('raid_history.id'), primary_key=True)
    user_id = Column(String, ForeignKey('users.twitch_id'), primary_key=True)
    initial_investment = Column(Integer, nullable=False)
    final_investment = Column(Integer, nullable=False)
    reward = Column(Integer, nullable=False)
    
    __table_args__ = (
        Index('idx_raid_participants_user', 'user_id'),
    )

class PlayerRaidStats(Base):
    __tablename__ = 'player_raid_stats'
    
    user_id = Column(String, ForeignKey('users.twitch_id'), primary_key=True)
    total_raids = Column(Integer, default=0)
    successful_raids = Column(Integer, default=0)
    total_invested = Column(Integer, default=0)
    total_plunder = Column(Integer, default=0)
    biggest_reward = Column(Integer, default=0)
    
    __table_args__ = (
        Index('idx_player_stats_plunder', 'total_plunder', postgresql_using='btree'),
    )