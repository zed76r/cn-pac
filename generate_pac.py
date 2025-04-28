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

def download_domain_list(url, skip_download=False, desc="域名列表"):
    """通用的域名列表下载和解析函数，区分 DOMAIN-SUFFIX 和 DOMAIN 类型"""
    if skip_download:
        print(f"跳过下载{desc}...")
        return {"suffixes": set(), "domains": set()}
    print(f"正在下载 {desc}...")
    domain_suffixes = set()
    domain_exacts = set()
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            content = response.read().decode('utf-8')
            for line in content.splitlines():
                line = line.strip()
                if line.startswith('DOMAIN-SUFFIX,'):
                    domain = line.split(',')[1].strip()
                    domain_suffixes.add(domain)
                elif line.startswith('DOMAIN,'):
                    domain = line.split(',')[1].strip()
                    domain_exacts.add(domain)
        print(f"成功下载{desc}: {len(domain_suffixes)} 个后缀匹配, {len(domain_exacts)} 个全字匹配")
        return {"suffixes": domain_suffixes, "domains": domain_exacts}
    except Exception as e:
        print(f"下载{desc}失败: {e}")
        return {"suffixes": set(), "domains": set()}

def download_china_domains(skip_download=False):
    """下载中国域名列表，调用通用下载函数"""
    return download_domain_list(CNLIST_URL, skip_download, "ACL4SSR 中国域名列表")

def download_localarea_domains(skip_download=False):
    """下载局域网域名列表，调用通用下载函数"""
    return download_domain_list(LOCALAREA_URL, skip_download, "ACL4SSR 局域网域名列表")

def read_domain_file(filename):
    """读取域名文件，根据是否以.开头来区分后缀匹配和全字匹配"""
    domains = {"suffixes": set(), "domains": set()}
    
    with open(filename, "r") as f:
        for line in f:
            domain = line.strip()
            if domain and not domain.startswith("#"):
                if domain.startswith("."):
                    # 以.开头的是后缀匹配规则，但需要去掉前面的.
                    domains["suffixes"].add(domain[1:])
                else:
                    # 不以.开头的是全字匹配规则
                    domains["domains"].add(domain)
    
    return domains

def format_domain_lists_for_pac(domain_dict, local_domains=None):
    """格式化域名列表为PAC文件需要的JSON格式，分别处理后缀和全字匹配域名"""
    # 初始化返回字典
    result = {
        "suffixes": "",
        "domains": ""
    }
    
    # 处理后缀匹配域名
    if "suffixes" in domain_dict and domain_dict["suffixes"]:
        suffix_domains = list(sorted(domain_dict["suffixes"]))
        result["suffixes"] = json.dumps(suffix_domains, ensure_ascii=False)
    else:
        result["suffixes"] = "[]"
    
    # 处理全字匹配域名
    if "domains" in domain_dict and domain_dict["domains"]:
        exact_domains = list(sorted(domain_dict["domains"]))
        result["domains"] = json.dumps(exact_domains, ensure_ascii=False)
    else:
        result["domains"] = "[]"
    
    return result

def check_duplicate_domains(china_domains, custom_domains):
    """检查自定义直连域名中哪些已经存在于中国域名列表中，并返回清理后的域名列表"""
    def check_duplicates_and_subdomains(custom_set, base_set, label):
        duplicates = []
        clean_set = set(custom_set)
        # 完全匹配
        matched = custom_set & base_set
        if matched:
            duplicates.extend(list(matched))
            clean_set -= matched
        # 子域名匹配
        for item in list(clean_set):
            parts = item.split('.')
            for i in range(1, len(parts)):
                parent = '.'.join(parts[i:])
                if parent in base_set:
                    duplicates.append(f"{item} (子域名匹配: {parent})")
                    clean_set.remove(item)
                    break
        return duplicates, clean_set

    duplicate_domains = []
    clean_domains = {"suffixes": set(), "domains": set()}

    # 后缀匹配
    dups, clean = check_duplicates_and_subdomains(
        custom_domains.get("suffixes", set()),
        china_domains.get("suffixes", set()),
        "后缀"
    )
    duplicate_domains.extend(dups)
    clean_domains["suffixes"] = clean

    # 全字匹配
    dups, clean = check_duplicates_and_subdomains(
        custom_domains.get("domains", set()),
        china_domains.get("domains", set()),
        "全字"
    )
    duplicate_domains.extend(dups)
    clean_domains["domains"] = clean

    return duplicate_domains, clean_domains

