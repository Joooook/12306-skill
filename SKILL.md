---
name: 12306-skill
description: 使用 Python 脚本调用 12306 接口，查询车票、车站和列车信息。
---

# 12306 Skill

## Quick Start

- 先进入目录：`12306-skill`
- 查看可用工具：`python scripts/12306_apis.py list-tools`
- 调用工具：`python scripts/12306_apis.py <tool-name> [--arg value ...]`

## Tool Commands

- `refresh-cache`: 刷新本地缓存（站点数据与 lcquery 路径）,非特殊情况不调用。
- `get-current-date`: 获取当前日期，以上海时区（Asia/Shanghai, UTC+8）为准，返回格式 `yyyy-MM-dd`。主要用于解析相对日期。
- `get-stations-code-in-city`: 通过中文城市名查询该城市所有火车站的名称及其对应的 `station_code`。
- `get-station-code-of-citys`: 通过中文城市名查询代表该城市的 `station_code`。
- `get-station-code-by-names`: 通过具体中文车站名查询其 `station_code` 和车站名。
- `get-station-by-telecode`: 通过 `station_telecode` 查询车站详细信息（名称、拼音、所属城市等），常用于补充查询与调试。
- `get-tickets`: 查询 12306 直达余票信息。
- `get-interline-tickets`: 查询 12306 中转余票信息。
- `get-train-route-stations`: 查询特定车次在指定日期的经停站、到发时间和停留信息。

## 函数调用参数说明

### `refresh-cache`

- 无参数。

### `get-current-date`

- 无参数。

### `get-stations-code-in-city`

- `city` (必填, string): 城市名，例如 `北京`。

### `get-station-code-of-citys`

- `citys` (必填, string): 一个或多个城市名，使用 `|` 分隔，例如 `北京|上海`。

### `get-station-code-by-names`

- `station_names` (必填, string): 一个或多个车站名，使用 `|` 分隔，例如 `北京南|上海虹桥`。

### `get-station-by-telecode`

- `station_telecode` (必填, string): 车站电报码，例如 `BJP`。

### `get-tickets`

- `date` (必填, string): 出发日期，格式 `YYYY-MM-DD`，且不能早于当天。
- `from_station` (必填, string): 出发站，可传站名（如 `北京南`）或电报码（如 `VNP`）。
- `to_station` (必填, string): 到达站，可传站名或电报码。
- `train_filter_flags` (可选, string, 默认 `""`): 车次过滤标记，可组合（如 `GD`）。支持：
  - `G` 高铁/城际
  - `D` 动车
  - `Z` 直达
  - `T` 特快
  - `K` 快速
  - `O` 其他
  - `F` 复兴号
  - `S` 智能动车组
- `earliest_start_time` (可选, int, 默认 `0`): 最早发车小时（含），范围建议 `0-23`。
- `latest_start_time` (可选, int, 默认 `24`): 最晚发车小时（不含），范围建议 `1-24`。
- `sort_flag` (可选, string, 默认 `""`): 排序字段，可选 `startTime` / `arriveTime` / `duration`。
- `sort_reverse` (可选, bool, 默认 `false`): 是否倒序。
- `limited_num` (可选, int, 默认 `0`): 返回数量限制，`0` 表示不限制。
- `format` (可选, string, 默认 `text`): 输出格式，可选 `text` / `csv` / `json`。

### `get-interline-tickets`

- `date` (必填, string): 出发日期，格式 `YYYY-MM-DD`，且不能早于当天。
- `from_station` (必填, string): 出发站，站名或电报码。
- `to_station` (必填, string): 到达站，站名或电报码。
- `middle_station` (可选, string, 默认 `""`): 指定中转站，站名或电报码；留空表示自动推荐中转站。
- `show_wz` (可选, bool, 默认 `false`): 是否显示无座方案。
- `train_filter_flags` (可选, string, 默认 `""`): 过滤规则同 `get-tickets`。
- `earliest_start_time` (可选, int, 默认 `0`): 最早发车小时（含）。
- `latest_start_time` (可选, int, 默认 `24`): 最晚发车小时（不含）。
- `sort_flag` (可选, string, 默认 `""`): 排序字段，可选 `startTime` / `arriveTime` / `duration`。
- `sort_reverse` (可选, bool, 默认 `false`): 是否倒序。
- `limited_num` (可选, int, 默认 `10`): 返回数量限制。
- `format` (可选, string, 默认 `text`): 输出格式，可选 `text` / `json`。

### `get-train-route-stations`

- `train_code` (必填, string): 车次号，例如 `G1033`。
- `depart_date` (必填, string): 运行日期，格式 `YYYY-MM-DD`。
- `format` (可选, string, 默认 `text`): 输出格式，可选 `text` / `json`。

## Args Examples

```bash
python scripts/12306_apis.py get-current-date
python scripts/12306_apis.py get-stations-code-in-city --city "北京"
python scripts/12306_apis.py get-tickets --date "2026-03-09" --from_station "北京" --to_station "上海" --train_filter_flags "G" --format text
python scripts/12306_apis.py get-interline-tickets --date "2026-03-09" --from_station "成都" --to_station "广州" --limited_num 5
python scripts/12306_apis.py get-train-route-stations --train_code "G1033" --depart_date "2026-03-09"
```

## Execution Rules

- 请尽量使用接口的筛选功能，来筛选必要的信息，以此节省Token。
