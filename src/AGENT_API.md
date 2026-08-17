# 串口助手 Agent API

串口助手 v1.1 启动后，会在本机 `127.0.0.1:18765` 提供 HTTP JSON 接口。接口与 GUI 共用同一组串口会话和 T5L 下载模块，适合 Codex、自动化脚本及其他智能体调用。

## 安全与连接

- 服务只监听本机回环地址，不接受局域网或互联网连接。
- 除 `/health` 外，所有接口必须携带请求头 `X-Serial-Token`。
- Token 和端口保存在 EXE 同目录的 `config.json`：

```json
{
  "agent_api_token": "自动生成的随机 Token",
  "agent_api_port": 18765
}
```

请勿公开 Token。修改端口或 Token 后需要重启串口助手。

## 命令行客户端

源码中的 `agent_api.py` 同时是命令行客户端。串口助手必须保持运行：

```powershell
python agent_api.py --config "D:\工具\串口助手\config.json" status
python agent_api.py --config "D:\工具\串口助手\config.json" open COM5 --baud 115200 --data-bits 8 --parity N --stop-bits 1
python agent_api.py --config "D:\工具\串口助手\config.json" send COM5 "5A A5 04 83 00 14 01" --hex
python agent_api.py --config "D:\工具\串口助手\config.json" send COM5 "hello"
python agent_api.py --config "D:\工具\串口助手\config.json" close COM5
python agent_api.py --config "D:\工具\串口助手\config.json" download --port COM5 --baud 115200 --folder "D:\DWIN_SET"
python agent_api.py --config "D:\工具\串口助手\config.json" download --port COM5 --file "D:\DWIN_SET\13TouchFile.bin" --file "D:\DWIN_SET\14ShowFile.bin"
python agent_api.py --config "D:\工具\串口助手\config.json" stop-download
```

校验位支持中文名称以及 `N`、`O`、`E`、`M`、`S`。

## HTTP 接口

基础地址：`http://127.0.0.1:18765`

| 方法 | 路径 | 功能 |
|---|---|---|
| GET | `/health` | 无需 Token 的存活检查 |
| GET | `/api/status` | 查询串口、收发计数和 T5L 下载状态 |
| POST | `/api/serial/open` | 创建或打开串口，并设置线路参数 |
| POST | `/api/serial/close` | 关闭指定串口，不删除标签配置 |
| POST | `/api/serial/send` | 向指定串口发送字符或 HEX 数据 |
| POST | `/api/serial/receive` | 读取指定串口最新接收数据，可选读取后清空 |
| POST | `/api/t5l/download` | 按目录或文件列表启动 T5L 下载 |
| POST | `/api/t5l/stop` | 请求停止当前 T5L 下载 |

### 打开串口

```json
{"port":"COM5","baud":115200,"data_bits":8,"parity":"N","stop_bits":1}
```

### 发送数据

HEX：

```json
{"port":"COM5","data":"01 03 00 21 00 04","hex":true,"checksum":"Modbus CRC16"}
```

字符：

```json
{"port":"COM5","data":"hello","hex":false}
```

`checksum` 可使用 `None`、`Modbus CRC16`、`CCITT CRC16`、`CRC32`、`ADD8`、`ADD16`、`XOR8`。校验范围使用该 COM 口在 GUI 中保存的独立设置。

### 启动 T5L 下载

下载目录中全部可识别文件：

```json
{"port":"COM5","baud":115200,"folder":"D:\\DWIN_SET"}
```

仅下载指定文件：

```json
{"port":"COM5","baud":115200,"files":["D:\\DWIN_SET\\13TouchFile.bin","D:\\DWIN_SET\\T5L51.bin"]}
```

下载为异步任务。接口返回 `started: true` 后，使用 `/api/status` 查询实时进度和运行状态。

### 读取最新接收数据

```json
{"port":"COM5","limit":20,"clear":false,"encoding":"GBK"}
```

返回 `latest` 和 `packets`，每包同时包含 `time`、`bytes`、`hex`、`text`。`clear` 为
`true` 时仅清空 Agent 独立接收缓存，不会清除界面中的通讯记录。

```powershell
python agent_api.py --config ".\\config.json" receive COM5 --limit 20
python agent_api.py --config ".\\config.json" receive COM5 --clear
```

## PowerShell 调用示例

```powershell
$config = Get-Content -Raw -Encoding UTF8 ".\config.json" | ConvertFrom-Json
$headers = @{ "X-Serial-Token" = $config.agent_api_token }
$body = @{ port="COM5"; data="5A A5 04 83 00 14 01"; hex=$true } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:$($config.agent_api_port)/api/serial/send" -Method Post -Headers $headers -ContentType "application/json" -Body $body
```

## 返回格式

成功：

```json
{"ok":true,"result":{}}
```

失败：

```json
{"ok":false,"error":"错误说明"}
```
