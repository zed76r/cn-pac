#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
比较 ACL4SSR 中国域名列表和本地 direct.txt，
从 direct.txt 中删除那些已经存在于中国域名列表中的域名

使用方法:
    python3 clean_direct_with_cnlist.py
"""

import os
import urllib.request
import sys

# 中国域名列表 URL
CNLIST_URL = "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ChinaDomain.list"
DIRECT_TXT = "config/direct.txt"
TIMEOUT = 30  # 设置请求超时时间（秒）

def download_china_domains():
    """从 ACL4SSR 下载中国域名列表，区分 DOMAIN-SUFFIX 和 DOMAIN 类型"""
    print("正在下载 ACL4SSR 中国域名列表...")
    domain_suffixes = set()  # 后缀匹配
    domain_exacts = set()    # 全字匹配
    try:
        req = urllib.request.Request(CNLIST_URL)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            content = response.read().decode('utf-8')
            for line in content.splitlines():
                # 提取域名规则
                line = line.strip()
                if line.startswith('DOMAIN-SUFFIX,'):
                    # 提取形如 DOMAIN-SUFFIX,example.com 的域名作为后缀匹配
                    domain = line.split(',')[1].strip()
                    domain_suffixes.add(domain)  # 直接添加域名作为后缀
                elif line.startswith('DOMAIN,'):
                    # 提取形如 DOMAIN,example.com 的域名作为全字匹配
                    domain = line.split(',')[1].strip()
                    domain_exacts.add(domain)
        print(f"成功下载中国域名: {len(domain_suffixes)} 个后缀匹配, {len(domain_exacts)} 个全字匹配")
        return {"suffixes": domain_suffixes, "domains": domain_exacts}
    except Exception as e:
        print(f"下载中国域名列表失败: {e}")
        return {"suffixes": set(), "domains": set()}

def read_direct_file():
    """读取本地 direct.txt 文件，区分后缀匹配和全字匹配域名"""
    direct_domains = {"suffixes": [], "domains": []}
    # 用于保存原始格式的域名，用于回写
    original_domains = []
    comments = []
    try:
        with open(DIRECT_TXT, 'r', encoding='utf-8') as f:
            for line in f:
                line_strip = line.strip()
                if not line_strip:  # 空行
                    comments.append(line)
                elif line_strip.startswith('#'):  # 注释
                    comments.append(line)
                else:  # 域名
                    original_domains.append(line_strip)
                    if line_strip.startswith('.'):
                        # 以.开头的是后缀匹配规则，但需要去掉前面的.进行比较
                        direct_domains["suffixes"].append(line_strip[1:])
                    else:
                        # 不以.开头的是全字匹配规则
                        direct_domains["domains"].append(line_strip)
        print(f"从 {DIRECT_TXT} 中读取了 {len(original_domains)} 个域名")
        return direct_domains, original_domains, comments
    except Exception as e:
        print(f"读取 {DIRECT_TXT} 失败: {e}")
        return {"suffixes": [], "domains": []}, [], []

def check_duplicate_domains(china_domains, direct_domains, original_domains):
    """
    检查重复的域名，并返回重复域名信息以及清理后的域名列表
    
    Args:
        china_domains: 中国域名字典，包含 "suffixes" 和 "domains" 键
        direct_domains: 自定义直连域名字典，包含 "suffixes" 和 "domains" 键
        original_domains: 原始域名列表（保留格式）
    
    Returns:
        duplicates: 完全匹配的重复域名列表
        child_domains: 包含(子域名,父域名)的元组列表
        clean_domains: 清理后的原始格式域名列表
    """
    duplicates = []
    child_domains = []
    
    # 创建原始域名到处理后域名的映射
    domain_map = {}
    for domain in original_domains:
        if domain.startswith('.'):
            domain_map[domain[1:]] = domain  # .example.com -> example.com
        else:
            domain_map[domain] = domain      # example.com -> example.com
    
    # 标记需要删除的域名
    domains_to_remove = set()
    
    # 1. 检查完全匹配的后缀
    cn_suffixes = china_domains.get("suffixes", set())
    direct_suffixes = direct_domains.get("suffixes", [])
    
    for custom_suffix in direct_suffixes:
        # 检查是否在中国域名后缀列表中
        if custom_suffix in cn_suffixes:
            duplicates.append(domain_map[custom_suffix])  # 用原始格式
            domains_to_remove.add(custom_suffix)
            continue
            
        # 检查是否是中国域名后缀的子域名
        domain_parts = custom_suffix.split('.')
        for i in range(1, len(domain_parts)):
            parent_domain = '.'.join(domain_parts[i:])
            if parent_domain in cn_suffixes:
                child_domains.append((domain_map[custom_suffix], parent_domain))  # 用原始格式
                domains_to_remove.add(custom_suffix)
                break
    
    # 2. 检查完全匹配的域名
    cn_exact_domains = china_domains.get("domains", set())
    direct_exact_domains = direct_domains.get("domains", [])
    
    for custom_domain in direct_exact_domains:
        # 检查是否在中国域名完全匹配列表中
        if custom_domain in cn_exact_domains:
            duplicates.append(domain_map[custom_domain])  # 用原始格式
            domains_to_remove.add(custom_domain)
            continue
            
        # 检查是否是中国域名后缀的子域名
        domain_parts = custom_domain.split('.')
        for i in range(1, len(domain_parts)):
            parent_domain = '.'.join(domain_parts[i:])
            if parent_domain in cn_suffixes:
                child_domains.append((domain_map[custom_domain], parent_domain))  # 用原始格式
                domains_to_remove.add(custom_domain)
                break
    
    # 构建清理后的原始格式域名列表
    clean_domains = [domain for domain in original_domains if domain_map.get(domain, domain) not in domains_to_remove and 
                    (domain.startswith('.') and domain[1:] not in domains_to_remove or not domain.startswith('.') and domain not in domains_to_remove)]
    
    return duplicates, child_domains, clean_domains

def save_direct_file(clean_domains, comments):
    """
    保存域名列表到文件，保留原始格式
    
    Args:
        clean_domains: 清理后的原始格式域名列表
        comments: 注释和空行列表
    
    Returns:
        bool: 保存是否成功
    """
    try:
        with open(DIRECT_TXT, 'w', encoding='utf-8') as f:
            # 写入注释
            for comment in comments:
                f.write(comment)
            
            # 写入域名
            for domain in clean_domains:
                f.write(domain + '\n')
        
        print(f"已成功更新 {DIRECT_TXT}")
        return True
    except Exception as e:
        print(f"保存文件失败: {e}")
        return False

def main():
    # 下载中国域名列表
    china_domains = download_china_domains()
    if not china_domains.get("suffixes") and not china_domains.get("domains"):
        print("无法获取中国域名列表，退出程序")
        return
    
    # 读取 direct.txt
    direct_domains, original_domains, comments = read_direct_file()
    if not direct_domains.get("suffixes") and not direct_domains.get("domains"):
        print("无法读取 direct.txt 或文件为空，退出程序")
        return
    
    # 检查重复域名并获取清理过的域名列表
    duplicates, child_domains, clean_domains = check_duplicate_domains(china_domains, direct_domains, original_domains)
    
    # 输出统计信息
    print(f"\n发现 {len(duplicates)} 个与中国域名列表完全匹配的域名")
    print(f"发现 {len(child_domains)} 个是中国域名列表中域名的子域名")
    
    # 如果有重复项或子域名，询问是否删除
    if duplicates or child_domains:
        # 输出重复域名
        if duplicates:
            print("\n以下域名在中国域名列表中已存在:")
            for domain in sorted(duplicates):
                print(f"- {domain}")
        
        # 输出子域名
        if child_domains:
            print("\n以下域名是中国域名列表中域名的子域名:")
            for child, parent in sorted(child_domains):
                print(f"- {child} (父域名: {parent})")
        
        # 询问是否继续
        choice = input("\n是否要从 direct.txt 中删除这些域名？(y/n): ")
        if choice.lower() != 'y':
            print("操作已取消")
            return
        
        # 保存清理后的文件
        if save_direct_file(clean_domains, comments):
            print(f"\n成功从 {DIRECT_TXT} 中删除了 {len(duplicates) + len(child_domains)} 个域名")
            print(f"原始域名数量: {len(original_domains)}")
            print(f"清理后域名数量: {len(clean_domains)}")
        else:
            print("\n清理操作失败")
    else:
        print(f"\n{DIRECT_TXT} 中没有发现与中国域名列表重复的域名")

if __name__ == "__main__":
    main()