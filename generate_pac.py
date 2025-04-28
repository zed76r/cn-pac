#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import urllib.request
import re
from datetime import datetime

# 配置参数
CNLIST_URL = "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/ChinaDomain.list"
LOCALAREA_URL = "https://raw.githubusercontent.com/ACL4SSR/ACL4SSR/master/Clash/LocalAreaNetwork.list"
CONFIG_DIR = "config"
OUTPUT_DIR = "output"
PAC_TEMPLATE = "pac-template"
PROXY_SERVER = "SOCKS5 127.0.0.1:%mixed-port%; DIRECT;"  # 默认代理服务器
DIRECT_RULE = "DIRECT"  # 默认直连规则
DEFAULT_RULE = PROXY_SERVER  # 默认规则与代理服务器相同
TIMEOUT = 30  # 设置请求超时时间（秒）

def ensure_dir(directory):
    """确保目录存在，不存在则创建"""
    if not os.path.exists(directory):
        os.makedirs(directory)

def download_china_domains(skip_download=False):
    """从 ACL4SSR 下载中国域名列表"""
    if skip_download:
        print("跳过下载中国域名列表...")
        return set()
        
    print("正在下载 ACL4SSR 中国域名列表...")
    domains = set()
    try:
        req = urllib.request.Request(CNLIST_URL)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            content = response.read().decode('utf-8')
            for line in content.splitlines():
                # 提取域名规则
                line = line.strip()
                if line.startswith('DOMAIN-SUFFIX,'):
                    # 提取形如 DOMAIN-SUFFIX,example.com 的域名
                    domain = line.split(',')[1].strip()
                    domains.add(domain)
                elif line.startswith('DOMAIN,'):
                    # 提取形如 DOMAIN,example.com 的域名
                    domain = line.split(',')[1].strip()
                    domains.add(domain)
                # 直连关键词我们直接忽略，因为 PAC 不支持关键词匹配
        print(f"成功下载 {len(domains)} 个中国域名")
        return domains
    except Exception as e:
        print(f"下载中国域名列表失败: {e}")
        return set()

def download_localarea_domains(skip_download=False):
    """从 ACL4SSR 下载局域网域名列表"""
    if skip_download:
        print("跳过下载局域网域名列表...")
        return set()
        
    print("正在下载 ACL4SSR 局域网域名列表...")
    domains = set()
    try:
        req = urllib.request.Request(LOCALAREA_URL)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            content = response.read().decode('utf-8')
            for line in content.splitlines():
                # 提取域名规则
                line = line.strip()
                if line.startswith('DOMAIN-SUFFIX,'):
                    # 提取形如 DOMAIN-SUFFIX,example.com 的域名
                    domain = line.split(',')[1].strip()
                    domains.add(domain)
                elif line.startswith('DOMAIN,'):
                    # 提取形如 DOMAIN,example.com 的域名
                    domain = line.split(',')[1].strip()
                    domains.add(domain)
                # 其他规则类型（如 IP-CIDR）在 PAC 中不直接支持，已通过模板中的 isPrivateIP 函数处理
        print(f"成功下载 {len(domains)} 个局域网域名")
        return domains
    except Exception as e:
        print(f"下载局域网域名列表失败: {e}")
        return set()

def read_domain_file(filepath):
    """读取域名文件"""
    domains = set()
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        domains.add(line)
        return domains
    except Exception as e:
        print(f"读取 {filepath} 失败: {e}")
        return set()

def format_domains_for_pac(domains, localarea_domains=None):
    """格式化域名列表为 PAC 文件中的 JavaScript 数组格式（单行紧凑格式）
    
    如果提供了局域网域名列表，会确保这些域名排在最前面
    """
    if not domains:
        return "[]"
    
    if localarea_domains:
        # 确保局域网域名排在最前面
        # 先提取局域网域名（保持它们的顺序）
        local_list = sorted(list(localarea_domains))
        # 然后提取其他域名（排除已经包含的局域网域名）
        other_list = sorted(list(domains - localarea_domains))
        # 合并两个列表，局域网域名在前
        domains_list = local_list + other_list
    else:
        # 没有局域网域名列表，按正常方式排序
        domains_list = sorted(list(domains))
    
    # 使用紧凑格式，所有域名在一行中显示
    return json.dumps(domains_list, separators=(',', ':'))

