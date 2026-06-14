# deliverables/web/ — 线上 HTML

要发布成**可公开访问链接**的交付物。每个站点/页面一个子目录，产出**自包含** HTML（样式内联或同目录，少依赖外部资源）。

```
web/
└── <name>/
    └── index.html
```

## 发布（采用者自配，本模板不绑定托管）

本模板**不含任何托管账号**。选一个静态托管，把发布命令记在 `CLAUDE.md` §6，例如：

- Vercel：`vercel deploy deliverables/web/<name> --prod`
- Netlify：`netlify deploy --dir deliverables/web/<name> --prod`
- Cloudflare Pages：`wrangler pages deploy deliverables/web/<name>`
- GitHub Pages / 对象存储（COS·OSS·S3）/ `rsync 到自己服务器` 等亦可。

发布成功后，把可访问链接回填到对应交付物 frontmatter 的 `published_url`。

> 配图等素材放 `assets/`，在 HTML 里相对引用。`_example-report/` 为示例，采用后删除。
