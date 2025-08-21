"""
告警规则数据模型
定义alert_rule表的数据结构和操作方法
"""

import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class WarningLevel(Enum):
    """告警级别枚举"""
    LOW = 1      # 低级告警
    MEDIUM = 2   # 中级告警
    HIGH = 3     # 高级告警


class ComparisonOperator(Enum):
    """比较操作符枚举"""
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    EQUAL = "=="
    NOT_EQUAL = "!="


class ServiceType(Enum):
    """服务类型枚举"""
    COMSRV = "comsrv"      # 通信服务
    RULESRV = "rulesrv"    # 规则服务
    MODSRV = "modsrv"      # 模型服务
    ALARMSRV = "alarmsrv"  # 告警服务
    HISSRV = "hissrv"      # 历史服务
    NETSRV = "netsrv"      # 网络服务


class DataType(Enum):
    """数据类型枚举"""
    TELEMETRY = "T"  # 遥测
    SIGNAL = "S"     # 遥信
    CONTROL = "C"    # 遥控
    ADJUSTMENT = "A" # 遥调


@dataclass
class AlertRule:
    """告警规则数据类"""
    id: Optional[int] = None
    service_type: str = "comsrv"  # 服务类型：comsrv, rulesrv, modsrv等
    channel_id: int = None
    data_type: str = None  # T, S, C, A
    point_id: int = None
    rule_name: str = ""
    warning_level: int = 1
    operator: str = ">"
    value: float = 0.0
    enabled: bool = True
    description: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "service_type": self.service_type,
            "channel_id": self.channel_id,
            "data_type": self.data_type,
            "point_id": self.point_id,
            "rule_name": self.rule_name,
            "warning_level": self.warning_level,
            "operator": self.operator,
            "value": self.value,
            "enabled": self.enabled,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AlertRule":
        """从字典创建实例"""
        return cls(
            id=data.get("id"),
            service_type=data.get("service_type", "comsrv"),
            channel_id=data.get("channel_id"),
            data_type=data.get("data_type"),
            point_id=data.get("point_id"),
            rule_name=data.get("rule_name", ""),
            warning_level=data.get("warning_level", 1),
            operator=data.get("operator", ">"),
            value=data.get("value", 0.0),
            enabled=data.get("enabled", True),
            description=data.get("description", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
        )

    def redis_key(self) -> str:
        """生成对应的Redis键"""
        return f"{self.service_type}:{self.channel_id}:{self.data_type}"

    def validate(self) -> bool:
        """验证规则有效性"""
        if not self.service_type or self.service_type.strip() == "":
            return False
            
        # 暂时只支持这些服务类型
        valid_services = ["comsrv", "rulesrv", "modsrv", "alarmsrv", "hissrv", "netsrv"]
        if self.service_type not in valid_services:
            return False
        
        if not self.channel_id or self.channel_id <= 0:
            return False
        
        if self.data_type not in ["T", "S", "C", "A"]:
            return False
            
        if not self.point_id or self.point_id <= 0:
            return False
            
        if not self.rule_name or self.rule_name.strip() == "":
            return False
            
        if self.warning_level not in [1, 2, 3]:
            return False
            
        if self.operator not in [">", "<", ">=", "<=", "==", "!="]:
            return False
            
        return True

    def evaluate(self, current_value: float) -> bool:
        """评估规则是否触发"""
        if not self.enabled:
            return False
            
        try:
            current_value = float(current_value)
            threshold = float(self.value)
            
            if self.operator == ">":
                return current_value > threshold
            elif self.operator == "<":
                return current_value < threshold
            elif self.operator == ">=":
                return current_value >= threshold
            elif self.operator == "<=":
                return current_value <= threshold
            elif self.operator == "==":
                return abs(current_value - threshold) < 1e-6  # 浮点数比较
            elif self.operator == "!=":
                return abs(current_value - threshold) >= 1e-6
                
        except (ValueError, TypeError):
            return False
            
        return False
