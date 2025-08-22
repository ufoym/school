#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Data parsing script for kindergarten information
解析幼儿园数据的脚本
"""

import csv
import json
import os
import sys
from typing import List, Dict, Any
import re


def clean_text(text: str) -> str:
    """Clean text by removing newlines, tabs, and extra whitespace"""
    if not text or text == "None":
        return ""
    
    # Remove newlines, carriage returns, and tabs
    text = text.replace('\n', '').replace('\r', '').replace('\t', ' ')
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    return text.strip()


def extract_pure_number(text: str) -> str:
    """Extract pure numeric value from fee text, removing currency symbols and formatting"""
    if not text or text == "None":
        return ""
    
    # Remove currency symbols, commas, and other formatting
    cleaned = text.replace('¥', '').replace('￥', '').replace(',', '').replace('元', '').replace('/', '').replace('月', '').replace('生', '')
    
    # Extract number using regex
    match = re.search(r'(\d+(?:\.\d+)?)', cleaned)
    if match:
        return match.group(1)
    
    return ""


def parse_multi_class_fee(fee_text: str) -> List[Dict[str, str]]:
    """
    Parse fee text that contains multiple class types and their corresponding fees.
    
    Examples:
    - "成长班2500国际班4000" -> [{"class": "成长班", "fee": "2500"}, {"class": "国际班", "fee": "4000"}]
    - "普通班：2800国际班：4800" -> [{"class": "普通班", "fee": "2800"}, {"class": "国际班", "fee": "4800"}]
    - "成长班¥2,500.00国际班4000" -> [{"class": "成长班", "fee": "2500.00"}, {"class": "国际班", "fee": "4000"}]
    
    Returns:
        List of dictionaries containing class name and fee, or single entry if no multiple classes found
    """
    if not fee_text:
        return [{"class": "", "fee": ""}]
    
    # Clean the fee text by removing currency symbols and unnecessary chars
    cleaned_text = fee_text.replace('¥', '').replace('￥', '').replace(',', '')
    
    # Pattern to match class names followed by fees
    # Supports formats like "成长班2500国际班4000" or "普通班：2800国际班：4800"
    # Updated pattern to be more precise and handle Chinese characters
    pattern = r'([\u4e00-\u9fff]+班)[:：]?(\d+(?:\.\d+)?)'
    matches = re.findall(pattern, cleaned_text)
    
    if len(matches) > 1:
        # Multiple classes found
        result = []
        for class_name, fee in matches:
            class_name = class_name.strip()
            fee = extract_pure_number(fee.strip())
            result.append({"class": class_name, "fee": fee})
        return result
    else:
        # Single fee or unrecognized format, extract pure number
        pure_fee = extract_pure_number(fee_text)
        return [{"class": "", "fee": pure_fee}]


def create_kindergarten_entries(base_data: Dict[str, Any], fee_classes: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    Create multiple kindergarten entries from a single base entry with multiple class fees.
    
    Args:
        base_data: The original kindergarten data
        fee_classes: List of class and fee pairs
    
    Returns:
        List of kindergarten entries, one for each class
    """
    entries = []
    
    for fee_class in fee_classes:
        # Create a copy of the base data
        entry = base_data.copy()
        
        # Update the fee
        entry["保教费收费标准（元/月/生）"] = fee_class["fee"]
        
        # Update the name if there's a class name
        if fee_class["class"]:
            original_name = entry["幼儿园名称"]
            entry["幼儿园名称"] = f"{original_name}（{fee_class['class']}）"
        
        entries.append(entry)
    
    return entries

try:
    import PyPDF2
except ImportError:
    try:
        import pdfplumber
    except ImportError:
        print("Error: Please install PyPDF2 or pdfplumber to parse PDF files")
        print("Run: pip install PyPDF2 or pip install pdfplumber")
        sys.exit(1)


def parse_csv_file(csv_path: str) -> List[Dict[str, Any]]:
    """Parse CSV file and extract kindergarten data"""
    kindergartens = []
    
    with open(csv_path, 'r', encoding='utf-8') as file:
        # Skip the first two header lines
        lines = file.readlines()[2:]
        
        # Create CSV reader from the remaining lines
        csv_reader = csv.reader(lines)
        
        for row in csv_reader:
            # Skip empty rows, rows with insufficient data, or header row
            if len(row) < 10 or not row[1].strip() or row[1] == "幼儿园名称":
                continue
                
            # Extract data from CSV row and clean text
            name = clean_text(row[1])
            office_nature = clean_text(row[3])
            is_inclusive = clean_text(row[4])
            scale = clean_text(row[5])
            address = clean_text(row[6])
            fee = clean_text(row[8])
            phone = clean_text(row[9])
            
            # Apply business logic for "是否普惠"
            if "民办" in office_nature:
                if "普惠性民办园" in office_nature:
                    is_inclusive_final = "是"
                else:
                    is_inclusive_final = "否"
            else:
                is_inclusive_final = "是"
            
            # Create base kindergarten data
            base_data = {
                "幼儿园名称": name,
                "办园性质": office_nature,
                "是否普惠": is_inclusive_final,
                "规模（班）": scale,
                "幼儿园地址": address,
                "保教费收费标准（元/月/生）": fee,
                "幼儿园联系电话": phone
            }
            
            # Parse fee for multiple classes
            fee_classes = parse_multi_class_fee(fee)
            
            # Create entries (one for each class if multiple classes exist)
            entries = create_kindergarten_entries(base_data, fee_classes)
            kindergartens.extend(entries)
    
    return kindergartens


