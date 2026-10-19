import difflib, hashlib, json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
freeze=json.loads((HERE/'freeze.json').read_text())
checks=[]
for name,files in freeze['skill_snapshots'].items():
    base=ROOT/json.loads((HERE/'protocol.json').read_text())['variants'][name]
    changed=[p for p,h in files.items() if not (base/p).is_file() or sha(base/p)!=h]
    checks.append({'variant':name,'frozen_files':len(files),'changed_files':changed})
fixture_changed=[p for p,h in freeze['files'].items() if sha(HERE/p)!=h]
assert not fixture_changed
assert all(not c['changed_files'] for c in checks)
assert sha(HERE/'protocol.json')==freeze['protocol_sha256']
assert sha(HERE/'run_challenges.py')==freeze['harness_sha256']
results={name:json.loads((HERE/(name+'-results.json')).read_text()) for name in ('old','frozen_new','repaired_new')}
rows=[]
for i,ch in enumerate(json.loads((HERE/'protocol.json').read_text())['challenges']):
    rows.append({**ch,**{n:results[n]['results'][i]['outcome'] for n in results}})
summary={'protocol_sha256':sha(HERE/'protocol.json'),'freeze_sha256':sha(HERE/'freeze.json'),'snapshots':checks,'inputs_changed':fixture_changed,'harness_unchanged':True,'counts':{},'paired':rows,'repairs':[{'id':'E19','bug':'Report silently treated open started attempts as zero known total spend and omitted their count.','current_files':['skills/eval-improve/scripts/report_eval.py','skills/eval-improve/references/artifacts.md'],'new_tests':['test_all_interrupted_attempts_do_not_look_free','test_interrupted_attempt_remains_unknown_and_counted_with_finished_cost']},{'id':'E20','bug':'Report accepted foreign per-result treatment binding after result-byte hash was updated, even when runner marked result identity required.','current_files':['skills/eval-improve/scripts/report_eval.py','skills/eval-improve/references/artifacts.md'],'new_tests':['test_report_rejects_foreign_result_binding_even_with_updated_byte_hash']}],'limits':['All fixtures are synthetic local applications and offline pricing/calibration; no actual target model ability or live provider prices measured.','Independent challenge count is 22 curated contracts, not independent production traffic; no statistical population improvement claim.','All current repairs and added regression variants are validation after observed failures, not untouched holdout.','Old missing extensions remain unsupported rather than whole-skill quality failures.','Stage coverage challenge checks a predeclared cardinality, not independent proof of every member identity.','Process runner does not enforce filesystem/network/credential isolation; hashes are not adversarial authentication.']}
for name,data in results.items():
    supported=[r for r in data['results'] if r['outcome']!='unsupported']
    shared=[r for r in data['results'] if r['classification']!='extension']
    controls=[r for r in data['results'] if r['classification']=='control']
    extensions=[r for r in data['results'] if r['classification']=='extension']
    summary['counts'][name]={'all_pass':data['pass'],'all_total':len(data['results']),'supported_pass':sum(r['outcome']=='pass' for r in supported),'supported_total':len(supported),'shared_pass':sum(r['outcome']=='pass' for r in shared),'shared_total':len(shared),'control_pass':sum(r['outcome']=='pass' for r in controls),'control_total':len(controls),'extension_pass':sum(r['outcome']=='pass' for r in extensions),'extension_total':len(extensions),'unsupported':data['unsupported']}
