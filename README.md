# <div align="center">12306-skill</div>

<div align="center">

[![](https://img.shields.io/badge/Joooook-blue.svg?logo=github&labelColor=497568&color=497568&style=flat-square)](https://github.com/Joooook)
[![](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white&labelColor=192c3b&color=192c3b&style=flat-square)](https://www.python.org/)
![](https://img.shields.io/badge/Agent-Skill-2f855a.svg?style=flat-square)
![](https://img.shields.io/badge/12306-API-f59e0b.svg?style=flat-square)

</div>

基于 Python 的 12306 查询 Skill，在对话中调用。支持站点查询、直达余票查询、中转查询、车次经停查询。

## <div align="center">🚩Features</div>

<div align="center">

| 功能 | 状态 |
|---|---|
| 查询城市下全部车站编码 | ✅ |
| 查询城市代表站编码 | ✅ |
| 查询站名对应编码 | ✅ |
| 查询站点详情 | ✅ |
| 查询直达余票（筛选/排序/限制） | ✅ |
| 查询中转余票（支持指定中转站） | ✅ |
| 查询车次经停信息 | ✅ |

</div>

## <div align="center">⚙️Requirements</div>

- Python `3.10+`
- 依赖：`requests`

安装依赖：

```bash
pip install requests
```

## <div align="center">▶️Quick Start</div>

在当前 Skill 目录执行：

```bash
python scripts/12306_apis.py list-tools
python scripts/12306_apis.py get-current-date
python scripts/12306_apis.py get-stations-code-in-city --city "北京"
python scripts/12306_apis.py get-tickets --date "2026-03-09" --from_station "北京" --to_station "上海" --train_filter_flags "G" --format text
```

## <div align="center">💡Notes</div>

- `date` 参数格式必须是 `YYYY-MM-DD`，且不能早于当天（按 `Asia/Shanghai` 计算）。
- 缓存文件 `scripts/stations.json` 与 `scripts/lcquery_path` 默认缓存 1 天。
- 建议优先使用筛选参数（如 `train_filter_flags`、`limited_num`）减少输出长度。

## <div align="center">☕️Donate</div>
请我喝杯奶茶吧。
<div align="center"> 
<a href="https://afdian.com/item/2a0e0cdcadf911ef9f725254001e7c00">
  <img src="https://s2.loli.net/2024/11/29/1JBxzphs7V6WcK9.jpg" width="500px">
</a>
</div>

