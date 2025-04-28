# CN-PAC

一个轻量、高效的代理自动配置（PAC）文件生成工具，专注于优化中国网站直连访问体验。

## 项目背景

这个项目源于我在使用代理工具时的实际需求：

- **轻量级直连方案**：虽然现代代理工具功能强大，但在某些场景下，我需要一个更轻量的 PAC 方案来加速直连访问。
- **应对 DNS 问题**：在实际使用中，我发现域名解析可能会受到系统 DNS 污染，因此本项目基于预定义的域名列表进行判断，不进行实时解析。
- **中国网站直连优化**：通过整合 ACL4SSR 的域名列表，确保中国网站能够直连访问，提高日常浏览体验。

这个项目参考了 gfw-pac 的思路，并根据个人使用需求进行了调整。PAC 文件在这里主要作为直连加速的辅助工具，可以与各种现代代理工具搭配使用，互为补充。

## 功能

- 自定义直连域名列表和代理域名列表
- 自动合并来自 [ACL4SSR](https://github.com/ACL4SSR/ACL4SSR) 的中国域名和局域网域名作为直连域名
- 内置对常见内网 IP 地址的识别和直连支持
- 通过 GitHub Actions 自动构建和发布 PAC 文件

## 使用方法

### 本地生成

1. 克隆此仓库
   ```bash
   git clone https://github.com/zed76r/cn-pac
   cd cn-pac
   ```

2. 编辑配置文件
   - `config/direct.txt` - 添加自定义直连域名
   - `config/proxy.txt` - 添加自定义代理域名

3. 运行脚本生成 PAC 文件
   ```bash
   python3 generate_pac.py
   ```

4. 生成的 PAC 文件位于 `output/proxy.pac`

### 命令行参数

脚本支持以下命令行参数，方便您根据需求自定义 PAC 文件：

```bash
python3 generate_pac.py [--proxy PROXY] [--direct DIRECT] [--default DEFAULT] [--skip-download] [--check-duplicates] [--help]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--proxy` | 设置代理服务器规则，用于访问代理域名 | `SOCKS5 127.0.0.1:%mixed-port%; DIRECT;` |
| `--direct` | 设置直连规则，用于访问直连域名和内网 IP | `DIRECT` |
| `--default` | 设置默认规则，用于不匹配任何规则的情况 | 与 `--proxy` 相同 |
| `--skip-download` | 跳过下载 ACL4SSR 中国域名列表 | - |
| `--check-duplicates` | 检查 direct.txt 中与 ACL4SSR 中国域名列表重复的域名，并在生成 PAC 文件时排除这些重复域名 | - |
| `--help` | 显示帮助信息 | - |

示例：

```bash
# 使用自定义代理服务器
python3 generate_pac.py --proxy "PROXY 192.168.1.100:8080; DIRECT"

# 设置默认使用代理
python3 generate_pac.py --default "PROXY 127.0.0.1:1080; DIRECT"

# 组合使用多个参数
python3 generate_pac.py --proxy "PROXY proxy.example.com:8080" --direct "DIRECT" --default "PROXY fallback.example.com:8080"

# 检查重复域名并自动移除
python3 generate_pac.py --check-duplicates

# 显示帮助信息
python3 generate_pac.py --help
```

### 使用预构建的 PAC 文件

您可以通过以下方式获取最新的预构建 PAC 文件：

- **直接下载**：[点击此处下载最新版本的 proxy.pac 文件](https://github.com/zed76r/cn-pac/releases/latest/download/proxy.pac)
- **查看所有版本**：访问 [GitHub Releases](https://github.com/zed76r/cn-pac/releases) 页面查看所有历史版本


## 配置说明

### 直连域名

在 `config/direct.txt` 文件中，每行一个域名：

```
example.com
example.org
```

### 代理域名

在 `config/proxy.txt` 文件中，每行一个域名：

```
google.com
github.com
```

## 自动构建

本项目使用 GitHub Actions 自动构建并发布 PAC 文件。每周会自动构建一次（每周一），并以日期作为 release 名称发布。此外，每当有代码推送到主分支时也会触发构建。

## 致谢

本项目参考或使用了以下开源项目的代码和数据，在此表示感谢：

- [gfw-pac](https://github.com/zhiyi7/gfw-pac) - PAC 文件生成的基础实现和模板
- [ACL4SSR](https://github.com/ACL4SSR/ACL4SSR) - 提供优质的中国域名列表
- [private-ip](https://github.com/frenchbread/private-ip) - 用于检测内网 IP 地址的正则表达式实现
- [GitHub Copilot](https://github.com/features/copilot) - 提供了智能代码建议和帮助优化脚本功能，特别是在重构代码结构、增强文件处理和添加命令行参数支持方面

这些优秀的开源项目和工具为本工具的开发提供了宝贵的参考和资源。

## 许可证

本项目采用 [MIT 许可证](LICENSE)。