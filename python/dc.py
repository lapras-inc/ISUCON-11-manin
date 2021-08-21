from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class Isu:
    id: int
    jia_isu_uuid: int
    name: str
    image: bytes
    character: str
    jia_user_id: str
    created_at: datetime
    updated_at: datetime


@dataclass
class IsuCondition:
    id: int
    jia_isu_uuid: str
    timestamp: datetime
    is_sitting: bool
    condition: str
    message: str
    created_at: datetime

    def __post_init__(self):
        if type(self.is_sitting) is int:
            self.is_sitting = bool(self.is_sitting)
        if type(self.timestamp) is datetime:
            self.timestamp = self.timestamp.astimezone(TZ)
        if type(self.created_at) is datetime:
            self.created_at = self.created_at.astimezone(TZ)


@dataclass
class ConditionsPercentage:
    sitting: int
    is_broken: int
    is_dirty: int
    is_overweight: int


@dataclass
class GraphDataPoint:
    score: int
    percentage: ConditionsPercentage


@dataclass
class GraphDataPointWithInfo:
    jia_isu_uuid: str
    start_at: datetime
    data: GraphDataPoint
    condition_timestamps: list[int]


@dataclass
class GraphResponse:
    start_at: int
    end_at: int
    data: GraphDataPoint
    condition_timestamps: list[int]


@dataclass
class GetIsuConditionResponse:
    jia_isu_uuid: str
    isu_name: str
    timestamp: int
    is_sitting: bool
    condition: str
    condition_level: str
    message: str


@dataclass
class GetIsuListResponse:
    id: int
    jia_isu_uuid: str
    name: str
    character: str
    latest_isu_condition: GetIsuConditionResponse


@dataclass
class TrendCondition:
    isu_id: int
    timestamp: int


@dataclass
class TrendResponse:
    character: str
    info: list[TrendCondition]
    warning: list[TrendCondition]
    critical: list[TrendCondition]


@dataclass
class PostIsuConditionRequest:
    is_sitting: bool
    condition: str
    message: str
    timestamp: int