(HERE/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
patch=[]
for relative in ('scripts/report_eval.py','references/artifacts.md'):
    old=ROOT/'.codex-tmp/contrast-2026-10-18/new/skills/eval-improve'/relative
    new=ROOT/'skills/eval-improve'/relative
    patch.extend(difflib.unified_diff(old.read_text().splitlines(True),new.read_text().splitlines(True),fromfile='frozen_new/skills/eval-improve/'+relative,tofile='repaired_new/skills/eval-improve/'+relative))
(HERE/'repair.diff').write_text(''.join(patch))
validation={'command':'python3 -m unittest scripts.test_amind_capability_kernel.KernelTests scripts.test_amind_capability_kernel.BillingCalibrationTests scripts.test_amind_app_skills scripts.test_amind_eval_reporting -v','returncode':0,'tests':83,'elapsed_seconds':12.010,'observed_summary':'Ran 83 tests in 12.010s; OK','new_regression_file':'scripts/test_amind_eval_reporting.py','new_regression_count':4,'evidence':'Observed stdout/stderr from terminal session41900 in this task, recorded without rerunning.','source_hashes':{str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'skills/eval-improve/scripts/report_eval.py',ROOT/'skills/eval-improve/references/artifacts.md',ROOT/'scripts/test_amind_eval_reporting.py')}}
(HERE/'validation-checks.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n')
text=['# AMind Eval 实际行为对比（2026-10-18）','', '预登记22个离线行为挑战，以公共 CLI 对等入口实际执行。冻结旧版0.3.0与冻结新版0.4.0均未改；修复版单列为 validation。没有调用模型、网络或子agent。', '', '| 测量 | 旧版 | 冻结新版 | 修复新版（validation） |','|---|---:|---:|---:|']
for title,pa,to in [('共享合同','shared_pass','shared_total'),('旧已有controls','control_pass','control_total'),('新扩展','extension_pass','extension_total')]:
    cells=[]
    for name,c in summary['counts'].items():
        cells.append(f"{c[pa]}/{c[to]}" if title!='新扩展' or name!='old' else f"{c['unsupported']} unsupported")
    text.append('| '+title+' | '+' | '.join(cells)+' |')
text+=['','不能把旧版未提供的10项扩展当成整体质量失败。共享合同旧6/12、冻结新11/12；6个控制三组均6/6，显示没有靠改变既有正确答案制造增益。冻结新共20/22；修复后22/22仅表示这些观察过的挑战通过。','', '## 成对明细','','| ID | 契约 | 类型 | 旧 | 冻结新 | 修复新 |','|---|---|---|---|---|---|']
for r in rows:text.append('| '+' | '.join([r['id'],r['name'],r['classification'],r['old'],r['frozen_new'],r['repaired_new']])+' |')
text+=['','## 真实缺陷与最小修复','','E19：report 只读取 finished 费用。存在 started、无 finished/result 的中断记录时，冻结旧/新均输出 total_cost_usd=0、unknown_cost_attempts=0、attempts=null。修复后输出 total=null、unknown=1、attempts=1，并保留中断明细。已完成调用的已知费用仍保留为 subtotal。','', 'E20：新 runner 的逐行 result_identity 已能防止 compare 中的产物移植，但 report 未校验这个绑定。把结果 treatment_hash 改为 foreign，并更新字节hash，冻结新 report 仍显示 hashes match export。修复后 integrity 为 unverified: result identity differs...。旧没有逐行绑定，记录为扩展 unsupported。', '', '仅改当前 Eval reporter 与对应 artifact 文档；新增4个公共 CLI 回归。83项已有/新增 Eval 测试全部通过，记录在 validation-checks.json；修复 diff 在 repair.diff。冻结副本和58输入文件/hash复核无变化。', '', '## 未提升和边界','', '6个原有正确控制没有提升：子集不重复计量、unknown/partial保留、混淆矩阵、真实adapter成对运行、served model校验、未reconcile恢复阻断均旧有正确。中断费用和报告产物绑定是这次挑战发现的新缺陷；不能将修复后的成绩追记为冻结新版成绩。', '', '这些结果不证明模型能力、生产定价、总体泛化或盲测效果。stage人口挑战核对预登记总数；它不能证明每个worker成员真实存在。Runner没有提供文件系统/网络/凭据隔离。价格为合成夹具，没有真实provider账单。', '', '## 证据','','- protocol.json：执行前挑战、评分和controls；sha256 '+summary['protocol_sha256'], '- freeze.json：协议、58输入、harness与新旧技能文件hash；sha256 '+summary['freeze_sha256'], '- old-results.json / frozen_new-results.json / repaired_new-results.json：三组独立观测。', '- runs/<variant>/<challenge>/evidence/*.command.json：每次公共CLI完整argv、exit、stdout/stderr。', '- runs/<variant>/<challenge>/flow：runner原始manifests、attempts、results、errors、trace与工作区。', '- agent-prompts.json：给root统一隔离执行的2项agent任务与可确定rubric；本子任务未调用它们。', '- summary.json：成对矩阵、分母与边界；repair.diff / validation-checks.json：修复与回归。','']
(HERE/'report.zh-CN.md').write_text('\n'.join(text))
print(json.dumps(summary['counts'],ensure_ascii=False,indent=2))