def check_duplicate_domains(china_domains, custom_domains):
    """检查自定义直连域名中哪些已经存在于中国域名列表中，并返回清理后的域名列表
    
    Args:
        china_domains: 中国域名集合
        custom_domains: 自定义直连域名集合
    
    Returns:
        tuple: (重复的域名列表, 清理后的域名集合)
    """
    duplicate_domains = []
    duplicate_set = set()  # 记录所有需要移除的域名
    
    # 检查完全匹配的域名
    direct_duplicates = custom_domains.intersection(china_domains)
    if direct_duplicates:
        duplicate_domains.extend(list(direct_duplicates))
        duplicate_set.update(direct_duplicates)
    
    # 检查是否是中国域名的子域名
    for custom_domain in custom_domains:
        if custom_domain not in duplicate_set:  # 已经标记为重复的就不再检查
            domain_parts = custom_domain.split('.')
            for i in range(1, len(domain_parts)):
                parent_domain = '.'.join(domain_parts[i:])
                if parent_domain in china_domains:
                    duplicate_domains.append(f"{custom_domain} (子域名: {parent_domain})")
                    duplicate_set.add(custom_domain)  # 添加到需要移除的集合
                    break
    
    # 创建清理后的域名集合
    clean_domains = custom_domains - duplicate_set
    
    return duplicate_domains, clean_domains

def generate_pac(proxy=PROXY_SERVER, direct=DIRECT_RULE, default=DEFAULT_RULE, skip_download=False, check_duplicates=False):
    """生成 PAC 文件"""
    print("开始生成 PAC 文件...")
    
    # 确保配置和输出目录存在
    ensure_dir(CONFIG_DIR)
    ensure_dir(OUTPUT_DIR)
    
    # 创建默认的配置文件（如果不存在）
    direct_config = os.path.join(CONFIG_DIR, "direct.txt")
    proxy_config = os.path.join(CONFIG_DIR, "proxy.txt")
    
    if not os.path.exists(direct_config):
        with open(direct_config, 'w', encoding='utf-8') as f:
            f.write("# 自定义直连域名列表，每行一个域名\n")
    
    if not os.path.exists(proxy_config):
        with open(proxy_config, 'w', encoding='utf-8') as f:
            f.write("# 自定义代理域名列表，每行一个域名\n")
    
    # 读取域名列表 - 先下载局域网域名，再下载中国域名
    localarea_domains = download_localarea_domains(skip_download)
    china_domains = download_china_domains(skip_download)
    custom_direct_domains = read_domain_file(direct_config)
    proxy_domains = read_domain_file(proxy_config)
    
    # 如果需要检查重复域名
    if check_duplicates:
        duplicate_domains, clean_custom_direct_domains = check_duplicate_domains(china_domains, custom_direct_domains)
        if duplicate_domains:
            print("\n以下域名已存在于中国域名列表中，可以从 direct.txt 中移除：")
            for domain in sorted(duplicate_domains):
                print(f"- {domain}")
            print()
            
            # 使用去重后的域名数组替换原始域名数组
            custom_direct_domains = clean_custom_direct_domains
            print(f"已自动移除重复域名，优化后的自定义直连域名数量: {len(custom_direct_domains)}")
    
    # 合并直连域名（局域网域名优先，然后是中国域名和自定义直连域名）
    direct_domains = localarea_domains.union(china_domains).union(custom_direct_domains)
    
    print(f"局域网域名数量: {len(localarea_domains)}")
    print(f"中国域名数量: {len(china_domains)}")
    print(f"自定义直连域名数量: {len(custom_direct_domains)}")
    print(f"直连域名总数: {len(direct_domains)}")
    print(f"代理域名总数: {len(proxy_domains)}")
    
    # 读取 PAC 模板
    try:
        with open(PAC_TEMPLATE, 'r', encoding='utf-8') as f:
            pac_template = f.read()
    except Exception as e:
        print(f"读取 PAC 模板失败: {e}")
        return False
    
    # 替换模板中的占位符
    # 传入局域网域名列表，确保它们排在最前面
    direct_domains_json = format_domains_for_pac(direct_domains, localarea_domains)
    proxy_domains_json = format_domains_for_pac(proxy_domains)
    
    pac_content = pac_template.replace("__DIRECT_DOMAINS_PLACEHOLDER__", direct_domains_json)
    pac_content = pac_content.replace("__PROXY_DOMAINS_PLACEHOLDER__", proxy_domains_json)
    pac_content = pac_content.replace("{proxy}", proxy)
    pac_content = pac_content.replace("{direct}", direct)
    pac_content = pac_content.replace("{default}", default)
    
    # 写入 PAC 文件
    output_file = os.path.join(OUTPUT_DIR, "proxy.pac")
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(pac_content)
        print(f"PAC 文件已生成: {output_file}")
        return True
    except Exception as e:
        print(f"写入 PAC 文件失败: {e}")
        return False

