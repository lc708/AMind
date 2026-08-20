# AMind · Nuwa v1 release

Nuwa v1 是一份从冻结证据中归纳 Anthropic 思想结构的可复算首版。发布包包含来源绑定的段落、52,225 条原子主张、归属与版本审计、主题映射、代表证据、人物声音差异和发布前评测。

## 人口

- 1,351 个分析单位；其中 1,348 个有正文，3 个为有证据边界的 unavailable 例外；
- 13,436 个无重叠证据段；
- 52,225 条逐字引句回链的原子主张；
- 9 个非互斥归纳主题、54 条逐条复核的代表证据。

## 从哪里开始

1. 阅读 `reports/synthesis.zh-CN.md` 获取首版结论；
2. 阅读 `reports/evaluation.zh-CN.md` 了解评测与限制；
3. 用 `data/synthesis-evidence.jsonl` 回查代表证据；
4. 用 `data/atomic-claims.jsonl.gz`、`data/passages.jsonl.gz` 和 `data/analysis-units.jsonl.gz` 做全量复算；
5. 用 `manifest.json` 校验每个源文件与发布文件的 SHA-256。

gzip 文件使用确定性压缩（mtime=0），解压后字节哈希记录在 manifest 中。

## 解释边界

- 主题频次是覆盖信号，不是共识投票；
- 机构口径不自动等于个人观点；
- 研究问题不当作已得到的答案；
- 语义矛盾筛查不声称完备；
- 54 条代表证据做了完整段落语义复核，但不声称 52,225 条主张全部经过逐条人工语义复核；
- 本包不含 13GB 本地原始抓取与历史证据库；它保留发布所需的来源绑定段落、主张和哈希链。
