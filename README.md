# 告警服务 (Alarm Service)

基于Python 3.10.12的工业物联网告警服务，提供实时告警规则配置和管理功能。

## 功能特性

### 🔧 核心功能
- **告警规则管理**: 支持创建、查询、更新、删除告警规则
- **数据库自动初始化**: 程序启动时自动创建SQLite数据库和表结构
- **WAL模式**: 启用Write-Ahead Logging，提升数据库并发性能
- **规则验证**: 实时验证告警规则的有效性和触发条件
- **RESTful API**: 提供完整的HTTP API接口

### 📊 告警规则字段
- **channel_id**: 通信服务通道ID
- **data_type**: 数据类型 (T=遥测, S=遥信, C=遥控, A=遥调)
- **point_id**: 数据点位ID
- **rule_name**: 规则名称
- **warning_level**: 告警级别 (1=低级, 2=中级, 3=高级)
- **operator**: 比较操作符 (>, <, >=, <=, ==, !=)
- **value**: 阈值
- **enabled**: 规则启用状态
- **description**: 规则描述

## 项目结构

```
alarmsrv/
├── app/                        # 应用核心代码
│   ├── core/                   # 核心模块
│   │   ├── config.py          # 配置管理
│   │   └── database.py        # 数据库管理
│   ├── models/                 # 数据模型
│   │   ├── __init__.py
│   │   └── alert_rule.py      # 告警规则模型
│   └── services/               # 业务服务
│       ├── __init__.py
│       └── alert_rule_service.py  # 告警规则服务
├── config/                     # 数据库文件目录
├── logs/                       # 日志文件目录
├── main.py                     # 应用入口
├── test_db.py                  # 数据库测试脚本
├── requirements.txt            # 依赖包列表
├── .env                        # 环境变量配置
└── README.md                   # 项目文档
```

## 快速开始

### 1. 环境要求
- Python 3.10.12+
- pip

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置环境变量
复制并编辑 `.env` 文件：
```bash
# 应用设置
DEBUG=true
PORT=6003

# 数据库配置
DATABASE_PATH=config/voltageems-alarm.db

# Redis配置
REDIS_HOST=192.168.30.62
REDIS_PORT=6379
REDIS_PREFIX=alarmsrv:

# 日志配置
LOG_LEVEL=DEBUG
```

### 4. 启动服务
```bash
python3 main.py
```

服务将在 http://localhost:6003 启动

### 5. 测试数据库功能
```bash
python3 test_db.py
```

## API 接口

### 基础接口
- `GET /` - 服务信息
- `GET /health` - 健康检查
- `GET /docs` - API文档 (Swagger UI)

### 告警规则接口
- `POST /api/rules` - 创建告警规则
- `GET /api/rules` - 获取告警规则列表
- `GET /api/rules/{rule_id}` - 获取指定规则
- `PUT /api/rules/{rule_id}` - 更新告警规则
- `DELETE /api/rules/{rule_id}` - 删除告警规则
- `PATCH /api/rules/{rule_id}/enable` - 启用规则
- `PATCH /api/rules/{rule_id}/disable` - 禁用规则
- `GET /api/rules/channel/{channel_id}` - 获取指定通道的规则

### 示例：创建告警规则
```bash
curl -X POST "http://localhost:6003/api/rules" \
  -H "Content-Type: application/json" \
  -d '{
    "channel_id": 1001,
    "data_type": "T", 
    "point_id": 1,
    "rule_name": "温度过高告警",
    "warning_level": 2,
    "operator": ">",
    "value": 85.0,
    "description": "当温度超过85度时触发告警"
  }'
```

## 数据库说明

### SQLite配置
- **数据库文件**: `/app/config/voltageems-alarm.db` (生产环境) 或 `config/voltageems-alarm.db` (开发环境)
- **WAL模式**: 自动启用，提供更好的并发性能
- **自动创建**: 程序启动时自动创建数据库和表结构

### 表结构：alert_rule
```sql
CREATE TABLE alert_rule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER NOT NULL,
    data_type TEXT NOT NULL CHECK(data_type IN ('T', 'S', 'C', 'A')),
    point_id INTEGER NOT NULL,
    rule_name TEXT NOT NULL,
    warning_level INTEGER NOT NULL CHECK(warning_level IN (1, 2, 3)),
    operator TEXT NOT NULL CHECK(operator IN ('>', '<', '>=', '<=', '==', '!=')),
    value REAL NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT 1,
    description TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(channel_id, data_type, point_id, rule_name)
);
```

## 配置说明

### 配置优先级
1. **环境变量** (.env 文件)
2. **默认配置** (app/core/config.py)

### 关键配置项
- `DATABASE_PATH`: 数据库文件路径
- `REDIS_HOST/PORT`: Redis连接信息
- `LOG_LEVEL`: 日志级别
- `DEBUG`: 调试模式

## 开发说明

### 日志系统
- 支持多级别日志: DEBUG, INFO, WARNING, ERROR
- 日志文件: `logs/alarmsrv.log`
- 控制台输出: 开发模式下同时输出到控制台

### 错误处理
- 统一的异常处理机制
- HTTP状态码标准化
- 详细的错误信息返回

### 数据验证
- 使用Pydantic进行数据验证
- 规则有效性检查
- 数据库约束检查

## 部署

### Docker部署
```bash
# 构建镜像
docker build -t alarmsrv .

# 运行容器
docker run -d -p 6003:6003 -v /app/config:/app/config alarmsrv
```

### 生产环境配置
1. 设置 `DEBUG=false`
2. 使用绝对路径 `DATABASE_PATH=/app/config/voltageems-alarm.db`
3. 配置适当的日志级别
4. 设置安全的JWT密钥

## 技术栈

- **Web框架**: FastAPI 0.104.1
- **数据库**: SQLite3 (WAL模式)
- **数据验证**: Pydantic 2.5.0
- **异步服务器**: Uvicorn
- **Redis客户端**: redis 5.0.1
- **认证**: JWT (PyJWT)
- **日志**: Python logging + loguru

## 版本信息

- **当前版本**: 1.0.0
- **Python版本**: 3.10.12+
- **API版本**: v1

---

**告警服务** - 工业物联网边缘计算告警管理系统