def generate_pac(proxy=PROXY_SERVER, direct=DIRECT_RULE, default=DEFAULT_RULE, skip_download=False, check_duplicates=False):
    """生成 PAC 文件，区分后缀匹配和全字匹配域名"""
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
            f.write("# 以 . 开头的域名（如 .example.com）视为后缀匹配\n")
            f.write("# 其他域名（如 example.com）视为全字匹配\n")
    
    if not os.path.exists(proxy_config):
        with open(proxy_config, 'w', encoding='utf-8') as f:
            f.write("# 自定义代理域名列表，每行一个域名\n")
            f.write("# 以 . 开头的域名（如 .example.com）视为后缀匹配\n")
            f.write("# 其他域名（如 example.com）视为全字匹配\n")
    
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
            print(f"已自动移除重复域名，优化后的自定义直连域名数量: "
                 f"{len(custom_direct_domains['suffixes']) + len(custom_direct_domains['domains'])}")
    
    # 合并直连域名
    direct_domains = {
        "suffixes": set().union(
            localarea_domains.get("suffixes", set()),
            china_domains.get("suffixes", set()),
            custom_direct_domains.get("suffixes", set())
        ),
        "domains": set().union(
            localarea_domains.get("domains", set()),
            china_domains.get("domains", set()),
            custom_direct_domains.get("domains", set())
        )
    }
    
    print(f"局域网域名数量: {len(localarea_domains.get('suffixes', set())) + len(localarea_domains.get('domains', set()))}")
    print(f"中国域名数量: {len(china_domains.get('suffixes', set())) + len(china_domains.get('domains', set()))}")
    print(f"自定义直连域名数量: {len(custom_direct_domains.get('suffixes', set())) + len(custom_direct_domains.get('domains', set()))}")
    print(f"直连域名总数: {len(direct_domains.get('suffixes', set())) + len(direct_domains.get('domains', set()))}")
    print(f"代理域名总数: {len(proxy_domains.get('suffixes', set())) + len(proxy_domains.get('domains', set()))}")
    
    # 读取 PAC 模板
    try:
        with open(PAC_TEMPLATE, 'r', encoding='utf-8') as f:
            pac_template = f.read()
    except Exception as e:
        print(f"读取 PAC 模板失败: {e}")
        return False
    
    # 使用新的格式化函数处理域名列表
    formatted_direct_domains = format_domain_lists_for_pac(direct_domains, localarea_domains)
    formatted_proxy_domains = format_domain_lists_for_pac(proxy_domains)
    
    # 替换模板中的占位符
    pac_content = pac_template
    
    # 替换新的域名列表占位符
    pac_content = pac_content.replace("__DIRECT_DOMAIN_SUFFIXES__", formatted_direct_domains["suffixes"])
    pac_content = pac_content.replace("__DIRECT_DOMAIN_EXACTS__", formatted_direct_domains["domains"])
    pac_content = pac_content.replace("__PROXY_DOMAIN_SUFFIXES__", formatted_proxy_domains["suffixes"])
    pac_content = pac_content.replace("__PROXY_DOMAIN_EXACTS__", formatted_proxy_domains["domains"])
    
    # 替换其他占位符
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
    print("  --check-duplicates 检查 direct.txt 中与 ACL4SSR 中国域名列表重复的域名，并在生成 PAC 文件时排除这些重复域名")
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
