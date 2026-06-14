# workstreams/ — 进行中的工作台

一个 **workstream** = 围绕某个主题/任务的进行中工作区：草稿、提纲、合成中间产物、待办。它介于 `sources/`（底稿）和 `deliverables/`（成品）之间。

```
workstreams/
└── <主题slug>/
    ├── brief.md       # 这件事是什么、目标、引用了哪些来源、下一步
    └── ...            # 草稿、片段、笔记
```

定稿后，把成品移到 `deliverables/<去向>/`，workstream 可保留作过程留痕或删除。

> `_example-workstream/` 为示例，采用后删除。
