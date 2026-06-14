# sources/getnote/ — 得到 / Get笔记 (Biji)

从「得到 / Get笔记」(Biji) 拉回的笔记。由 `scripts/pull-getnote.sh`（Biji OpenAPI）写入。

- 文件名：`YYYY-MM-DD_<note_id>_<标题slug>.md`
- frontmatter：`source: getnote` · `channel: 得到/Biji` · `type: note` · `captured:` · `note_id:`

拉取/查询见 `get-biji` 技能（`.claude/skills/get-biji/`）。凭证在仓库根 `.env.local`。

> `_example-*.md` 为示例，采用后删除。
