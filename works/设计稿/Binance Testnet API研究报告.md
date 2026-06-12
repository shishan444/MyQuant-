# Binance Testnet (Simulation Trading) API 研究报告

> 研究日期: 2026-04-30
> 文档来源: Binance 官方开发者文档 (最后更新 2026-04-28)
> 用途: 为 MyQuant 项目交易集成提供实现参考

---

## 1. Binance Testnet 是什么?与真实 API 的区别?

### 定义

Binance Testnet 是币安提供的模拟交易环境，使用虚拟资金，专门用于开发测试和策略验证。功能接口与生产环境几乎完全一致。

### 与真实 API 的关键区别

| 维度 | Testnet | Production |
|------|---------|------------|
| 资金 | 虚拟资金(可免费获取) | 真实资金 |
| 数据 | 模拟行情数据 | 真实市场数据 |
| API Key | 通过 GitHub 账号登录 testnet.binance.vision 创建 | 通过币安账户创建 |
| 稳定性 | 定期重置所有数据(约每1-3个月) | 持续运行 |
| 流动性 | 较低(无真实交易对手) | 高流动性 |
| 用途 | 开发/测试/策略验证 | 生产交易 |

### 已知的数据重置时间

- 2026-02-04, 2026-01-07
- 2025-10-01, 2025-09-05, 2025-07-02, 2025-06-04, 2025-04-01

重置后所有账户余额、订单历史、API Key 等数据清零，需要重新注册和配置。

---

## 2. 可用的 API 端点 (Spot Trading)

### Base URL

- REST API: `https://testnet.binance.vision/api`
- WebSocket Streams: `wss://stream.testnet.binance.vision/ws`
- WebSocket API: `wss://ws-api.testnet.binance.vision/ws-api/v3`
- FIX API: `fix-oi.testnet.binance.vision:9000` (单订单)/`fix-oi.testnet.binance.vision:9001` (批量)

### 市场数据端点 (无需认证)

| 端点 | 方法 | 说明 | 权重 |
|------|------|------|------|
| `/api/v3/ping` | GET | 连通性测试 | 1 |
| `/api/v3/time` | GET | 服务器时间 | 1 |
| `/api/v3/exchangeInfo` | GET | 交易规则和交易对信息 | 20 |
| `/api/v3/depth` | GET | 深度信息(订单簿) | 2-100 |
| `/api/v3/trades` | GET | 近期成交 | 2 |
| `/api/v3/historicalTrades` | GET | 历史成交 | 20 |
| `/api/v3/aggTrades` | GET | 归集成交 | 2 |
| `/api/v3/klines` | GET | K线数据 | 2 |
| `/api/v3/uiKlines` | GET | UI K线数据 | 2 |
| `/api/v3/ticker/24hr` | GET | 24h 价格变动 | 2-40 |
| `/api/v3/ticker/price` | GET | 最新价格 | 2-4 |
| `/api/v3/ticker/bookTicker` | GET | 最优挂价 | 2-4 |

### 账户端点 (需要 USER_DATA 权限)

| 端点 | 方法 | 说明 | 权重 |
|------|------|------|------|
| `/api/v3/account` | GET | 账户信息(余额等) | 20 |
| `/api/v3/myTrades` | GET | 账户成交历史 | 20 |
| `/api/v3/rateLimit/order` | GET | 当前订单数限制 | 20 |
| `/api/v3/openOrders` | GET | 当前挂单 | 6 |
| `/api/v3/allOrders` | GET | 所有订单历史 | 20 |

### 交易端点 (需要 TRADE 权限)