def show_help():
    """显示帮助信息"""
    print("CN-PAC - 自动生成代理自动配置（PAC）文件的工具")
    print("\n用法: python3 generate_pac.py [选项]")
    print("\n选项:")
    print("  --proxy PROXY      设置代理服务器规则，用于访问代理域名")
    print(f"                     默认值: {PROXY_SERVER}")
    print("  --direct DIRECT    设置直连规则，用于访问直连域名和内网 IP")
    print(f"                     默认值: {DIRECT_RULE}")
    print("  --default DEFAULT  设置默认规则，用于不匹配任何规则的情况")
    print(f"                     默认值: 与 --proxy 相同")
    print("  --skip-download    跳过下载 ACL4SSR 中国域名列表")
    print("  --check-duplicates 检查并从 direct.txt 中自动移除与 ACL4SSR 中国域名列表重复的域名")
    print("  --help             显示此帮助信息\n")
    print("示例:")
    print("  python3 generate_pac.py --proxy \"PROXY 192.168.1.100:8080; DIRECT\"")
    print("  python3 generate_pac.py --direct \"DIRECT\" --default \"SOCKS5 127.0.0.1:1080; DIRECT\"")
    print("  python3 generate_pac.py --check-duplicates")

if __name__ == "__main__":
    # 支持命令行参数设置代理服务器和默认规则
    proxy = PROXY_SERVER
    direct = DIRECT_RULE
    default = DEFAULT_RULE
    skip_download = False
    check_duplicates = False
    
    # 解析命令行参数
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--proxy" and i+1 < len(sys.argv):
            proxy = sys.argv[i+1]
            i += 2
        elif sys.argv[i] == "--direct" and i+1 < len(sys.argv):
            direct = sys.argv[i+1]
            i += 2
        elif sys.argv[i] == "--default" and i+1 < len(sys.argv):
            default = sys.argv[i+1]
            i += 2
        elif sys.argv[i] == "--skip-download":
            skip_download = True
            i += 1
        elif sys.argv[i] == "--check-duplicates":
            check_duplicates = True
            i += 1
        elif sys.argv[i] == "--help":
            show_help()
            sys.exit(0)
        else:
            i += 1
    
    print(f"使用代理服务器: {proxy}")
    print(f"使用直连规则: {direct}")
    print(f"使用默认规则: {default}")
    if skip_download:
        print("跳过下载中国域名列表")
    if check_duplicates:
        print("将检查直连域名列表中的重复项")
    
    # 生成 PAC 文件
    if generate_pac(proxy, direct, default, skip_download, check_duplicates):
        print("PAC 文件生成成功！")
    else:
        print("PAC 文件生成失败！")
        sys.exit(1)