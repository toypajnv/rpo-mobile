from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'server/app/static/app.css'
text = path.read_text(encoding='utf-8')
marker = '/* RPO 2.0 — approvals, structural units, global operational search */'
if marker not in text:
    text += r'''

/* RPO 2.0 — approvals, structural units, global operational search */
.global-filter{display:flex;gap:10px;align-items:end;background:#fff;border:1px solid #e2e9f3;border-radius:14px;padding:10px 12px;margin:0 0 14px;box-shadow:0 3px 16px rgba(16,45,80,.05)}
.global-filter[hidden]{display:none!important}.search-field{display:flex;align-items:center;gap:8px;flex:1;min-width:240px;border:1px solid #ccd7e7;border-radius:10px;padding:0 11px;height:42px;color:#738198}.search-field input{border:0;outline:0;width:100%;font:inherit;background:transparent}.unit-filter{display:flex;flex-direction:column;gap:3px;font-size:11px;color:#657188}.unit-filter select{height:42px;min-width:180px;border:1px solid #ccd7e7;border-radius:10px;background:#fff;padding:0 10px}.filter-reset{height:42px;border:1px solid #ccd7e7;border-radius:10px;background:#f7f9fc;padding:0 14px;cursor:pointer}.unit-pill{display:inline-flex;align-items:center;padding:4px 8px;border-radius:999px;background:#edf3fb;color:#24527f;font-size:11px;font-weight:700;white-space:nowrap}.badge.approval-wait{background:#fff0d6;color:#9a5a00}.badge.neutral{background:#eef1f5;color:#667386}.approve-button{border:0;border-radius:8px;background:#168347;color:#fff;font-weight:700;padding:8px 11px;cursor:pointer;white-space:nowrap}.approve-button:hover{filter:brightness(.95)}.approve-button:disabled{opacity:.6;cursor:wait}.approve-button.small{padding:5px 8px;font-size:11px}.stage-approval{display:flex;gap:6px;align-items:center;flex-wrap:wrap}.approval-count{display:block;color:#9a5a00;margin-top:4px;font-size:10px}.stats{grid-template-columns:repeat(auto-fit,minmax(190px,1fr))}
@media(max-width:900px){.global-filter{align-items:stretch;flex-direction:column}.search-field,.unit-filter select{width:100%;min-width:0}.filter-reset{width:100%}}
'''
    path.write_text(text, encoding='utf-8')
print('css v2 applied')
