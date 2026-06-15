# 领域研究工作流示例

> 场景：我想研究 "AI Coding Agent" 这个赛道，把小宇宙上相关播客全部拉下来做交叉分析。

## 完整流程

```bash
# 1. 登录（首次）
python3 xiaoyuzhou.py login

# 2. 用关键词搜索 → 找候选播客
python3 xiaoyuzhou.py search --keyword "Coding Agent" --type podcast --json > candidates.json

# 看一眼有哪些
cat candidates.json | python3 -c "
import json, sys
for p in json.load(sys.stdin):
    print(f'{p[\"pid\"]}  {p[\"title\"]:30}  订阅 {p.get(\"subscriptionCount\",0)}')
"
```

输出大概是：

```
63e9ef4de99bdef7d39944c8  AI炼金术          订阅 53958
6486ee4fe68894365df9ed14  叭叭呜            订阅 12345
...
```

## 一条命令批量拉

```bash
# 取 top 5 个相关播客 + 全量单集 + 逐字稿
python3 xiaoyuzhou.py batch \
  --keyword "Coding Agent" \
  --top-podcasts 5 \
  --with-transcript \
  --output-dir ./research/coding-agent
```

或者手动指定 pid（更精确）：

```bash
python3 xiaoyuzhou.py batch \
  --pids 63e9ef4de99bdef7d39944c8,6486ee4fe68894365df9ed14 \
  --with-transcript \
  --limit-per-podcast 30 \
  --output-dir ./research/coding-agent
```

## 喂给 LLM 做交叉分析

```bash
# 把所有 transcript 拼一起
find ./research/coding-agent -name "*.md" -exec cat {} \; > all-content.md

# 用 Claude / GPT 做总结
# 例: 通过 API 或者直接复制粘贴到对话窗口
claude "请阅读以下小宇宙播客的内容，总结：
1. 大家对 Coding Agent 的核心争议是什么？
2. 哪些产品被反复提及？
3. 创业者关注的痛点 top 5？

$(cat all-content.md)"
```

## 增量更新

后续再次运行同样的 `fetch` 命令，只会拉新增的单集，已有的会跳过。

```bash
# 每周跑一次，自动同步新单集
python3 xiaoyuzhou.py fetch --pid 63e9ef4de99bdef7d39944c8 --with-transcript
```

## 集成到知识库（Obsidian / 个人 KB）

输出目录直接是 Markdown，可以：

1. 把 `output_dir` 设为你的 Obsidian vault 子目录
2. 用任何全文检索工具索引（grep / ripgrep / SQLite FTS5）
3. 配合 Dataview 插件做 metadata 过滤

```bash
python3 xiaoyuzhou.py fetch \
  --pid xxx \
  --output-dir ~/Documents/ObsidianVault/Sources/Xiaoyuzhou
```

## 给 AI Agent 用的话术

如果你把这个 skill 装到 Claude Code / OpenClaw，可以直接说：

> "去小宇宙拉一下 AI Agent 相关的 5 个最热门播客，每个最多 20 集，连逐字稿一起，存到 ./research 目录。然后帮我总结大家对 Coding Agent 的核心争议。"

Agent 会自动：
1. 调用 `xiaoyuzhou.py search --keyword "AI Agent"`
2. 解析返回的 pid 列表，挑订阅数最高的 5 个
3. 调用 `xiaoyuzhou.py batch --pids ... --with-transcript --output-dir ./research`
4. 读取所有生成的 Markdown
5. 输出综述
