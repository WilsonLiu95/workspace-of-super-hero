# ai-image 配置示例 —— 复制为 config.local.sh（已被 .gitignore 忽略）填入真实值，
# 用前 `source` 一下；或直接把这些 export 写进你的 shell profile。
#
#   cp config.example.sh config.local.sh
#   # 编辑 config.local.sh 填入真实 key / endpoint
#   source .claude/skills/ai-image/config.local.sh
#
# 本模板不内置任何 key 或私有 endpoint（安全可分享）。采用者自带自己的：

export AIPROXY_API_KEY="your-api-key-here"
export AIPROXY_ENDPOINT="https://your-host/v1/images/generations"

# 可选：
# 多个 endpoint 用逗号分隔，按顺序尝试（前一个 5xx/网络错误时降级到下一个）
# export AIPROXY_ENDPOINT="https://primary-host/v1/images/generations,http://localhost:PORT/v1/images/generations"
# export AIPROXY_MODEL="gpt-image-2"
# export AIPROXY_FALLBACK_MODEL="gemini-3.1-flash-image"