def parse_pdf_file(pdf_path: str) -> List[Dict[str, Any]]:
    """Parse PDF file and extract kindergarten data"""
    kindergartens = []
    
    try:
        import pdfplumber
        
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                # Try to extract table data
                tables = page.extract_tables()
                
                if tables:
                    for table in tables:
                        for row in table:
                            if not row or len(row) < 6:
                                continue
                            
                            # Skip header rows
                            if any(header in str(row) for header in ['序号', '镇街', '园所名称', '办园性质']):
                                continue
                            
                            try:
                                # Extract data based on PDF table structure
                                # Expected columns: 序号, 镇街, 园所名称, 是否镇街中心园, 办园性质, 地址, 招生联系电话, 班数, 小班人数, 保教费
                                if len(row) >= 10:
                                    name = clean_text(str(row[2]) if row[2] else "")
                                    office_nature = clean_text(str(row[4]) if row[4] else "")
                                    address = clean_text(str(row[5]) if row[5] else "")
                                    phone = clean_text(str(row[6]) if row[6] else "")
                                    scale = clean_text(str(row[7]) if row[7] else "")
                                    fee = clean_text(str(row[10]) if row[10] else "")
                                    
                                    # Skip if essential data is missing
                                    if not name or name == "None" or "幼儿园" not in name:
                                        continue
                                    
                                    # Determine 是否普惠 based on 办园性质
                                    if "民办" in office_nature:
                                        if "普惠" in office_nature or "民办普惠" in office_nature:
                                            is_inclusive = "是"
                                        else:
                                            is_inclusive = "否"
                                    else:
                                        is_inclusive = "是"  # 公办默认为普惠
                                    
                                    # Create base kindergarten data
                                    base_data = {
                                        "幼儿园名称": name,
                                        "办园性质": office_nature,
                                        "是否普惠": is_inclusive,
                                        "规模（班）": scale,
                                        "幼儿园地址": address,
                                        "保教费收费标准（元/月/生）": fee,
                                        "幼儿园联系电话": phone
                                    }
                                    
                                    # Parse fee for multiple classes
                                    fee_classes = parse_multi_class_fee(fee)
                                    
                                    # Create entries (one for each class if multiple classes exist)
                                    entries = create_kindergarten_entries(base_data, fee_classes)
                                    kindergartens.extend(entries)
                            except Exception as e:
                                continue
                
                # Fallback: try text extraction if table extraction fails
                if not tables:
                    text = page.extract_text() or ""
                    lines = text.split('\n')
                    
                    for line in lines:
                        line = line.strip()
                        if not line or "幼儿园" not in line:
                            continue
                        
                        # Try to parse structured text lines
                        # Look for patterns like: "序号 镇街 幼儿园名称 ... 信息"
                        parts = line.split()
                        if len(parts) >= 6:
                            for i, part in enumerate(parts):
                                if "幼儿园" in part:
                                    name = clean_text(part)
                                    
                                    # Try to extract other info from surrounding parts
                                    office_nature = ""
                                    address = ""
                                    phone = ""
                                    scale = ""
                                    fee = ""
                                    
                                    # Simple heuristic extraction
                                    for j in range(i+1, min(i+6, len(parts))):
                                        part_str = clean_text(parts[j])
                                        if "公办" in part_str or "民办" in part_str:
                                            office_nature = part_str
                                        elif re.match(r'^\d{3,4}-?\d{8}$', part_str) or re.match(r'^020-\d{8}$', part_str):
                                            phone = part_str
                                        elif re.match(r'^\d+$', part_str) and len(part_str) <= 3:
                                            if not scale:
                                                scale = part_str
                                            elif not fee:
                                                fee = part_str
                                        elif "广州" in part_str:
                                            address = part_str
                                    
                                    # Determine 是否普惠
                                    if "民办" in office_nature:
                                        if "普惠" in office_nature:
                                            is_inclusive = "是"
                                        else:
                                            is_inclusive = "否"
                                    else:
                                        is_inclusive = "是"
                                    
                                    # Create base kindergarten data
                                    base_data = {
                                        "幼儿园名称": name,
                                        "办园性质": office_nature,
                                        "是否普惠": is_inclusive,
                                        "规模（班）": scale,
                                        "幼儿园地址": address,
                                        "保教费收费标准（元/月/生）": fee,
                                        "幼儿园联系电话": phone
                                    }
                                    
                                    # Parse fee for multiple classes
                                    fee_classes = parse_multi_class_fee(fee)
                                    
                                    # Create entries (one for each class if multiple classes exist)
                                    entries = create_kindergarten_entries(base_data, fee_classes)
                                    kindergartens.extend(entries)
                                    break
    
    except Exception as e:
        print(f"Error parsing PDF file: {e}")
        print("Note: PDF parsing may require adjustments based on the actual file structure")
    
    return kindergartens


def main():
    """Main function to parse both files and output JSON"""
    # Define file paths
    csv_path = "data/raw/hp.csv"
    pdf_path = "data/raw/zc.pdf"
    output_path = "data/school.json"
    
    # Check if input files exist
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        return
    
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        return
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Parse CSV file
    print("Parsing CSV file...")
    csv_data = parse_csv_file(csv_path)
    print(f"Found {len(csv_data)} kindergartens in CSV file")
    
    # Parse PDF file
    print("Parsing PDF file...")
    pdf_data = parse_pdf_file(pdf_path)
    print(f"Found {len(pdf_data)} kindergartens in PDF file")
    
    # Combine data
    all_data = csv_data + pdf_data
    
    # Save to JSON file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    
    print(f"Data successfully saved to {output_path}")
    print(f"Total kindergartens: {len(all_data)}")


if __name__ == "__main__":
    main()
