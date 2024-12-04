# features/raids/message_handler.py

import random
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class RaidMessageHandler:
    def __init__(self):
        self.raid_start_messages = [
            "Sails on the horizon! {ship_type} spotted bearing {direction}!",
            "Lookout reports a {ship_type} flying {nation} colors!",
            "Through the spyglass: A wealthy {ship_type} has strayed from its escort!",
            "The fog parts to reveal a {ship_type} heavy in the water with cargo!",
            "A {ship_type} has run aground on the reef - easy pickings!",
            "Storm's scattered a convoy - lone {ship_type} at our mercy!"
        ]

        self.crew_join_messages = [
            "{user} throws their lot in with the crew! ({current}/{needed})",
            "{user} signs on for the raid! ({current}/{needed})",
            "{user} takes up arms with the crew! ({current}/{needed})",
            "Yarr! {user} joins the boarding party! ({current}/{needed})",
            "{user} sharpens their cutlass and joins! ({current}/{needed})",
            "{user} checks their powder and joins up! ({current}/{needed})"
        ]

        self.milestone_messages = [
            "By the stars! The {ship_type} is carrying more than we thought!",
            "She's flying the royal flag - this'll be a rich haul!",
            "Look at the size of those cargo holds! Who's up for a bigger share?",
            "That's no ordinary merchant - she's a treasure ship!",
            "The crew spots additional escort ships - but the prize just got bigger!"
        ]

        self.success_messages = [
            "Victory! The {ship_type} strikes her colors!",
            "The cargo's ours! Time to divvy up the spoils!",
            "A clean sweep! Not a single coin left in her holds!",
            "Another successful raid! The crew's reputation grows!",
            "The {ship_type} is ours! Even the captain's parrot surrendered!"
        ]

        self.weather_conditions = [
            "Calm seas and clear skies - perfect raiding weather!",
            "Fog rolling in - we'll catch them unawares!",
            "Storm's brewing, but that's never stopped us before!",
            "High tide's in our favor - full speed ahead!",
            "The moon's hidden by clouds - perfect for a night raid!"
        ]

        self.compass_directions = ["north", "south", "east", "west", "northwest", "northeast", "southwest", "southeast"]
        self.nations = ["Spanish", "Portuguese", "Dutch", "French", "English", "Venetian"]

    def get_raid_start_message(self, ship_type: str) -> str:
        """Generate raid start message"""
        return random.choice(self.raid_start_messages).format(
            ship_type=ship_type,
            direction=random.choice(self.compass_directions),
            nation=random.choice(self.nations)
        )

    def get_crew_join_message(self, username: str, current: int, needed: int) -> str:
        """Generate crew join message"""
        return random.choice(self.crew_join_messages).format(
            user=username,
            current=current,
            needed=needed
        )

    def get_milestone_message(self, ship_type: str, multiplier: float) -> str:
        """Generate milestone message"""
        base_message = random.choice(self.milestone_messages).format(ship_type=ship_type)
        return f"{base_message} (Reward multiplier now {multiplier}x!)"

    def get_success_message(self, ship_type: str, total_crew: int, total_plunder: int) -> str:
        """Generate success message"""
        base_message = random.choice(self.success_messages).format(ship_type=ship_type)
        return f"{base_message} {total_crew} crew members share {total_plunder} points!"

    def get_weather_condition(self) -> str:
        """Get random weather condition"""
        return random.choice(self.weather_conditions)