#!/usr/bin/env python3
"""Standalone 12306 skill backend.
This module mirrors all function names from 12306-mcp/src/index.ts and provides CLI access for each original MCP tool.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from functools import cmp_to_key
from typing import Any, Callable, Literal
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests

VERSION = "0.1.0"
API_BASE = "https://kyfw.12306.cn"
SEARCH_API_BASE = "https://search.12306.cn"
WEB_URL = "https://www.12306.cn/index/"
LCQUERY_INIT_URL = "https://kyfw.12306.cn/otn/lcQuery/init"

MISSING_STATIONS = [{"station_id":"@cdd","station_name":"成  都东","station_code":"WEI","station_pinyin":"chengdudong","station_short":"cdd","station_index":"","code":"1707","city":"成都","r1":"","r2":""}]

TICKET_DATA_KEYS = ["secret_Sstr","button_text_info","train_no","station_train_code","start_station_telecode","end_station_telecode","from_station_telecode","to_station_telecode","start_time","arrive_time","lishi","canWebBuy","yp_info","start_train_date","train_seat_feature","location_code","from_station_no","to_station_no","is_support_card","controlled_train_flag","gg_num","gr_num","qt_num","rw_num","rz_num","tz_num","wz_num","yb_num","yw_num","yz_num","ze_num","zy_num","swz_num","srrb_num","yp_ex","seat_types","exchange_train_flag","houbu_train_flag","houbu_seat_limit","yp_info_new","40","41","42","43","44","45","dw_flag","47","stopcheckTime","country_flag","local_arrive_time","local_start_time","52","bed_level_info","seat_discount_info","sale_time","56"]
STATION_DATA_KEYS = ["station_id","station_name","station_code","station_pinyin","station_short","station_index","code","city","r1","r2"]

SEAT_SHORT_TYPES = {"swz":"商务座","tz":"特等座","zy":"一等座","ze":"二等座","gr":"高软卧","srrb":"动卧","rw":"软卧","yw":"硬卧","rz":"软座","yz":"硬座","wz":"无座","qt":"其他","gg":"","yb":""}
SEAT_TYPES = {"9":{"name":"商务座","short":"swz"},"P":{"name":"特等座","short":"tz"},"M":{"name":"一等座","short":"zy"},"D":{"name":"优选一等座","short":"zy"},"O":{"name":"二等座","short":"ze"},"S":{"name":"二等包座","short":"ze"},"6":{"name":"高级软卧","short":"gr"},"A":{"name":"高级动卧","short":"gr"},"4":{"name":"软卧","short":"rw"},"I":{"name":"一等卧","short":"rw"},"F":{"name":"动卧","short":"rw"},"3":{"name":"硬卧","short":"yw"},"J":{"name":"二等卧","short":"yw"},"2":{"name":"软座","short":"rz"},"1":{"name":"硬座","short":"yz"},"W":{"name":"无座","short":"wz"},"WZ":{"name":"无座","short":"wz"},"H":{"name":"其他","short":"qt"}}
DW_FLAGS = ["智能动车组","复兴号","静音车厢","温馨动卧","动感号","支持选铺","老年优惠"]

STATIONS: dict[str, dict[str, str]] = {}
CITY_STATIONS: dict[str, list[dict[str, str]]] = {}
CITY_CODES: dict[str, dict[str, str]] = {}
NAME_STATIONS: dict[str, dict[str, str]] = {}
LCQUERY_PATH = ""
COOKIES = None

def format_cookies(cookies: dict[str, str]) -> str:
    return "; ".join([f"{key}={value}" for key, value in cookies.items()])


def get_cookie() -> dict[str, str] | None:
    global COOKIES
    if COOKIES: return COOKIES
    url = f"{API_BASE}/otn/leftTicket/init"
    try:
        response = requests.get(url)
        cookies = response.cookies.get_dict()
        COOKIES = cookies
        return cookies
    except Exception as error:
        print(f"Error get cookie: {error}", file=sys.stderr)
        return None


def parse_station_code(station: str) -> str | None:
    if re.fullmatch(r"[A-Z]+", station or "") and station in STATIONS:
        return station
    station = station[:-1] if station.endswith("站") else station
    if station in NAME_STATIONS:
        return NAME_STATIONS[station]["station_code"]
    return None


def parse_route_stations_data(raw_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(item) for item in raw_data]


def parse_route_stations_info(route_stations_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not route_stations_data: return []
    first = route_stations_data[0]
    result: list[dict[str, Any]] = [{
        "train_class_name": first.get("train_class_name"),
        "service_type": first.get("service_type"),
        "end_station_name": first.get("end_station_name"),
        "station_name": first.get("station_name"),
        "station_train_code": first.get("station_train_code"),
        "arrive_time": first.get("arrive_time"),
        "start_time": first.get("start_time"),
        "lishi": first.get("running_time"),
        "arrive_day_str": first.get("arrive_day_str")
    }]
    for routeStationData in route_stations_data[1:]:
        result.append({
            "station_name": routeStationData.get("station_name"),
            "station_train_code": routeStationData.get("station_train_code"),
            "arrive_time": routeStationData.get("arrive_time"),
            "start_time": routeStationData.get("start_time"),
            "lishi": routeStationData.get("running_time"),
            "arrive_day_str": routeStationData.get("arrive_day_str")
        })
    return result


def parse_tickets_data(raw_data: list[str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in raw_data:
        values = item.split("|")
        entry: dict[str, Any] = {}
        for index, key in enumerate(TICKET_DATA_KEYS):
            entry[key] = values[index]
        result.append(entry)
    return result


def _parse_start_train_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y%m%d")




def parse_tickets_info(tickets_data: list[dict[str, Any]], map: dict[str, str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for ticket in tickets_data:
        prices = extract_prices(ticket.get("yp_info_new", ""), ticket.get("seat_discount_info", ""), ticket)
        dw_flag = extract_dw_flags(ticket.get("dw_flag", ""))
        start_hours, start_minutes = [int(x) for x in ticket["start_time"].split(":")]
        duration_hours, duration_minutes = [int(x) for x in ticket["lishi"].split(":")]
        start_date = _parse_start_train_date(ticket["start_train_date"]).replace(hour=start_hours, minute=start_minutes)
        arrive_date = start_date + timedelta(hours=duration_hours, minutes=duration_minutes)
        result.append({
            "train_no": ticket.get("train_no"),
            "start_date": start_date.strftime("%Y-%m-%d"),
            "arrive_date": arrive_date.strftime("%Y-%m-%d"),
            "start_train_code": ticket.get("station_train_code"),
            "start_time": ticket.get("start_time"),
            "arrive_time": ticket.get("arrive_time"),
            "lishi": ticket.get("lishi"),
            "from_station": map.get(ticket.get("from_station_telecode", ""), ""),
            "to_station": map.get(ticket.get("to_station_telecode", ""), ""),
            "from_station_telecode": ticket.get("from_station_telecode"),
            "to_station_telecode": ticket.get("to_station_telecode"),
            "prices": prices,
            "dw_flag": dw_flag
        })
    return result

def format_ticket_status(num: str) -> str:
    if num.isdigit():
        count = int(num)
        return "无票" if count == 0 else f"剩余{count}张票"
    if num in ["有", "充足"]:
        return "有票"
    if num in ["无", "--", ""]:
        return "无票"
    if num == "候补":
        return "无票需候补"
    return f"{num}票"


def format_tickets_info(tickets_info: list[dict[str, Any]]) -> str:
    if not tickets_info:
        return "没有查询到相关车次信息"
    result = "车次|出发站 -> 到达站|出发时间 -> 到达时间|历时\n"
    for ticket_info in tickets_info:
        info = f"{ticket_info['start_train_code']} {ticket_info['from_station']}(telecode:{ticket_info['from_station_telecode']}) -> {ticket_info['to_station']}(telecode:{ticket_info['to_station_telecode']}) {ticket_info['start_time']} -> {ticket_info['arrive_time']} 历时：{ticket_info['lishi']}"
        for price in ticket_info["prices"]:
            info += f"\n- {price['seat_name']}: {format_ticket_status(price.get('num', ''))} {price['price']}元"
        result += info + "\n"
    return result


def format_tickets_info_csv(tickets_info: list[dict[str, Any]]) -> str:
    if not tickets_info:
        return "没有查询到相关车次信息"
    result = "车次,出发站,到达站,出发时间,到达时间,历时,票价,特色标签\n"
    for ticket_info in tickets_info:
        line = f"{ticket_info['start_train_code']},{ticket_info['from_station']}(telecode:{ticket_info['from_station_telecode']}),{ticket_info['to_station']}(telecode:{ticket_info['to_station_telecode']}),{ticket_info['start_time']},{ticket_info['arrive_time']},{ticket_info['lishi']},["
        for price in ticket_info["prices"]:
            line += f"{price['seat_name']}: {format_ticket_status(str(price.get('num', '')))}{price['price']}元,"
        tags = "/" if not ticket_info["dw_flag"] else "&".join(ticket_info["dw_flag"])
        line += f"],{tags}"
        result += line + "\n"
    return result


def format_route_stations_info(route_stations_info: list[dict[str, Any]]) -> str:
    if not route_stations_info:
        return "未查询到相关车次信息。"
    first = route_stations_info[0]
    ac = "无空调" if first.get("service_type") == "0" else "有空调"
    result = f"{first.get('station_train_code')}次列车（{first.get('train_class_name')} {ac}）\n站序|车站|车次|到达时间|出发时间|历时(hh:mm)\n"
    for idx, station in enumerate(route_stations_info, start=1):
        result += f"{idx}|{station.get('station_name')}|{station.get('station_train_code')}|{station.get('arrive_time')}|{station.get('start_time')}|{station.get('arrive_day_str')} {station.get('lishi')}\n"
    return result


def train_filter_G(ticket_info: dict[str, Any]) -> bool:
    code = ticket_info.get("start_train_code", "")
    return code.startswith("G") or code.startswith("C")
def train_filter_D(ticket_info: dict[str, Any]) -> bool: return ticket_info.get("start_train_code", "").startswith("D")
def train_filter_Z(ticket_info: dict[str, Any]) -> bool: return ticket_info.get("start_train_code", "").startswith("Z")
def train_filter_T(ticket_info: dict[str, Any]) -> bool: return ticket_info.get("start_train_code", "").startswith("T")
def train_filter_K(ticket_info: dict[str, Any]) -> bool: return ticket_info.get("start_train_code", "").startswith("K")
def train_filter_O(ticket_info: dict[str, Any]) -> bool: return not (train_filter_G(ticket_info) or train_filter_D(ticket_info) or train_filter_Z(ticket_info) or train_filter_T(ticket_info) or train_filter_K(ticket_info))

def train_filter_F(ticket_info: dict[str, Any]) -> bool:
    if "dw_flag" in ticket_info:
        return "复兴号" in (ticket_info.get("dw_flag") or [])
    ticket_list = ticket_info.get("ticketList", [])
    return bool(ticket_list and "复兴号" in (ticket_list[0].get("dw_flag") or []))

def train_filter_S(ticket_info: dict[str, Any]) -> bool:
    if "dw_flag" in ticket_info:
        return "智能动车组" in (ticket_info.get("dw_flag") or [])
    ticket_list = ticket_info.get("ticketList", [])
    return bool(ticket_list and "智能动车组" in (ticket_list[0].get("dw_flag") or []))

TRAIN_FILTERS: dict[str, Callable[[dict[str, Any]], bool]] = {"G": train_filter_G, "D": train_filter_D, "Z": train_filter_Z, "T": train_filter_T, "K": train_filter_K, "O": train_filter_O, "F": train_filter_F, "S": train_filter_S}


def _compare_by_date_and_time(a_date: str, a_time: str, b_date: str, b_time: str) -> int:
    ad = datetime.strptime(a_date, "%Y-%m-%d")
    bd = datetime.strptime(b_date, "%Y-%m-%d")
    if ad != bd:
        return -1 if ad < bd else 1
    ah, am = [int(x) for x in a_time.split(":")]
    bh, bm = [int(x) for x in b_time.split(":")]
    if ah != bh:
        return ah - bh
    return am - bm

def compare_start_time(a: dict[str, Any], b: dict[str, Any]) -> int: return _compare_by_date_and_time(a["start_date"], a["start_time"], b["start_date"], b["start_time"])
def compare_arrive_time(a: dict[str, Any], b: dict[str, Any]) -> int: return _compare_by_date_and_time(a["arrive_date"], a["arrive_time"], b["arrive_date"], b["arrive_time"])

def compare_duration(a: dict[str, Any], b: dict[str, Any]) -> int:
    ah, am = [int(x) for x in a["lishi"].split(":")]
    bh, bm = [int(x) for x in b["lishi"].split(":")]
    if ah != bh:
        return ah - bh
    return am - bm

TIME_COMPARETOR: dict[str, Callable[[dict[str, Any], dict[str, Any]], int]] = {"startTime": compare_start_time, "arriveTime": compare_arrive_time, "duration": compare_duration}


def filter_tickets_info(tickets_info: list[dict[str, Any]], train_filter_flags: str, earliest_start_time: int = 0, latest_start_time: int = 24, sort_flag: Literal["", "startTime", "arriveTime", "duration"] = "", sort_reverse: bool = False, limited_num: int = 0) -> list[dict[str, Any]]:
    result = tickets_info if not train_filter_flags else []
    if train_filter_flags:
        for ticket_info in tickets_info:
            for flag in train_filter_flags:
                if flag in TRAIN_FILTERS and TRAIN_FILTERS[flag](ticket_info):
                    result.append(ticket_info)
                    break
    result = [item for item in result if earliest_start_time <= int(item.get("start_time", "00:00").split(":")[0]) < latest_start_time]
    if sort_flag in TIME_COMPARETOR:
        result.sort(key=cmp_to_key(TIME_COMPARETOR[sort_flag]))
        if sort_reverse:
            result.reverse()
    return result if limited_num == 0 else result[:limited_num]


def parse_interlines_ticket_info(interline_tickets_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for ticket in interline_tickets_data:
        prices = extract_prices(ticket.get("yp_info", ""), ticket.get("seat_discount_info", ""), ticket)
        start_hours, start_minutes = [int(x) for x in ticket["start_time"].split(":")]
        duration_hours, duration_minutes = [int(x) for x in ticket["lishi"].split(":")]
        start_date = _parse_start_train_date(ticket["start_train_date"]).replace(hour=start_hours, minute=start_minutes)
        arrive_date = start_date + timedelta(hours=duration_hours, minutes=duration_minutes)
        result.append({"train_no": ticket.get("train_no"),"start_train_code": ticket.get("station_train_code"),"start_date": start_date.strftime("%Y-%m-%d"),"arrive_date": arrive_date.strftime("%Y-%m-%d"),"start_time": ticket.get("start_time"),"arrive_time": ticket.get("arrive_time"),"lishi": ticket.get("lishi"),"from_station": ticket.get("from_station_name"),"to_station": ticket.get("to_station_name"),"from_station_telecode": ticket.get("from_station_telecode"),"to_station_telecode": ticket.get("to_station_telecode"),"prices": prices,"dw_flag": extract_dw_flags(ticket.get("dw_flag", ""))})
    return result


def parse_interlines_info(interline_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for ticket in interline_data:
        interline_tickets = parse_interlines_ticket_info(ticket.get("fullList", []))
        result.append({"lishi": extract_lishi(ticket.get("all_lishi", "")),"start_time": ticket.get("start_time"),"start_date": ticket.get("train_date"),"middle_date": ticket.get("middle_date"),"arrive_date": ticket.get("arrive_date"),"arrive_time": ticket.get("arrive_time"),"from_station_code": ticket.get("from_station_code"),"from_station_name": ticket.get("from_station_name"),"middle_station_code": ticket.get("middle_station_code"),"middle_station_name": ticket.get("middle_station_name"),"end_station_code": ticket.get("end_station_code"),"end_station_name": ticket.get("end_station_name"),"start_train_code": interline_tickets[0]["start_train_code"] if interline_tickets else "","first_train_no": ticket.get("first_train_no"),"second_train_no": ticket.get("second_train_no"),"train_count": ticket.get("train_count"),"ticketList": interline_tickets,"same_station": ticket.get("same_station") == "0","same_train": ticket.get("same_train") == "Y","wait_time": ticket.get("wait_time")})
    return result


def format_interlines_info(interlines_info: list[dict[str, Any]]) -> str:
    result = "出发时间 -> 到达时间 | 出发车站 -> 中转车站 -> 到达车站 | 换乘标志 |换乘等待时间| 总历时\n\n"
    for interlineInfo in interlines_info:
        line = f"{interlineInfo['start_date']} {interlineInfo['start_time']} -> {interlineInfo['arrive_date']} {interlineInfo['arrive_time']} | {interlineInfo['from_station_name']} -> {interlineInfo['middle_station_name']} -> {interlineInfo['end_station_name']} | "
        transfer = "同车换乘" if interlineInfo.get("same_train") else ("同站换乘" if interlineInfo.get("same_station") else "换站换乘")
        line += f"{transfer} | {interlineInfo['wait_time']} | {interlineInfo['lishi']}\n\n"
        line += "\t" + format_tickets_info(interlineInfo.get("ticketList", [])).replace("\n", "\n\t") + "\n"
        result += line
    return result

def parse_stations_data(raw_data: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    data_array = raw_data.split("|")
    data_list = [data_array[i : i + 10] for i in range(0, len(data_array) // 10 * 10, 10)]
    for group in data_list:
        station = {k: (group[idx] if idx < len(group) else "") for idx, k in enumerate(STATION_DATA_KEYS)}
        code = station.get("station_code")
        if code:
            result[code] = station
    return result


def extract_lishi(all_lishi: str) -> str:
    match = re.search(r"(?:(\d+)小时)?(\d+?)分钟", all_lishi)
    if not match:
        raise ValueError("extractLishi失败，没有匹配到关键词")
    hour = match.group(1)
    minute = match.group(2)
    return f"00:{minute}" if not hour else f"{hour.zfill(2)}:{minute}"


def extract_prices(yp_info: str, seat_discount_info: str, ticket_data: dict[str, Any]) -> list[dict[str, Any]]:
    PRICE_STR_LENGTH = 10
    DISCOUNT_STR_LENGTH = 5
    prices: list[dict[str, Any]] = []
    discounts: dict[str, int] = {}
    for i in range(len(seat_discount_info) // DISCOUNT_STR_LENGTH):
        discount_str = seat_discount_info[i * DISCOUNT_STR_LENGTH : (i + 1) * DISCOUNT_STR_LENGTH]
        if len(discount_str) == DISCOUNT_STR_LENGTH:
            discounts[discount_str[0]] = int(discount_str[1:])
    for i in range(len(yp_info) // PRICE_STR_LENGTH):
        price_str = yp_info[i * PRICE_STR_LENGTH : (i + 1) * PRICE_STR_LENGTH]
        if len(price_str) < PRICE_STR_LENGTH:
            continue
        if int(price_str[6:10]) >= 3000:
            seat_type_code = "W"
        elif price_str[0] not in SEAT_TYPES:
            seat_type_code = "H"
        else:
            seat_type_code = price_str[0]
        seat_type = SEAT_TYPES[seat_type_code]
        prices.append({"seat_name": seat_type["name"],"short": seat_type["short"],"seat_type_code": seat_type_code,"num": ticket_data.get(f"{seat_type['short']}_num", ""),"price": int(price_str[1:6]) / 10,"discount": discounts.get(seat_type_code)})
    return prices


def extract_dw_flags(dw_flag_str: str) -> list[str]:
    dw_flag_list = (dw_flag_str or "").split("#")
    result: list[str] = []
    if len(dw_flag_list) > 0 and dw_flag_list[0] == "5": result.append(DW_FLAGS[0])
    if len(dw_flag_list) > 1 and dw_flag_list[1] == "1": result.append(DW_FLAGS[1])
    if len(dw_flag_list) > 2:
        if dw_flag_list[2].startswith("Q"): result.append(DW_FLAGS[2])
        elif dw_flag_list[2].startswith("R"): result.append(DW_FLAGS[3])
    if len(dw_flag_list) > 5 and dw_flag_list[5] == "D": result.append(DW_FLAGS[4])
    if len(dw_flag_list) > 6 and dw_flag_list[6] != "z": result.append(DW_FLAGS[5])
    if len(dw_flag_list) > 7 and dw_flag_list[7] != "z": result.append(DW_FLAGS[6])
    return result


def check_date(date: str) -> bool:
    timezone = ZoneInfo("Asia/Shanghai")
    now = datetime.now(timezone).replace(hour=0, minute=0, second=0, microsecond=0)
    input_date = datetime.fromisoformat(date).astimezone(timezone).replace(hour=0, minute=0, second=0, microsecond=0)
    return input_date >= now


def make_12306_request(url: str, scheme: dict[str, str] | None = None, cookies: dict[str, str] | None = None, headers: dict[str, str] | None = None, return_text: bool = False) -> Any:
    scheme = scheme or {}
    headers = headers or {}
    query = urlencode(scheme)
    full_url = f"{url}?{query}" if query else url
    try:
        response = requests.get(full_url, cookies=cookies, headers=headers)
        if return_text:
            return response.text
        return response.json()
    except Exception as error:
        print(f"Error making 12306 request: {error}", file=sys.stderr)
        return None


def get_stations() -> dict[str, dict[str, str]]:
    html = make_12306_request(WEB_URL, return_text=True)
    if html is None or not isinstance(html, str): raise RuntimeError("Error: get 12306 web page failed.")
    match = re.search(r"\./script/core/common/station_name.+?\.js", html)
    if not match: raise RuntimeError("Error: get station name js file failed.")
    station_js = make_12306_request(WEB_URL + match.group(0)[1:], return_text=True)
    if station_js is None or not isinstance(station_js, str): raise RuntimeError("Error: get station name js file failed.")
    raw_match = re.search(r"station_names\s*=\s*'([^']+)'", station_js)
    if not raw_match: raise RuntimeError("Error: parse station names failed.")
    stations_data = parse_stations_data(raw_match.group(1))
    for station in MISSING_STATIONS:
        if station["station_code"] not in stations_data: stations_data[station["station_code"]] = station
    return stations_data


def get_lc_query_path() -> str:
    html = make_12306_request(LCQUERY_INIT_URL, return_text=True)
    if html is None or not isinstance(html, str): raise RuntimeError("Error: get 12306 web page failed.")
    match = re.search(r" var lc_search_url = '(.+?)'", html)
    if not match: raise RuntimeError("Error: get station name js file failed.")
    return match.group(1)


def init() -> None:
    global STATIONS, CITY_STATIONS, CITY_CODES, NAME_STATIONS, LCQUERY_PATH
    lcquery_path_cache_file = os.path.join(__file__, "..", "lcquery_path")
    if os.path.exists(lcquery_path_cache_file) and os.path.getmtime(lcquery_path_cache_file) > time.time() - 86400: # 缓存一天
        with open(lcquery_path_cache_file, "r", encoding="utf-8") as f:
            LCQUERY_PATH = f.read()
    else:
        LCQUERY_PATH = get_lc_query_path()
        with open(lcquery_path_cache_file, "w", encoding="utf-8") as f:
            f.write(LCQUERY_PATH)
    
    stations_cache_file = os.path.join(__file__, "..", "stations.json")
    if os.path.exists(stations_cache_file) and os.path.getmtime(stations_cache_file) > time.time() - 86400: # 缓存一天
        with open(stations_cache_file, "r", encoding="utf-8") as f:
            STATIONS = json.load(f)
    else:
        STATIONS = get_stations()
        with open(stations_cache_file, "w", encoding="utf-8") as f:
            json.dump(STATIONS, f, ensure_ascii=False)
    city_stations: dict[str, list[dict[str, str]]] = {}
    for station in STATIONS.values():
        city = station.get("city", "")
        city_stations.setdefault(city, []).append({"station_code": station["station_code"], "station_name": station["station_name"]})
    city_codes: dict[str, dict[str, str]] = {}
    for city, stations in city_stations.items():
        for station in stations:
            if station["station_name"] == city:
                city_codes[city] = station
                break
    name_stations: dict[str, dict[str, str]] = {}
    for station in STATIONS.values():
        name_stations[station["station_name"]] = {"station_code": station["station_code"],"station_name": station["station_name"]}
    CITY_STATIONS, CITY_CODES, NAME_STATIONS = city_stations, city_codes, name_stations


def tool_get_current_date() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")


def tool_refresh_cache() -> str:
    """手动刷新站点与查询路径缓存，强制重新执行一次初始化流程。"""
    lcquery_path_cache_file = os.path.join(__file__, "..", "lcquery_path")
    LCQUERY_PATH = get_lc_query_path()
    with open(lcquery_path_cache_file, "w", encoding="utf-8") as f:
        f.write(LCQUERY_PATH)
    
    stations_cache_file = os.path.join(__file__, "..", "stations.json")
    STATIONS = get_stations()
    with open(stations_cache_file, "w", encoding="utf-8") as f:
        json.dump(STATIONS, f, ensure_ascii=False)
    return "缓存刷新完成：已重新初始化站点数据与 lcquery 路径。"


def tool_get_stations_code_in_city(city: str) -> str:
    if city not in CITY_STATIONS:
        return "Error: City not found. "
    return json.dumps(CITY_STATIONS[city], ensure_ascii=False)


def tool_get_station_code_of_citys(citys: str) -> str:
    result: dict[str, Any] = {}
    for city in citys.split("|"):
        result[city] = CITY_CODES[city] if city in CITY_CODES else {"error": "未检索到城市。"}
    return json.dumps(result, ensure_ascii=False)


def tool_get_station_code_by_names(station_names: str) -> str:
    result: dict[str, Any] = {}
    for station_name in station_names.split("|"):
        station_name = station_name[:-1] if station_name.endswith("站") else station_name
        result[station_name] = NAME_STATIONS[station_name] if station_name in NAME_STATIONS else {"error": "未检索到城市。"}
    return json.dumps(result, ensure_ascii=False)


def tool_get_station_by_telecode(station_telecode: str) -> str:
    if station_telecode not in STATIONS:
        return "Error: Station not found. "
    return json.dumps(STATIONS[station_telecode], ensure_ascii=False)


def tool_get_tickets(
    date: str,
    from_station: str,
    to_station: str,
    train_filter_flags: str = "",
    earliest_start_time: int = 0,
    latest_start_time: int = 24,
    sort_flag: Literal["", "startTime", "arriveTime", "duration"] = "",
    sort_reverse: bool = False,
    limited_num: int = 0,
    format: Literal["text", "csv", "json"] = "text",
) -> str:
    if not check_date(date):
        return "Error: The date cannot be earlier than today."

    from_station_code = parse_station_code(from_station)
    to_station_code = parse_station_code(to_station)
    if from_station_code is None or to_station_code is None:
        return f"Error: Station not found. from_station_result: {from_station_code}, to_station_result: {to_station_code}."

    cookies = get_cookie()
    if not cookies:
        return "Error: Get cookie failed. Check your network."

    query_response = make_12306_request(
        f"{API_BASE}/otn/leftTicket/query",
        {
            "leftTicketDTO.train_date": date,
            "leftTicketDTO.from_station": from_station_code,
            "leftTicketDTO.to_station": to_station_code,
            "purpose_codes": "ADULT",
        },
        cookies=cookies,
    )
    if not query_response:
        return "Error: Get tickets data failed. "
    tickets_data = parse_tickets_data(query_response["data"]["result"])
    try:
        tickets_info = parse_tickets_info(tickets_data, query_response["data"]["map"])
    except Exception:
        return "Error: Parse tickets info failed. "

    filtered = filter_tickets_info(
        tickets_info,
        train_filter_flags,
        earliest_start_time,
        latest_start_time,
        sort_flag,
        sort_reverse,
        limited_num,
    )

    out_format = format.lower()
    if out_format == "csv":
        return format_tickets_info_csv(filtered)
    if out_format == "json":
        return json.dumps(filtered, ensure_ascii=False)
    return format_tickets_info(filtered)


def tool_get_interline_tickets(
    date: str,
    from_station: str,
    to_station: str,
    middle_station: str = "",
    show_wz: bool = False,
    train_filter_flags: str = "",
    earliest_start_time: int = 0,
    latest_start_time: int = 24,
    sort_flag: Literal["", "startTime", "arriveTime", "duration"] = "",
    sort_reverse: bool = False,
    limited_num: int = 10,
    format: Literal["text", "json"] = "text",
) -> str:
    if not check_date(date):
        return "Error: The date cannot be earlier than today."

    from_station_code = parse_station_code(from_station)
    to_station_code = parse_station_code(to_station)
    middle_station_code = parse_station_code(middle_station)
    if from_station_code is None or to_station_code is None or (middle_station != "" and middle_station_code is None):
        return (
            f"Error: Station not found. from_station_result: {from_station_code}, to_station_result: {to_station_code}, middle_station_result: {middle_station_code}"
        )

    cookies = get_cookie()
    if not cookies:
        return "Error: Get cookie failed. Check your network."

    query_url = f"{API_BASE}{LCQUERY_PATH}"
    limited_num = int(limited_num)
    interline_data: list[dict[str, Any]] = []
    query_params = {
        "train_date": date,
        "from_station_telecode": from_station_code,
        "to_station_telecode": to_station_code,
        "middle_station": middle_station_code or "",
        "result_index": "0",
        "can_query": "Y",
        "isShowWZ": "Y" if show_wz else "N",
        "purpose_codes": "00",
        "channel": "E",
    }

    while len(interline_data) < limited_num:
        query_response = make_12306_request(query_url, query_params, cookies=cookies)
        if not query_response:
            return "Error: request interline tickets data failed. "
        if isinstance(query_response.get("data"), str):
            return f"很抱歉，未查到相关的列车余票。({query_response.get('errorMsg', '')})"

        data = query_response["data"]
        interline_data.extend(data.get("middleList", []))
        if data.get("can_query") == "N":
            break
        query_params["result_index"] = str(data.get("result_index", "0"))

    try:
        interline_info = parse_interlines_info(interline_data)
    except Exception as error:
        return f"Error: parse tickets info failed. {error}"

    filtered = filter_tickets_info(
        interline_info,
        train_filter_flags,
        earliest_start_time,
        latest_start_time,
        sort_flag,
        sort_reverse,
        limited_num,
    )

    return json.dumps(filtered, ensure_ascii=False) if format.lower() == "json" else format_interlines_info(filtered)


def tool_get_train_route_stations(train_code: str, depart_date: str, format: Literal["text", "json"] = "text") -> str:
    search_response = make_12306_request(
        f"{SEARCH_API_BASE}/search/v1/train/search",
        {"keyword": train_code, "date": depart_date.replace("-", "")},
    )
    if not search_response or not search_response.get("data"):
        return "很抱歉，未查询到对应车次。"

    cookies = get_cookie()
    if not cookies:
        return "Error: get cookie failed. Check your network."

    search_data = search_response["data"][0]
    query_response = make_12306_request(
        f"{API_BASE}/otn/queryTrainInfo/query",
        {
            "leftTicketDTO.train_no": search_data["train_no"],
            "leftTicketDTO.train_date": depart_date,
            "rand_code": "",
        },
        cookies=cookies,
    )
    if not query_response or query_response.get("data") is None:
        return "Error: get train route stations failed. "

    route_info = parse_route_stations_info(query_response["data"].get("data", []))
    if not route_info:
        return "未查询到相关车次信息。"
    return json.dumps(route_info, ensure_ascii=False) if format.lower() == "json" else format_route_stations_info(route_info)


TOOL_NAMES = [
    "refresh-cache",
    "get-current-date",
    "get-stations-code-in-city",
    "get-station-code-of-citys",
    "get-station-code-by-names",
    "get-station-by-telecode",
    "get-tickets",
    "get-interline-tickets",
    "get-train-route-stations",
]


def list_tools() -> dict[str, Any]:
    return {"tools": TOOL_NAMES, "version": VERSION}


def run_tool(tool_name: Literal["list-tools", "refresh-cache", "get-current-date", "get-stations-code-in-city", "get-station-code-of-citys", "get-station-code-by-names", "get-station-by-telecode", "get-tickets", "get-interline-tickets", "get-train-route-stations"], **kwargs: Any) -> str:
    init()
    if tool_name == "list-tools":
        return json.dumps(list_tools(), ensure_ascii=False)
    if tool_name == "refresh-cache":
        return tool_refresh_cache()
    if tool_name == "get-current-date":
        return tool_get_current_date()
    if tool_name == "get-stations-code-in-city":
        return tool_get_stations_code_in_city(kwargs["city"])
    if tool_name == "get-station-code-of-citys":
        return tool_get_station_code_of_citys(kwargs["citys"])
    if tool_name == "get-station-code-by-names":
        return tool_get_station_code_by_names(kwargs["station_names"])
    if tool_name == "get-station-by-telecode":
        return tool_get_station_by_telecode(kwargs["station_telecode"])
    if tool_name == "get-tickets":
        return tool_get_tickets(
            date=kwargs["date"],
            from_station=kwargs["from_station"],
            to_station=kwargs["to_station"],
            train_filter_flags=kwargs.get("train_filter_flags", ""),
            earliest_start_time=kwargs.get("earliest_start_time", 0),
            latest_start_time=kwargs.get("latest_start_time", 24),
            sort_flag=kwargs.get("sort_flag", ""),
            sort_reverse=kwargs.get("sort_reverse", False),
            limited_num=kwargs.get("limited_num", 0),
            format=kwargs.get("format", "text"),
        )
    if tool_name == "get-interline-tickets":
        return tool_get_interline_tickets(
            date=kwargs["date"],
            from_station=kwargs["from_station"],
            to_station=kwargs["to_station"],
            middle_station=kwargs.get("middle_station", ""),
            show_wz=kwargs.get("show_wz", False),
            train_filter_flags=kwargs.get("train_filter_flags", ""),
            earliest_start_time=kwargs.get("earliest_start_time", 0),
            latest_start_time=kwargs.get("latest_start_time", 24),
            sort_flag=kwargs.get("sort_flag", ""),
            sort_reverse=kwargs.get("sort_reverse", False),
            limited_num=kwargs.get("limited_num", 10),
            format=kwargs.get("format", "text"),
        )
    if tool_name == "get-train-route-stations":
        return tool_get_train_route_stations(
            train_code=kwargs["train_code"],
            depart_date=kwargs["depart_date"],
            format=kwargs.get("format", "text"),
        )
    raise KeyError(f"Unknown tool: {tool_name}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="12306 standalone skill tool runner")
    subparsers = parser.add_subparsers(dest="tool", required=True)

    subparsers.add_parser("list-tools", help="List available tools")
    subparsers.add_parser(
        "refresh-cache",
        help="Manually refresh local cache by re-running init() (stations data and lcquery path).",
    )
    subparsers.add_parser("get-current-date", help="Get current date in Asia/Shanghai")

    p_city = subparsers.add_parser("get-stations-code-in-city", help="Get all station codes in a city")
    p_city.add_argument("--city", required=True)

    p_citys = subparsers.add_parser("get-station-code-of-citys", help="Get representative station code of city/cities")
    p_citys.add_argument("--citys", required=True)

    p_names = subparsers.add_parser("get-station-code-by-names", help="Get station codes by station names")
    p_names.add_argument("--station_names", required=True)

    p_tele = subparsers.add_parser("get-station-by-telecode", help="Get station detail by telecode")
    p_tele.add_argument("--station_telecode", required=True)

    p_tickets = subparsers.add_parser("get-tickets", help="Query 12306 tickets")
    p_tickets.add_argument("--date", required=True)
    p_tickets.add_argument("--from_station", required=True)
    p_tickets.add_argument("--to_station", required=True)
    p_tickets.add_argument("--train_filter_flags", default="")
    p_tickets.add_argument("--earliest_start_time", type=int, default=0)
    p_tickets.add_argument("--latest_start_time", type=int, default=24)
    p_tickets.add_argument("--sort_flag", default="")
    p_tickets.add_argument("--sort_reverse", action="store_true")
    p_tickets.add_argument("--limited_num", type=int, default=0)
    p_tickets.add_argument("--format", choices=["text", "csv", "json"], default="text")

    p_inter = subparsers.add_parser("get-interline-tickets", help="Query interline tickets")
    p_inter.add_argument("--date", required=True)
    p_inter.add_argument("--from_station", required=True)
    p_inter.add_argument("--to_station", required=True)
    p_inter.add_argument("--middle_station", default="")
    p_inter.add_argument("--show_wz", action="store_true")
    p_inter.add_argument("--train_filter_flags", default="")
    p_inter.add_argument("--earliest_start_time", type=int, default=0)
    p_inter.add_argument("--latest_start_time", type=int, default=24)
    p_inter.add_argument("--sort_flag", default="")
    p_inter.add_argument("--sort_reverse", action="store_true")
    p_inter.add_argument("--limited_num", type=int, default=10)
    p_inter.add_argument("--format", choices=["text", "json"], default="text")

    p_route = subparsers.add_parser("get-train-route-stations", help="Query train route stations")
    p_route.add_argument("--train_code", required=True)
    p_route.add_argument("--depart_date", required=True)
    p_route.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def _main() -> int:
    parser = _build_parser()
    ns = parser.parse_args()
    try:
        kwargs = vars(ns)
        tool_name = kwargs.pop("tool")
        print(run_tool(tool_name, **kwargs))
        return 0
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(_main())
