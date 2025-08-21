"""
告警监控引擎
实现定时从Redis获取数据并根据规则进行告警处理
"""

import asyncio
import logging
import redis
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor

from app.core.config import settings
from app.services.alert_rule_service import alert_rule_service
from app.services.alert_service import alert_service
from app.models.alert_rule import AlertRule

logger = logging.getLogger(__name__)


class AlarmMonitor:
    """告警监控引擎"""
    
    def __init__(self):
        self.redis_client = None
        self.is_running = False
        self.monitor_task = None
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.last_check_time = None
        
    def start(self):
        """启动监控"""
        if self.is_running:
            logger.warning("告警监控已在运行")
            return
            
        try:
            # 初始化Redis连接
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                health_check_interval=30
            )
            
            # 测试连接
            self.redis_client.ping()
            logger.info(f"Redis连接成功: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
            
            self.is_running = True
            # 启动异步监控任务
            self.monitor_task = asyncio.create_task(self._monitor_loop())
            logger.info("告警监控引擎启动成功")
            
        except Exception as e:
            logger.error(f"告警监控启动失败: {e}")
            self.redis_client = None
    
    async def stop(self):
        """停止监控"""
        if not self.is_running:
            return
            
        self.is_running = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        if self.redis_client:
            self.redis_client.close()
            
        self.executor.shutdown(wait=True)
        logger.info("告警监控引擎已停止")
    
    async def _monitor_loop(self):
        """主监控循环"""
        logger.info("开始告警监控循环")
        
        while self.is_running:
            try:
                start_time = datetime.now()
                
                # 获取所有启用的规则
                enabled_rules = alert_rule_service.get_all_enabled_rules()
                if not enabled_rules:
                    logger.debug("没有启用的告警规则")
                else:
                    logger.debug(f"监控 {len(enabled_rules)} 条告警规则")
                    
                    # 并发处理规则检查
                    await self._process_rules_concurrent(enabled_rules)
                
                # 记录检查时间
                self.last_check_time = start_time
                processing_time = (datetime.now() - start_time).total_seconds()
                logger.debug(f"告警检查完成，耗时: {processing_time:.2f}秒")
                
                # 等待下一次检查
                await asyncio.sleep(settings.DATA_FETCH_INTERVAL)
                
            except asyncio.CancelledError:
                logger.info("监控循环被取消")
                break
            except Exception as e:
                logger.error(f"监控循环异常: {e}")
                await asyncio.sleep(5)  # 异常时短暂等待
    
    async def _process_rules_concurrent(self, rules: List[AlertRule]):
        """并发处理规则检查"""
        try:
            # 将规则分组以减少Redis连接数
            tasks = []
            for rule in rules:
                task = asyncio.create_task(self._check_single_rule(rule))
                tasks.append(task)
            
            # 等待所有任务完成
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            logger.error(f"并发处理规则异常: {e}")
    
    async def _check_single_rule(self, rule: AlertRule):
        """检查单个规则"""
        try:
            # 从Redis获取数据
            current_value = await self._get_redis_value(rule)
            if current_value is None:
                logger.debug(f"规则 {rule.rule_name} 无法获取数据: {rule.redis_key()}")
                return
            
            # 评估规则
            is_triggered = rule.evaluate(current_value)
            
            # 检查当前是否已有告警
            existing_alert = alert_service.get_alert_by_rule_id(rule.id)
            
            if is_triggered:
                if existing_alert:
                    # 已有告警，更新当前值
                    alert_service.update_alert_value(existing_alert.id, current_value)
                    logger.debug(f"更新告警值: {rule.rule_name}, 当前值: {current_value}")
                else:
                    # 新触发告警
                    alert_id = alert_service.create_alert(rule, current_value)
                    if alert_id:
                        logger.warning(f"触发告警: {rule.rule_name}, 当前值: {current_value}, 阈值: {rule.operator} {rule.value}")
            else:
                if existing_alert:
                    # 告警恢复
                    if alert_service.resolve_alert(existing_alert.id, current_value):
                        logger.info(f"告警恢复: {rule.rule_name}, 当前值: {current_value}")
                
        except Exception as e:
            logger.error(f"检查规则失败 {rule.rule_name}: {e}")
    
    async def _get_redis_value(self, rule: AlertRule) -> Optional[float]:
        """从Redis获取数据值"""
        try:
            redis_key = rule.redis_key()
            point_field = str(rule.point_id)
            
            # 使用线程池执行Redis操作
            loop = asyncio.get_event_loop()
            value_str = await loop.run_in_executor(
                self.executor,
                self._redis_hget,
                redis_key,
                point_field
            )
            
            if value_str is not None:
                try:
                    return float(value_str)
                except (ValueError, TypeError):
                    logger.warning(f"无效的数值格式: {redis_key}:{point_field} = {value_str}")
                    return None
            else:
                logger.debug(f"Redis键不存在或字段为空: {redis_key}:{point_field}")
                return None
                
        except Exception as e:
            logger.error(f"从Redis获取数据失败: {e}")
            return None
    
    def _redis_hget(self, key: str, field: str) -> Optional[str]:
        """Redis HGET操作（同步）"""
        try:
            if self.redis_client:
                return self.redis_client.hget(key, field)
            return None
        except Exception as e:
            logger.error(f"Redis操作失败: {e}")
            return None
    
    async def manual_check_rule(self, rule_id: int) -> Dict[str, Any]:
        """手动检查指定规则"""
        try:
            rule = alert_rule_service.get_rule_by_id(rule_id)
            if not rule:
                return {
                    "success": False,
                    "message": "规则不存在",
                    "data": {}
                }
            
            if not rule.enabled:
                return {
                    "success": False,
                    "message": "规则已禁用",
                    "data": {}
                }
            
            # 获取当前值
            current_value = await self._get_redis_value(rule)
            if current_value is None:
                return {
                    "success": False,
                    "message": "无法从Redis获取数据",
                    "data": {
                        "redis_key": rule.redis_key(),
                        "point_id": rule.point_id
                    }
                }
            
            # 评估规则
            is_triggered = rule.evaluate(current_value)
            existing_alert = alert_service.get_alert_by_rule_id(rule.id)
            
            return {
                "success": True,
                "message": "手动检查完成",
                "data": {
                    "rule_name": rule.rule_name,
                    "current_value": current_value,
                    "threshold_value": rule.value,
                    "operator": rule.operator,
                    "is_triggered": is_triggered,
                    "has_active_alert": existing_alert is not None,
                    "redis_key": rule.redis_key(),
                    "check_time": datetime.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"手动检查规则失败: {e}")
            return {
                "success": False,
                "message": f"检查失败: {str(e)}",
                "data": {}
            }
    
    def on_rule_updated(self, rule_id: int):
        """规则更新时的回调处理"""
        try:
            rule = alert_rule_service.get_rule_by_id(rule_id)
            if not rule:
                return
            
            existing_alert = alert_service.get_alert_by_rule_id(rule_id)
            
            if not rule.enabled and existing_alert:
                # 规则被禁用，解除现有告警
                alert_service.resolve_alerts_by_rule_id(rule_id)
                logger.info(f"规则被禁用，解除相关告警: {rule.rule_name}")
            
            logger.info(f"规则更新处理完成: {rule.rule_name}")
            
        except Exception as e:
            logger.error(f"处理规则更新失败: {e}")
    
    def on_rule_deleted(self, rule_id: int):
        """规则删除时的回调处理"""
        try:
            # 解除该规则的所有告警
            count = alert_service.resolve_alerts_by_rule_id(rule_id)
            logger.info(f"规则删除，解除了 {count} 条相关告警")
            
        except Exception as e:
            logger.error(f"处理规则删除失败: {e}")
    
    def get_monitor_status(self) -> Dict[str, Any]:
        """获取监控状态"""
        try:
            redis_status = "disconnected"
            if self.redis_client:
                try:
                    self.redis_client.ping()
                    redis_status = "connected"
                except:
                    redis_status = "error"
            
            return {
                "running": self.is_running,
                "redis_status": redis_status,
                "last_check_time": self.last_check_time.isoformat() if self.last_check_time else None,
                "check_interval": settings.DATA_FETCH_INTERVAL,
                "redis_config": {
                    "host": settings.REDIS_HOST,
                    "port": settings.REDIS_PORT,
                    "db": settings.REDIS_DB
                }
            }
            
        except Exception as e:
            logger.error(f"获取监控状态失败: {e}")
            return {
                "running": False,
                "redis_status": "error",
                "error": str(e)
            }


# 创建全局监控实例
alarm_monitor = AlarmMonitor()
