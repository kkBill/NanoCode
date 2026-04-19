# Ruff 配置说明

## 配置文件位置

`pyproject.toml`

## 配置内容

```toml
[tool.ruff]
line-length = 180           # 每行最长 180 个字符，超过就换行
target-version = "py311"    # 按 Python 3.11 语法标准处理（影响某些规则是否触发）

[tool.ruff.format]
quote-style = "double"      # 字符串统一用双引号 "，单引号 ' 会被自动转
indent-style = "space"      # 缩进用空格（而非 Tab）

[tool.ruff.lint]
select = ["E", "F", "I"]    # 启用三类检查规则
```

## 配置含义逐行解释

### `[tool.ruff]`

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `line-length` | `180` | 每行最长 180 个字符，超过自动换行 |
| `target-version` | `"py311"` | 按 Python 3.11 语法标准处理，影响某些规则是否触发 |

### `[tool.ruff.format]`

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `quote-style` | `"double"` | 字符串统一使用双引号 `"`，单引号 `'` 会被自动转换 |
| `indent-style` | `"space"` | 缩进使用空格，而非 Tab |

### `[tool.ruff.lint]`

| 代码 | 类别 | 检查内容 |
|------|------|----------|
| **E** | pycodestyle Errors | 代码风格错误，如 `a=1`（缺少空格）、行尾多余空格、空行不规范等 |
| **F** | Pyflakes | 逻辑错误，如导入未使用的模块、变量定义后未使用、`print(x)` 中 `x` 未定义等 |
| **I** | isort | import 排序，自动按 标准库 → 第三方库 → 本地模块 分组排序 |

## Ruff 的等价替代关系

Ruff 是一个**统一替换**方案，内部实现了多个旧工具的功能：

| 旧工具 | 功能 | Ruff 对应命令 |
|--------|------|--------------|
| `black` | 代码格式化 | `ruff format` |
| `flake8` | 代码检查 (lint) | `ruff check` 的 E + F 规则 |
| `isort` | import 排序 | `ruff check --select I` |

因此只需要安装一个 ruff，即可替代以前三个工具的组合。

## 常用命令

```bash
# 格式化代码
uv run ruff format nanocode/

# 自动修复 lint 错误（包括 import 排序）
uv run ruff check --select I --fix nanocode/

# 仅检查不修复
uv run ruff check nanocode/
```
