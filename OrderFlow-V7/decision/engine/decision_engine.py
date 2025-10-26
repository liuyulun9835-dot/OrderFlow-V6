"""V7 决策引擎

- 以 clarity 与 transition 概率映射仓位；
- respect 900s 冷却；
- 如果 prototype_drift 或校准门控失败则直接 abstain。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class DecisionContext:
    transition_prob: float
    clarity: float
    prototype_drift: float
    gates_passed: bool
    last_action_ts: Optional[datetime] = None
    threshold: float = 0.75
    cooldown: timedelta = timedelta(seconds=900)


@dataclass
class DecisionResult:
    action: str
    size: float
    reason: str
    abstain: bool


def map_clarity_to_size(clarity: float) -> float:
    if clarity < 0.55:
        return 0.0
    if clarity < 0.7:
        return 0.33
    if clarity < 0.85:
        return 0.66
    return 1.0


def cooldown_active(context: DecisionContext, now: datetime) -> bool:
    if context.last_action_ts is None:
        return False
    return now - context.last_action_ts < context.cooldown


def decide(context: DecisionContext, now: Optional[datetime] = None) -> DecisionResult:
    now = now or datetime.utcnow()
    if context.prototype_drift >= 0.15:
        return DecisionResult(action="abstain", size=0.0, reason="prototype drift breached", abstain=True)
    if not context.gates_passed:
        return DecisionResult(action="abstain", size=0.0, reason="validation gates failed", abstain=True)
    if cooldown_active(context, now):
        return DecisionResult(action="hold", size=0.0, reason="cooldown active", abstain=False)
    if context.transition_prob < context.threshold:
        return DecisionResult(action="hold", size=0.0, reason="transition prob below threshold", abstain=False)

    size = map_clarity_to_size(context.clarity)
    if size == 0.0:
        return DecisionResult(action="abstain", size=0.0, reason="clarity below floor", abstain=True)

    return DecisionResult(action="enter", size=size, reason="clarity-driven sizing", abstain=False)


__all__ = ["DecisionContext", "DecisionResult", "decide"]