| 端点 | 方法 | 说明 | 权重 | 未成交订单计数 |
|------|------|------|------|----------|
| `/api/v3/order` | POST | 下单 | 1 | 1 |
| `/api/v3/order/test` | POST | 测试下单(不实际提交) | 1/20 | 0 |
| `/api/v3/order` | GET | 查询订单 | 4 | 0 |
| `/api/v3/order` | DELETE | 撤销订单 | 1 | 0 |
| `/api/v3/openOrders` | DELETE | 撤销所有挂单 | 1 | 0 |
| `/api/v3/order/cancelReplace` | POST | 撤销并替换订单 | 1 | 1 |
| `/api/v3/order/amend/keepPriority` | PUT | 修改订单(保持优先级) | 4 | 0 |
| `/api/v3/orderList/oco` | POST | OCO 订单列表 | 1 | 2 |
| `/api/v3/orderList/oto` | POST | OTO 订单列表 | 1 | 2 |
| `/api/v3/orderList/otoco` | POST | OTOCO 订单列表 | 1 | 3 |
| `/api/v3/orderList/opo` | POST | OPO 订单列表 | 1 | 2 |
| `/api/v3/orderList/opoco` | POST | OPOCO 订单列表 | 1 | 3 |
| `/api/v3/orderList` | DELETE | 撤销订单列表 | 1 | 0 |
| `/api/v3/sor/order` | POST | SOR(智能订单路由)下单 | 1 | 1 |

### 订单类型

- LIMIT - 限价单
- MARKET - 市价单
- STOP_LOSS - 止损单
- STOP_LOSS_LIMIT - 止损限价单
- TAKE_PROFIT - 止盈单
- TAKE_PROFIT_LIMIT - 止盈限价单
- LIMIT_MAKER - 限价只挂单

### 注意事项

- 自 2026-03-27 起，成功的订单下单请求权重为 0(失败的仍计权重)
- API 超时时间为 10 秒

---

## 3. 认证方式

### API Key 创建

通过 GitHub 账号登录 `https://testnet.binance.vision` 后在 API Management 页面创建。API Key 通过 HTTP Header `X-MBX-APIKEY` 传递。

### 支持三种签名方式

#### (A) HMAC SHA256 (最常用)

将所有请求参数(包括 timestamp)按字母序排列拼接为 query string，使用 Secret Key 计算 HMAC SHA256 签名。

```python
import hashlib
import hmac
import time
import requests

API_KEY = 'your-api-key'
API_SECRET = 'your-api-secret'

base_url = 'https://testnet.binance.vision'
timestamp = int(time.time() * 1000)
params = {
    'timestamp': timestamp,
    'recvWindow': 5000
}
query_string = '&'.join(f'{k}={v}' for k, v in params.items())
signature = hmac.new(
    API_SECRET.encode('utf-8'),
    query_string.encode('utf-8'),
    hashlib.sha256
).hexdigest()
params['signature'] = signature

headers = {'X-MBX-APIKEY': API_KEY}
response = requests.get(f'{base_url}/api/v3/account', headers=headers, params=params)
```

#### (B) RSA (PKCS#8)

