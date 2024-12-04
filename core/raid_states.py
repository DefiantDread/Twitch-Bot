# raid_states.py
from enum import Enum, auto
from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

class RaidState(Enum):
    INACTIVE = auto()
    RECRUITING = auto()
    MILESTONE = auto()
    LAUNCHING = auto()
    ACTIVE = auto()
    COMPLETED = auto()

@dataclass
class RaidMilestone:
    participant_count: int
    multiplier: float
    description: str

@dataclass
class Participant:
    username: str
    initial_investment: int
    total_investment: int
    join_time: datetime

class RaidInstance:
    def __init__(
        self,
        ship_type: str,
        required_crew: int,
        viewer_count: int,
        base_multiplier: float = 1.5
    ):
        self.start_time = datetime.now(timezone.utc)
        self.ship_type = ship_type
        self.required_crew = required_crew
        self.viewer_count = viewer_count
        self.base_multiplier = base_multiplier
        self.current_multiplier = base_multiplier
        self.participants: Dict[str, Participant] = {}
        self.state = RaidState.RECRUITING
        self.milestones: List[RaidMilestone] = []
        self._setup_milestones()
    
    def _setup_milestones(self):
        """Setup raid milestones based on viewer count"""
        if self.viewer_count < 10:
            self.milestones = [
                RaidMilestone(3, 1.8, "Crew growing stronger!"),
                RaidMilestone(5, 2.0, "Full crew assembled!")
            ]
        else:
            participant_threshold = max(3, int(self.viewer_count * 0.1))
            self.milestones = [
                RaidMilestone(
                    participant_threshold, 
                    1.8, 
                    "Initial crew assembled!"
                ),
                RaidMilestone(
                    int(participant_threshold * 1.5), 
                    2.0, 
                    "Strong crew formed!"
                ),
                RaidMilestone(
                    int(participant_threshold * 2), 
                    2.5, 
                    "Legendary crew ready!"
                )
            ]

    def add_participant(self, user_id: str, username: str, investment: int) -> bool:
        """Add a participant to the raid"""
        if self.state not in [RaidState.RECRUITING, RaidState.MILESTONE]:
            return False
            
        if user_id in self.participants:
            return False
            
        self.participants[user_id] = Participant(
            username=username,
            initial_investment=investment,
            total_investment=investment,
            join_time=datetime.now(timezone.utc)
        )
        
        return True

    def increase_investment(self, user_id: str, additional: int) -> bool:
        """Increase a participant's investment"""
        if self.state != RaidState.MILESTONE:
            return False
            
        if user_id not in self.participants:
            return False
            
        participant = self.participants[user_id]
        if participant.total_investment + additional > 2000:
            return False
            
        participant.total_investment += additional
        return True

    def check_milestone(self) -> Optional[RaidMilestone]:
        """Check if a new milestone has been reached"""
        participant_count = len(self.participants)
        
        for milestone in self.milestones:
            if (participant_count >= milestone.participant_count and 
                milestone.multiplier > self.current_multiplier):
                self.current_multiplier = milestone.multiplier
                return milestone
                
        return None

    def get_status(self) -> Dict:
        """Get current raid status"""
        return {
            'state': self.state,
            'ship_type': self.ship_type,
            'required_crew': self.required_crew,
            'current_crew': len(self.participants),
            'multiplier': self.current_multiplier,
            'total_investment': sum(
                p.total_investment for p in self.participants.values()
            ),
            'time_elapsed': (
                datetime.now(timezone.utc) - self.start_time
            ).total_seconds(),
            'next_milestone': next(
                (m for m in self.milestones 
                 if len(self.participants) < m.participant_count),
                None
            )
        }

    def get_rewards(self) -> Dict[str, int]:
        """Calculate rewards for all participants"""
        return {
            user_id: int(participant.total_investment * self.current_multiplier)
            for user_id, participant in self.participants.items()
        }

    def is_successful(self) -> bool:
        """Check if raid meets success criteria"""
        return len(self.participants) >= self.required_crew