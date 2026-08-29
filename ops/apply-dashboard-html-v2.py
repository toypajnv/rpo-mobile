from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding='utf-8')
    if old not in text:
        raise RuntimeError(f'Marker not found in {path}: {old[:120]!r}')
    target.write_text(text.replace(old, new, 1), encoding='utf-8')

path='server/app/templates/dashboard.html'
replace_once(path, '/static/app.css?v=20260821-1', '/static/app.css?v=20260829-2')
replace_once(path, '''</header>
{% if request.query_params.get('export') == 'ok' %}''', '''</header>
<div class="global-filter" id="global-filter" hidden>
  <label class="search-field">⌕ <input id="global-search" type="search" placeholder="НД, ФИО, этап, значение или комментарий"></label>
  <label class="unit-filter">Подразделение<select id="global-unit"><option value="">Все подразделения</option>{% for unit in structural_units %}<option value="{{ unit }}">{{ unit }}</option>{% endfor %}</select></label>
  <button type="button" class="filter-reset" id="global-filter-reset">Сбросить</button>
</div>
{% if request.query_params.get('export') == 'ok' %}''')
replace_once(path, '''   <article><span class="round orange">!</span><div><small>Не выгружено</small><strong>{{ pending }}</strong><em>нарядов-допусков</em></div></article>
   <article><span class="round green">♟</span>''', '''   <article><span class="round orange">!</span><div><small>Не выгружено</small><strong>{{ pending }}</strong><em>нарядов-допусков</em></div></article>
   <article><span class="round orange">✓</span><div><small>Ожидают разрешения</small><strong>{{ pending_approvals }}</strong><em>этапов работ</em></div></article>
   <article><span class="round green">♟</span>''')

old_trans = '''    <div class="table-wrap tall"><table><thead><tr><th>Получено</th><th>Работник</th><th>НД</th><th>Этап</th><th>Переданное значение</th><th>Комментарий</th><th>Выгрузка</th></tr></thead><tbody id="transmissions-body">
      {% for e in transmissions %}<tr><td>{{ e.received_at.astimezone().strftime('%d.%m.%Y %H:%M:%S') }}</td><td><b>{{ e.worker_name }}</b></td><td><b>{{ e.permit_number }}</b></td><td><span class="stage-code">{{ e.field_key }}</span> {{ e.stage_label }}</td><td>{{ e.field_value }}</td><td class="wrap-cell">{{ e.comment or '—' }}</td><td>{% if e.exported_at %}<span class="badge done">Выгружено</span>{% else %}<span class="badge pending">Ожидает</span>{% endif %}</td></tr>{% endfor %}
    </tbody></table></div>'''
new_trans = '''    <div class="table-wrap tall"><table><thead><tr><th>Получено</th><th>Подразделение</th><th>Работник</th><th>НД</th><th>Этап</th><th>Переданное значение</th><th>Комментарий</th><th>Разрешение</th><th>Действие</th></tr></thead><tbody id="transmissions-body">
      {% for e in transmissions %}<tr><td>{{ e.received_at.astimezone().strftime('%d.%m.%Y %H:%M:%S') }}</td><td><span class="unit-pill">{{ e.structural_unit or '—' }}</span></td><td><b>{{ e.worker_name }}</b></td><td><b>{{ e.permit_number }}</b></td><td><span class="stage-code">{{ e.field_key }}</span> {{ e.stage_label }}</td><td>{{ e.field_value }}</td><td class="wrap-cell">{{ e.comment or '—' }}</td><td>{% if not e.approval_required %}<span class="badge neutral">Не требуется</span>{% elif e.approval_status == 'approved' %}<span class="badge done">Разрешено</span>{% else %}<span class="badge approval-wait">Ожидает</span>{% endif %}</td><td>{% if e.approval_required and e.approval_status != 'approved' %}<button type="button" class="approve-button" data-approve-event="{{ e.id }}">Разрешить</button>{% else %}—{% endif %}</td></tr>{% endfor %}
    </tbody></table></div>'''
replace_once(path, old_trans, new_trans)

replace_once(path, '''    <div class="table-wrap tall"><table><thead><tr><th>Обновлено</th><th>НД</th><th>Работник</th><th>Текущее состояние</th><th>Прогресс</th><th>Этапы</th><th>Выгрузка</th><th>Действия</th></tr></thead><tbody id="works-body" data-can-delete="{{ 'true' if is_admin else 'false' }}">''', '''    <div class="table-wrap tall"><table><thead><tr><th>Обновлено</th><th>Подразделение</th><th>НД</th><th>Работник</th><th>Текущее состояние</th><th>Разрешение</th><th>Прогресс</th><th>Этапы</th><th>Выгрузка</th><th>Действия</th></tr></thead><tbody id="works-body" data-can-delete="{{ 'true' if is_admin else 'false' }}">''')
replace_once(path, '''{% for e in works %}<tr><td>{{ e.updated_at.astimezone().strftime('%d.%m.%Y %H:%M:%S') }}</td><td><b>{{ e.permit_number }}</b></td><td><b>{{ e.worker_name }}</b></td><td><span class="work-state {{ e.status_class }}">{{ e.status }}</span></td><td><div class="progress">''', '''{% for e in works %}<tr><td>{{ e.updated_at.astimezone().strftime('%d.%m.%Y %H:%M:%S') }}</td><td><span class="unit-pill">{{ e.structural_unit or '—' }}</span></td><td><b>{{ e.permit_number }}</b></td><td><b>{{ e.worker_name }}</b></td><td><span class="work-state {{ e.status_class }}">{{ e.status }}</span></td><td><span class="badge {% if e.approval.status == 'approved' %}done{% elif e.approval.status == 'pending' %}approval-wait{% else %}neutral{% endif %}">{{ e.approval.label }}</span></td><td><div class="progress">''')

for old,new in [
('<article><small>Всего НД</small><strong>{{ analytics.total }}</strong>','<article><small>Всего НД</small><strong id="analytics-total">{{ analytics.total }}</strong>'),
('<article><small>Сейчас в работе</small><strong>{{ analytics.active }}</strong>','<article><small>Сейчас в работе</small><strong id="analytics-active">{{ analytics.active }}</strong>'),
('<article><small>Остановлено</small><strong>{{ analytics.stopped }}</strong>','<article><small>Остановлено</small><strong id="analytics-stopped">{{ analytics.stopped }}</strong>'),
('<article><small>Завершено</small><strong>{{ analytics.completed }}</strong>','<article><small>Завершено</small><strong id="analytics-completed">{{ analytics.completed }}</strong>'),
('<article><small>Продлений</small><strong>{{ analytics.extended }}</strong>','<article><small>Продлений</small><strong id="analytics-extended">{{ analytics.extended }}</strong>'),
('<article><small>Среднее время работ</small><strong>{{ analytics.avg_completion_label }}</strong>','<article><small>Среднее время работ</small><strong id="analytics-average">{{ analytics.avg_completion_label }}</strong>'),
('<div class="bar-chart">{% for p in analytics.activity_days %}','<div class="bar-chart" id="analytics-activity">{% for p in analytics.activity_days %}'),
('<div class="bar-chart stage-chart">{% for p in analytics.stage_progress %}','<div class="bar-chart stage-chart" id="analytics-stages">{% for p in analytics.stage_progress %}'),
('<div class="leader-list">{% for p in analytics.top_workers %}','<div class="leader-list" id="analytics-workers">{% for p in analytics.top_workers %}'),
('/static/dashboard.js?v=20260821-1','/static/dashboard.js?v=20260829-2'),
]:
    replace_once(path, old, new)
print('dashboard html v2 applied')