使用 RSA 私钥(推荐 PKCS#8 格式)对 query string 进行 RSASSA-PKCS1-v1_5 with SHA-256 签名，结果 Base64 编码。

#### (C) Ed25519 (官方推荐 - 最佳性能/安全性)

```python
import base64
import time
from cryptography.hazmat.primitives.serialization import load_pem_private_key

API_KEY = 'your-api-key'
PRIVATE_KEY_PATH = 'test-prv-key.pem'

with open(PRIVATE_KEY_PATH, 'rb') as f:
    private_key = load_pem_private_key(data=f.read(), password=None)

params = {
    'symbol': 'BTCUSDT', 'side': 'BUY', 'type': 'LIMIT',
    'timeInForce': 'GTC', 'quantity': '0.001', 'price': '50000',
    'timestamp': int(time.time() * 1000),
}
payload = '&'.join([f'{k}={v}' for k, v in params.items()])
signature = base64.b64encode(private_key.sign(payload.encode('ASCII')))
params['signature'] = signature

headers = {'X-MBX-APIKEY': API_KEY}
response = requests.post(
    'https://testnet.binance.vision/api/v3/order',
    headers=headers,
    data=params
)
```

### 安全类型分类

| 类型 | 说明 | 需要 API Key | 需要 签名 |
|------|------|:---:|:---:|
| NONE | 公开端点 | 否 | 否 |
| TRADE | 下单/撤单 | 是 | 是 |
| USER_DATA | 账户/订单查询 | 是 | 是 |
| USER_STREAM | 用户数据流 | 是 | 否(仅需 listenKey) |

### 时间安全参数

- `timestamp` - 必需，毫秒或微秒时间戳
- `recvWindow` - 可选，默认 5000ms，最大 60000ms。服务器检查 `timestamp + recvWindow` 是否包含当前时间。

---

## 4. 频率限制

### 三种限制类型

| 类型 | 说明 | 限制 |
|------|------|------|
| RAW_REQUESTS | 每个 IP 的原始 HTTP 请求数 | 300,000 / 5 分钟 |
| REQUEST_WEIGHT | 请求权重累计(每个端点不同) | 6,000 / 5 分钟 |
| ORDERS | 未成交订单计数 | 按时间窗口递增 |

### 响应头 (监控用量)

```
X-MBX-USED-WEIGHT-(intervalNum)(intervalLetter)  # 当前权重用量
X-MBX-ORDER-COUNT-(intervalNum)(intervalLetter)  # 当前订单计数
```

### 超限处理

| HTTP 状态码 | 含义 |
|-------------|------|
| 429 | 触发频率限制，需停止请求 |
| 418 | IP 被封禁(重复违规)，封禁时间从 2 分钟到 3 天递增 |

### 实践建议

- 每次请求后检查响应头中的用量
- 实现 429 自动退避机制(指数退避)
- 避免在循环中高频轮询，优先使用 WebSocket
- 成功下单请求(自 2026-03-27)权重为 0，但失败请求仍计权重

---

## 5. Python SDK / Library 支持 Testnet

有两个主要的 Python SDK，都支持 Testnet:

### 方案 A: python-binance (社区版，更简洁)

**仓库**: https://github.com/sammchardy/python-binance
**特点**: 非官方封装，API 更简洁，支持同步/异步，支持 Spot/Futures/Options

```python
from binance import Client, AsyncClient

# Testnet 模式 - 只需设置 testnet=True
client = Client(api_key='your_api_key', api_secret='your_api_secret', testnet=True)

# 异步 Testnet
async_client = await AsyncClient.create(api_key, api_secret, testnet=True)

# 支持 RSA/Ed25519 密钥认证
client = Client(
    api_key='your_api_key',
    private_key=open('private_key.pem').read(),
    testnet=True
)

# 基本操作
account = client.get_account()
prices = client.get_all_tickers()
order = client.create_order(
    symbol='BTCUSDT',
    side='BUY',
    type='LIMIT',
    timeInForce='GTC',
    quantity='0.001',
    price='50000'
)
```

**安装**: `pip install python-binance`

### 方案 B: binance-connector-python (官方版，模块化)

**仓库**: https://github.com/binance/binance-connector-python
**特点**: 官方维护，模块化设计(Spot/Futures/Portfolio Margin 独立包)

```python
from binance_common.configuration import ConfigurationRestAPI
from binance_common.constants import SPOT_REST_API_TESTNET_URL
from binance_sdk_spot.spot import Spot

# Spot Testnet 配置
configuration = ConfigurationRestAPI(
    api_key="testnet-api-key",
    api_secret="testnet-api-secret",
    base_path=SPOT_REST_API_TESTNET_URL,
)
client = Spot(config_rest_api=configuration)

# 获取账户信息
response = client.rest_api.account()
```

**安装**: `pip install binance-sdk-spot binance-common`

### 推荐选择

| 维度 | python-binance | binance-connector-python |
|------|----------------|--------------------------|
| 维护方 | 社区(sammchardy) | Binance 官方 |
| 接口风格 | 简洁、Pythonic | 类型安全、结构化 |
| Testnet 配置 | `testnet=True` 一键切换 | 需要手动设置 base_path |
| 异步支持 | 原生 AsyncClient | 通过配置支持 |
| 文档质量 | 中等 | 良好 |
| 适用场景 | 快速原型/策略开发 | 正式生产系统 |

**建议**: 对于 MyQuant 项目，推荐 `python-binance`，因为 `testnet=True` 一行即可切换环境，接口简洁适合快速开发。

---

## 6. Base URL 汇总

### Spot Testnet

| 协议 | URL |
|------|-----|
| REST API | `https://testnet.binance.vision/api` |
| WebSocket Streams | `wss://stream.testnet.binance.vision/ws` |
| WebSocket API | `wss://ws-api.testnet.binance.vision/ws-api/v3` |
| FIX API | `fix-oi.testnet.binance.vision:9000`(单) / `:9001`(批量) |

### Futures Testnet (USDS-M)

| 协议 | URL |
|------|-----|
| Web UI | `https://testnet.binancefuture.com` |
| REST API | `https://testnet.binancefuture.com/fapi/v1/*` |
| COIN-M REST | `https://testnet.binancefuture.com/dapi/v1/*` |

### python-binance 中 Testnet URL 自动映射

设置 `testnet=True` 后，SDK 自动将所有请求路由到 testnet URL，无需手动配置。

---

## 7. Futures / 杠杆交易支持

### Testnet 支持的衍生品类型

| 类型 | Testnet 支持 | REST 前缀 | 说明 |
|------|:---:|------|------|
| USDS-M Futures | 是 | `/fapi/v1/` | USDT 保证金永续/交割合约 |
| COIN-M Futures | 是 | `/dapi/v1/` | 币本位永续/交割合约 |
| Portfolio Margin | 是 | `/papi/v1/` | 组合保证金模式 |

### USDS-M Futures 主要端点

- `POST /fapi/v1/leverage` - 设置杠杆倍数
- `POST /fapi/v1/marginType` - 切换全仓/逐仓
- `POST /fapi/v1/order` - 下单
- `GET /fapi/v1/account` - 账户信息
- `GET /fapi/v1/positionRisk` - 持仓信息
- `GET /fapi/v1/exchangeInfo` - 交易规则

### python-binance Futures Testnet 示例

```python
from binance import Client

client = Client(api_key, api_secret, testnet=True)

# 设置杠杆
client.futures_change_leverage(symbol='BTCUSDT', leverage=10)

# 下单
order = client.futures_create_order(
    symbol='BTCUSDT',
    side='BUY',
    type='LIMIT',
    timeInForce='GTC',
    quantity=0.001,
    price=50000
)

# 查询持仓
positions = client.futures_position_information(symbol='BTCUSDT')
```

### binance-connector-python Futures Testnet 示例

```python
from binance_common.configuration import ConfigurationRestAPI
from binance_common.constants import DERIVATIVES_TRADING_USDS_FUTURES_REST_API_TESTNET_URL
from binance_sdk_derivatives_trading_usds_futures.derivatives_trading_usds_futures import (
    DerivativesTradingUsdsFutures
)

configuration = ConfigurationRestAPI(
    api_key="your-api-key",
    api_secret="your-api-secret",
    base_path=DERIVATIVES_TRADING_USDS_FUTURES_REST_API_TESTNET_URL,
)
client = DerivativesTradingUsdsFutures(config_rest_api=configuration)
```

---

## 8. 已知限制(与生产环境差异)

### 功能限制

1. **数据定期重置**: 约 1-3 个月重置一次，所有余额、订单、API Key 清零
2. **流动性低**: 没有真实交易对手，深度可能不够
3. **行情数据偏差**: 模拟行情可能与真实市场有差异
4. **API Key 管理**: 必须通过 GitHub 登录创建，不支持其他登录方式

### API 差异

5. **listenKey 已弃用**: 基于传统 listenKey 的用户数据流已废弃，需使用 WebSocket API 订阅方式(需要 Ed25519 密钥)
6. **SBE 格式**: 支持 Simple Binary Encoding 市场数据格式(生产环境也支持)
7. **部分端点可能延迟更新**: Testnet 的功能更新可能与生产环境有时间差

### 测试注意事项

8. **时间同步**: 本地时间与服务器时间差必须在 recvWindow 内(默认5秒)
9. **IP 限速与生产环境相同**: 测试时也要遵守频率限制
10. **精度规则**: 与生产环境一致，需严格按照 exchangeInfo 中的精度规则下单

---

## 附录: 快速开始 Checklist

1. 访问 `https://testnet.binance.vision`，用 GitHub 账号登录
2. 在 API Management 创建 API Key 和 Secret
3. 获取测试资金(页面内有 faucet 功能)
4. 安装 SDK: `pip install python-binance`
5. 配置客户端:

```python
from binance import Client

client = Client(
    api_key='your-testnet-api-key',
    api_secret='your-testnet-api-secret',
    testnet=True
)

# 验证连接
print(client.get_account())
```

6. 开始开发和测试交易逻辑
