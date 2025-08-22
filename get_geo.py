#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Intelligent geocoding script for kindergartens and home addresses
智能地理编码脚本，确保获取精确的坐标信息

API频率限制说明：
- 高德地图API限制：最多3次/秒
- 本脚本严格遵守：每次API调用后等待400毫秒
- 实际频率：约2.5次/秒，确保不超过官方限制
"""

import json
import requests
import time
import os
from typing import Dict, List, Any, Optional

# 高德地图API配置
API_KEY = os.getenv("AMAP_API_KEY", "")
if not API_KEY:
    raise ValueError("AMAP_API_KEY environment variable is required")
GEOCODING_URL = "https://restapi.amap.com/v3/geocode/geo"

# 家庭住址列表
HOME_ADDRESSES = [
    "越秀·保利爱特城22栋",
    "中海誉东花园A7栋"
]

# 精确度级别要求：兴趣点级别表示位置比较精确
PRECISE_LEVELS = ["兴趣点", "门牌号", "单元号", "楼层", "房间", "门址"]

def load_existing_geocodes() -> Dict[str, Any]:
    """Load existing geocode data from geo.json"""
    geo_file = "data/geo.json"
    if os.path.exists(geo_file):
        try:
            with open(geo_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading existing geo.json: {e}")
            return {}
    return {}

def save_geocodes(geocodes: Dict[str, Any]) -> None:
    """Save geocode data to geo.json with only required fields"""
    os.makedirs("data", exist_ok=True)
    
    # 只保留必要字段
    cleaned_geocodes = {}
    for key, data in geocodes.items():
        if isinstance(data, dict) and 'location' in data:
            cleaned_geocodes[key] = {
                'province': data.get('province', ''),
                'city': data.get('city', ''),
                'district': data.get('district', ''),
                'location': data.get('location', ''),
                'level': data.get('level', '')
            }
        else:
            # 保持原有数据结构（如果已经是清理过的）
            cleaned_geocodes[key] = data
    
    with open("data/geo.json", 'w', encoding='utf-8') as f:
        json.dump(cleaned_geocodes, f, ensure_ascii=False, indent=2)

def get_geocode(address: str, city: str = "广州") -> Optional[Dict[str, Any]]:
    """
    Get geocoding information from Amap API
    获取地址的地理编码信息
    """
    params = {
        'key': API_KEY,
        'address': address,
        'city': city
    }
    
    try:
        response = requests.get(GEOCODING_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') == '1' and data.get('geocodes'):
            result = data['geocodes'][0] if data['geocodes'] else None
            if result:
                print(f"    API返回: {result.get('formatted_address', '')}")
                print(f"    精确度级别: {result.get('level', '未知')}")
                print(f"    坐标: {result.get('location', '无坐标')}")
            return result
        else:
            print(f"    地理编码失败: {data.get('info', 'Unknown error')}")
            return None
            
    except Exception as e:
        print(f"    API请求错误: {e}")
        return None
    finally:
        # 严格遵守3次/秒的API限制：每次调用后等待400毫秒
        # (1000ms ÷ 3 = 333.33ms，使用400ms更安全)
        time.sleep(0.4)

def geocode_with_fallback(name: str, address: str, city: str = "广州") -> Optional[Dict[str, Any]]:
    """
    智能地理编码：首先用名称，如果精确度不够则用地址
    """
    print(f"正在处理: {name}")
    
    # 第一步：尝试用名称获取坐标
    print(f"  步骤1: 用名称搜索 - {name}")
    name_result = get_geocode(name, city)
    
    # 检查名称搜索结果的精确度
    if name_result and name_result.get('level') in PRECISE_LEVELS:
        print(f"  ✓ 名称搜索成功，精确度足够 (级别: {name_result.get('level')})")
        return name_result
    
    # 第二步：如果名称搜索失败或精确度不够，用地址搜索
    if address:
        print(f"  步骤2: 用地址搜索 - {address}")
        address_result = get_geocode(address, city)
        
        if address_result:
            level = address_result.get('level', '')
            print(f"  ✓ 地址搜索成功 (级别: {level})")
            return address_result
        else:
            print(f"  ✗ 地址搜索也失败")
    else:
        print(f"  ✗ 名称搜索精确度不够且无地址信息")
    
    # 第三步：如果都失败了，检查名称搜索是否有结果（即使精确度不够）
    if name_result:
        level = name_result.get('level', '')
        print(f"  ⚠ 使用名称搜索结果，但精确度可能不够 (级别: {level})")
        return name_result
    
    print(f"  ✗ 完全失败，无法获取坐标")
    return None

def geocode_kindergartens() -> None:
    """
    为所有幼儿园进行智能地理编码
    """
    # Load kindergarten data
    with open('data/school.json', 'r', encoding='utf-8') as f:
        kindergartens = json.load(f)
    
    # Load existing geocodes
    geocodes = load_existing_geocodes()
    
    print(f"开始处理 {len(kindergartens)} 个幼儿园...")
    print("=" * 80)
    
    success_count = 0
    cache_hit_count = 0
    failed_count = 0
    improved_count = 0  # 重新获取到更精确坐标的数量
    
    for i, kg in enumerate(kindergartens):
        name = kg.get('幼儿园名称', '')
        address = kg.get('幼儿园地址', '')
        
        if not name:
            continue
            
        print(f"\n[{i+1}/{len(kindergartens)}] ", end="")
        
        # 检查是否已有缓存，以及缓存的精确度
        existing_data = geocodes.get(name)
        if existing_data:
            existing_level = existing_data.get('level', '')
            if existing_level in PRECISE_LEVELS:
                cache_hit_count += 1
                print(f"已缓存精确坐标: {name} (级别: {existing_level})")
                continue
            else:
                print(f"已有坐标但精确度不够，重新获取: {name} (当前级别: {existing_level})")
        
        # 进行智能地理编码
        geocode_result = geocode_with_fallback(name, address, "广州")
        
        if geocode_result:
            geocodes[name] = geocode_result
            if existing_data:
                improved_count += 1
                print(f"  ✓ 坐标已改进")
            else:
                success_count += 1
                print(f"  ✓ 新获取坐标")
        else:
            failed_count += 1
            print(f"  ✗ 获取坐标失败")
        
        # API频率控制已在get_geocode函数中处理
        
        # 定期保存进度
        if (i + 1) % 50 == 0:
            save_geocodes(geocodes)
            print(f"\n>>> 进度保存 - {i+1}/{len(kindergartens)} 已处理")
    
    print("\n" + "=" * 80)
    print("幼儿园地理编码完成！")
    print(f"新获取成功: {success_count}")
    print(f"坐标改进: {improved_count}")
    print(f"缓存命中: {cache_hit_count}")
    print(f"获取失败: {failed_count}")
    print(f"总计处理: {success_count + improved_count + cache_hit_count}")
    
    # 保存最终结果
    save_geocodes(geocodes)

def geocode_home_addresses() -> None:
    """
    为家庭住址进行地理编码
    """
    geocodes = load_existing_geocodes()
    
    print(f"开始处理 {len(HOME_ADDRESSES)} 个家庭住址...")
    print("=" * 50)
    
    for address in HOME_ADDRESSES:
        print(f"\n正在处理家庭住址: {address}")
        
        # 检查缓存
        if address in geocodes:
            existing_level = geocodes[address].get('level', '')
            print(f"已缓存: {address} (级别: {existing_level})")
            continue
        
        # 家庭住址直接用地址搜索
        geocode_result = get_geocode(address, "广州")
        
        if geocode_result:
            geocodes[address] = geocode_result
            print(f"✓ 获取成功")
        else:
            print(f"✗ 获取失败")
        
        # API频率控制已在get_geocode函数中处理
    
    print("\n家庭住址地理编码完成！")
    save_geocodes(geocodes)

def check_precision_summary():
    """检查并总结坐标精确度"""
    geocodes = load_existing_geocodes()
    
    level_stats = {}
    total = len(geocodes)
    
    for key, data in geocodes.items():
        level = data.get('level', '未知')
        level_stats[level] = level_stats.get(level, 0) + 1
    
    print("\n" + "=" * 50)
    print("坐标精确度统计:")
    print("=" * 50)
    
    for level, count in sorted(level_stats.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / total) * 100
        status = "✓ 精确" if level in PRECISE_LEVELS else "⚠ 可能不精确"
        print(f"{level:15} {count:3}个 ({percentage:5.1f}%) {status}")
    
    precise_count = sum(count for level, count in level_stats.items() if level in PRECISE_LEVELS)
    precise_percentage = (precise_count / total) * 100
    
    print("-" * 50)
    print(f"总计: {total}个地点")
    print(f"精确坐标: {precise_count}个 ({precise_percentage:.1f}%)")
    print(f"可能不精确: {total - precise_count}个 ({100 - precise_percentage:.1f}%)")

def main():
    """Main function"""
    print("开始智能地理编码处理...")
    print(f"API Key: {API_KEY[:10]}...")
    print(f"精确度要求: {', '.join(PRECISE_LEVELS)}")
    print("API频率控制: 严格遵守3次/秒限制，每次调用后等待400毫秒")
    print("预计处理时间: 由于API限制，处理速度较慢但更稳定")
    
    # 先处理家庭住址
    print("\n" + "="*50)
    print("第一步: 处理家庭住址")
    print("="*50)
    geocode_home_addresses()
    
    # 再处理幼儿园
    print("\n" + "="*50)
    print("第二步: 处理幼儿园")
    print("="*50)
    geocode_kindergartens()
    
    # 最后生成精确度报告
    check_precision_summary()
    
    print("\n" + "="*50)
    print("所有地理编码处理完成！")
    print("数据已保存到 data/geo.json")
    print("="*50)

if __name__ == "__main__":
    main()
