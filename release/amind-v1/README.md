# AMind v1

AMind v1 是一份从冻结证据中归纳 Anthropic 思想结构的可复算研究发布。它不是模型、应用或 Codex 技能；阅读、检索和验证都不需要安装第三方依赖。

发布包包含来源绑定的段落、52,225 条原子主张、归属与版本审计、主题映射、代表证据、人物声音差异和发布前评测。

## 人口

- 1,351 个分析单位；其中 1,348 个有正文，3 个为有证据边界的 unavailable 例外；
- 13,436 个无重叠证据段；
- 52,225 条逐字引句回链的原子主张；
- 9 个非互斥归纳主题、54 条逐条复核的代表证据。

## 最快使用方式

1. 阅读 `reports/synthesis.zh-CN.md` 获取首版结论；
2. 阅读 `reports/evaluation.zh-CN.md` 了解评测与限制；
3. 用 `data/synthesis-evidence.jsonl` 回查代表证据；
4. 在本目录运行 `python3 -B amind.py summary` 查看概览；
5. 运行 `python3 -B amind.py search "alignment faking" --limit 5` 检索来源绑定主张；
6. 用 `manifest.json` 和仓库根目录的独立校验器核验每个文件的 SHA-256。

常用命令：

```bash
python3 -B amind.py summary
python3 -B amind.py themes
python3 -B amind.py search "model welfare" --limit 5
python3 -B amind.py show nuwa1-claim-f169332e5fa3d349672a254d
```

`amind.py` 只使用 Python 标准库，不联网、不修改数据。

## 给 AI 与 RAG 系统

不需要安装技能。小规模问答优先读取 `reports/synthesis.zh-CN.md` 与 `data/synthesis-evidence.jsonl`；需要全量检索时，流式读取 `data/atomic-claims.jsonl.gz`，再以 `analysis_unit_id` 连接 `data/analysis-units.jsonl.gz`。回答时应同时保留 claim ID、逐字引句、来源标题和 canonical URL。

gzip 文件使用确定性压缩（mtime=0），解压后字节哈希记录在 manifest 中。

## 兼容性说明

机器数据中的 `nuwa1-*`、`nuwa1804-*` 和 `nuwa-v1-*` 是首轮构建时形成的稳定内部 ID/schema 前缀。为避免破坏跨文件外键与审计哈希，本版保留这些前缀；公开产品与发布名称统一为 **AMind v1**。

## 解释边界

- 主题频次是覆盖信号，不是共识投票；
- 机构口径不自动等于个人观点；
- 研究问题不当作已得到的答案；
- 语义矛盾筛查不声称完备；
- 54 条代表证据做了完整段落语义复核，但不声称 52,225 条主张全部经过逐条人工语义复核；
- 本包不含 13GB 本地原始抓取与历史证据库；它保留发布所需的来源绑定段落、主张和哈希链。
