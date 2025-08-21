"""
告警服务主入口文件
实现FastAPI应用程序和数据库初始化
"""

import logging
import sys
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from datetime import datetime
import uvicorn

from app.core.config import settings
from app.core.database import init_database
from app.services.alert_rule_service import alert_rule_service
from app.models.alert_rule import AlertRule

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="工业物联网告警服务 - 监控和管理告警规则",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化操作"""
    logger.info("启动告警服务...")
    
    # 初始化数据库
    logger.info("初始化数据库...")
    success = init_database()
    if not success:
        logger.error("数据库初始化失败！")
        sys.exit(1)
    
    logger.info("数据库初始化成功")
    
    # 记录服务启动信息
    logger.info(f"告警服务启动成功")
    logger.info(f"数据库路径: {settings.DATABASE_PATH}")
    logger.info(f"Redis连接: {settings.REDIS_HOST}:{settings.REDIS_PORT}")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的清理操作"""
    logger.info("关闭告警服务...")


@app.get("/")
async def root():
    """根路径"""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "database": settings.DATABASE_PATH,
    }


@app.get("/health")
async def health_check():
    """健康检查接口"""
    try:
        # 检查数据库连接
        rule_count = alert_rule_service.get_rule_count()
        enabled_count = alert_rule_service.get_enabled_rule_count()
        
        return {
            "status": "healthy",
            "database": "connected",
            "rules": {
                "total": rule_count,
                "enabled": enabled_count
            }
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        raise HTTPException(status_code=500, detail="Service unhealthy")


# 告警规则API端点
@app.post("/alarmApi/rules", response_model=dict)
async def create_alert_rule(rule_data: dict):
    """创建告警规则"""
    try:
        # 验证必需字段
        required_fields = ["channel_id", "data_type", "point_id", "rule_name", "warning_level", "operator", "value"]
        for field in required_fields:
            if field not in rule_data:
                return {
                    "success": False,
                    "message": f"缺少必需字段: {field}",
                    "data": {}
                }
        
        # 创建AlertRule对象
        rule = AlertRule.from_dict(rule_data)
        
        # 验证规则
        if not rule.validate():
            return {
                "success": False,
                "message": "规则验证失败",
                "data": {}
            }
        
        # 创建规则
        rule_id = alert_rule_service.create_rule(rule)
        if rule_id:
            return {
                "success": True,
                "message": "告警规则创建成功",
                "data": {"rule_id": rule_id}
            }
        else:
            return {
                "success": False,
                "message": "创建规则失败",
                "data": {}
            }
            
    except Exception as e:
        logger.error(f"创建告警规则失败: {e}")
        return {
            "success": False,
            "message": f"创建失败: {str(e)}",
            "data": {}
        }


@app.get("/alarmApi/rules/{rule_id}")
async def get_alert_rule(rule_id: int):
    """获取指定ID的告警规则"""
    try:
        rule = alert_rule_service.get_rule_by_id(rule_id)
        if rule:
            return {
                "success": True,
                "message": "获取规则成功",
                "data": {
                    "total": 1,
                    "list": [rule.to_dict()]
                }
            }
        else:
            return {
                "success": False,
                "message": "规则不存在",
                "data": {
                    "total": 0,
                    "list": []
                }
            }
            
    except Exception as e:
        logger.error(f"获取告警规则失败: {e}")
        return {
            "success": False,
            "message": f"获取失败: {str(e)}",
            "data": {
                "total": 0,
                "list": []
            }
        }


@app.get("/alarmApi/rules")
async def list_alert_rules(
    keyword: str = Query("", description="关键词搜索，支持规则名称、描述、通道ID、点位ID"),
    service_type: str = Query("", description="服务类型过滤：comsrv, rulesrv, modsrv等"),
    warning_level: Optional[int] = Query(None, description="告警级别过滤：1=低级, 2=中级, 3=高级"),
    enabled: Optional[bool] = Query(None, description="启用状态过滤"),
    start_time: Optional[str] = Query(None, description="开始时间，格式：YYYY-MM-DD HH:MM:SS"),
    end_time: Optional[str] = Query(None, description="结束时间，格式：YYYY-MM-DD HH:MM:SS"),
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(10, ge=1, le=100, description="每页大小，最大100")
):
    """高级搜索告警规则列表"""
    try:
        # 时间参数转换
        start_datetime = None
        end_datetime = None
        
        if start_time:
            try:
                start_datetime = datetime.fromisoformat(start_time.replace(' ', 'T'))
            except ValueError:
                return {
                    "success": False,
                    "message": "开始时间格式错误，请使用：YYYY-MM-DD HH:MM:SS",
                    "data": {"total": 0, "list": []}
                }
        
        if end_time:
            try:
                end_datetime = datetime.fromisoformat(end_time.replace(' ', 'T'))
            except ValueError:
                return {
                    "success": False,
                    "message": "结束时间格式错误，请使用：YYYY-MM-DD HH:MM:SS",
                    "data": {"total": 0, "list": []}
                }
        
        # 执行搜索
        result = alert_rule_service.search_rules(
            keyword=keyword,
            service_type=service_type,
            warning_level=warning_level,
            enabled=enabled,
            start_time=start_datetime,
            end_time=end_datetime,
            page=page,
            page_size=page_size
        )
        
        return result
        
    except Exception as e:
        logger.error(f"获取告警规则列表失败: {e}")
        return {
            "success": False,
            "message": f"查询失败: {str(e)}",
            "data": {"total": 0, "list": []}
        }


@app.get("/alarmApi/rules/channel/{channel_id}")
async def get_channel_rules(
    channel_id: int,
    service_type: str = Query("", description="服务类型，如：comsrv")
):
    """获取指定通道的告警规则"""
    try:
        if service_type:
            # 如果指定了服务类型，使用更精确的搜索
            result = alert_rule_service.search_rules(
                keyword=str(channel_id),
                service_type=service_type,
                page=1,
                page_size=100
            )
        else:
            rules = alert_rule_service.get_rules_by_channel(channel_id)
            result = {
                "success": True,
                "message": f"查询成功，共找到 {len(rules)} 条记录",
                "data": {
                    "total": len(rules),
                    "list": [rule.to_dict() for rule in rules]
                }
            }
        
        return result
        
    except Exception as e:
        logger.error(f"获取通道告警规则失败: {e}")
        return {
            "success": False,
            "message": f"查询失败: {str(e)}",
            "data": {"total": 0, "list": []}
        }


@app.put("/alarmApi/rules/{rule_id}")
async def update_alert_rule(rule_id: int, rule_data: dict):
    """更新告警规则"""
    try:
        # 确保规则ID正确
        rule_data["id"] = rule_id
        
        # 创建AlertRule对象
        rule = AlertRule.from_dict(rule_data)
        
        # 更新规则
        success = alert_rule_service.update_rule(rule)
        if success:
            return {
                "success": True,
                "message": "告警规则更新成功",
                "data": {"rule_id": rule_id}
            }
        else:
            return {
                "success": False,
                "message": "规则不存在或更新失败",
                "data": {}
            }
            
    except Exception as e:
        logger.error(f"更新告警规则失败: {e}")
        return {
            "success": False,
            "message": f"更新失败: {str(e)}",
            "data": {}
        }


@app.delete("/alarmApi/rules/{rule_id}")
async def delete_alert_rule(rule_id: int):
    """删除告警规则"""
    try:
        success = alert_rule_service.delete_rule(rule_id)
        if success:
            return {
                "success": True,
                "message": "告警规则删除成功",
                "data": {"rule_id": rule_id}
            }
        else:
            return {
                "success": False,
                "message": "规则不存在",
                "data": {}
            }
            
    except Exception as e:
        logger.error(f"删除告警规则失败: {e}")
        return {
            "success": False,
            "message": f"删除失败: {str(e)}",
            "data": {}
        }


@app.patch("/alarmApi/rules/{rule_id}/enable")
async def enable_alert_rule(rule_id: int):
    """启用告警规则"""
    try:
        success = alert_rule_service.enable_rule(rule_id)
        if success:
            return {
                "success": True,
                "message": "告警规则启用成功",
                "data": {"rule_id": rule_id}
            }
        else:
            return {
                "success": False,
                "message": "规则不存在",
                "data": {}
            }
            
    except Exception as e:
        logger.error(f"启用告警规则失败: {e}")
        return {
            "success": False,
            "message": f"启用失败: {str(e)}",
            "data": {}
        }


@app.patch("/alarmApi/rules/{rule_id}/disable")
async def disable_alert_rule(rule_id: int):
    """禁用告警规则"""
    try:
        success = alert_rule_service.disable_rule(rule_id)
        if success:
            return {
                "success": True,
                "message": "告警规则禁用成功",
                "data": {"rule_id": rule_id}
            }
        else:
            return {
                "success": False,
                "message": "规则不存在",
                "data": {}
            }
            
    except Exception as e:
        logger.error(f"禁用告警规则失败: {e}")
        return {
            "success": False,
            "message": f"禁用失败: {str(e)}",
            "data": {}
        }


if __name__ == "__main__":
    # 确保日志目录存在
    log_dir = Path(settings.LOG_FILE).parent
    if not log_dir.exists():
        log_dir.mkdir(parents=True, exist_ok=True)
    
    # 启动服务
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
