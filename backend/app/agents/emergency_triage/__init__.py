"""
Emergency Triage Agent package.
Detects life-threatening situations and provides immediate guidance.
Runs exclusively (no parallel execution).
"""

from .agent import EmergencyTriageAgent

__all__ = ["EmergencyTriageAgent"]
