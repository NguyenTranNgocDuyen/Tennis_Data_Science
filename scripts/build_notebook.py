"""Create the member B notebook; calculations live in src, not duplicated here."""
from pathlib import Path
import nbformat as nbf

ROOT=Path(__file__).resolve().parents[1]


def build():
    nb=nbf.v4.new_notebook()
    cells=[]
    def md(s): cells.append(nbf.v4.new_markdown_cell(s.strip()))
    def code(s): cells.append(nbf.v4.new_code_cell(s.strip()))
    md('''# Phân tích khám phá tennis của thành viên B

Notebook bàn giao phần B trên dữ liệu thật giai đoạn 2015–2025. Phần A đã thu thập bản lưu trữ của dữ liệu Jeff Sackmann / Tennis Abstract, ghim commit và checksum. Notebook kiểm tra lại nguồn, chạy module tiền xử lý, rồi khám phá các bảng thống kê dùng chung với C.

Đọc `README.md` để cài môi trường và chạy pipeline trước. Chọn kernel **Python (Tennis A B)**. Không cần tải lại mạng khi dữ liệu raw đã có. Mỗi trận có một dòng winner/loser; ngày nguồn là ngày bắt đầu giải, không phải ngày thực tế của từng trận. Các hình trong notebook là EDA của B; module trực quan hóa và báo cáo tổng hợp vẫn thuộc phần C.''')
    code('''from pathlib import Path
import sys, json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
from IPython.display import display, Markdown

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p/'config/project.json').exists())
sys.path.insert(0, str(ROOT))
from src.data_collection import collect, load_raw
from src.data_validation import load_schema, validate_frame
from src.preprocessing import clean_matches, player_matches
from src.analysis import build_tables, verify_tables

CONFIG = json.loads((ROOT/'config/project.json').read_text())
SCHEMA = load_schema(ROOT/'data/schemas/tennis_schema.json')
plt.rcParams.update({'figure.dpi': 120, 'axes.spines.top': False, 'axes.spines.right': False})
pd.set_option('display.max_columns', 20)
print('Project:', ROOT)
print('Pinned source commit:', CONFIG['source_commit'])''')
    md('''## Kiểm tra phần A và làm sạch dữ liệu

Đọc raw dưới dạng chuỗi để phát hiện giá trị sai trước khi ép kiểu. Chế độ offline xác minh SHA256 của từng nguồn; không gọi tải dữ liệu mới. Bảng flow cho phép đối soát toàn bộ dòng bị loại hoặc giữ lại.''')
    code('''manifest = collect(ROOT, CONFIG, offline=True)
raw = load_raw(ROOT, CONFIG)
result = clean_matches(raw, SCHEMA, CONFIG)
m = result.matches
assert validate_frame(m, SCHEMA, allow_features=True).empty
assert m.match_id.is_unique
display(pd.DataFrame(result.flow.items(), columns=['metric', 'value']))
display(result.issues.groupby(['severity','field','rule']).size().reset_index(name='n_issues'))
print('Data-source license:', manifest['license'])''')
    md('''## Kiểm tra pipeline trên dữ liệu mẫu

Mẫu chỉ chứa dòng thật và hai bản sao có chủ đích. Mẫu có trường tùy chọn thiếu; không thay thế dữ liệu thật để viết kết luận. Giá trị sai nhân tạo được kiểm tra riêng bằng pytest.''')
    code('''sample = pd.read_csv(ROOT/'data/sample/tennis_sample.csv', dtype='string')
sample_result = clean_matches(sample, SCHEMA, CONFIG)
assert sample_result.flow['exact_duplicates_removed'] == 2
assert validate_frame(sample_result.matches, SCHEMA, allow_features=True).empty
display(pd.DataFrame(sample_result.flow.items(), columns=['metric','value']))''')
    md('''## Tái tạo bảng thống kê và đối chiếu số liệu bàn giao

Tái tính bảng bằng code trong src/analysis, kiểm tra mẫu số và so sánh với CSV đã xuất. Không chỉnh số thủ công trong notebook.''')
    code('''tables = build_tables(m, raw, SCHEMA)
verify_tables(m, tables)
for name, calculated in tables.items():
    saved = pd.read_csv(ROOT/f'reports/tables/{name}.csv')
    # Round-trip CSV can change nullable dtype, not the numeric values.
    from io import StringIO
    expected = pd.read_csv(StringIO(calculated.to_csv(index=False)))
    pd.testing.assert_frame_equal(saved, expected, check_exact=False, rtol=1e-12, atol=1e-12)
display(tables['season_summary'])
display(tables['score_status'])
print('Verified', len(tables), 'tables against exported CSVs')''')
    md('''## Cơ cấu và xu hướng số trận

Đếm theo mùa của tên file, không dùng năm tourney_date thay cho mùa. Mùa 2020 có số trận thấp hơn; số liệu này tự nó không giải thích nguyên nhân. Tỷ lệ mặt sân tính trên toàn bộ bản ghi trong phạm vi, gồm cả trận chưa hoàn tất.''')
    code('''season = tables['season_summary']
surface = tables['surface_summary']
fig, ax = plt.subplots(1, 2, figsize=(12, 4), layout='constrained')
ax[0].bar(season.season.astype(str), season.n_matches, color='#286c87')
ax[0].set(title='Retained matches by season', xlabel='Source season', ylabel='Matches')
ax[0].tick_params(axis='x', rotation=45)
ax[1].bar(surface.surface_group, surface.n_matches, color=['#bb7445','#608b47','#286c87'][:len(surface)])
ax[1].set(title='Surface distribution', xlabel='Surface', ylabel='Matches')
for i, row in surface.reset_index(drop=True).iterrows():
    ax[1].text(i, row.n_matches, f'{row.n_matches/len(m):.1%}', ha='center', va='bottom')
plt.show()''')
    md('''## Thiếu dữ liệu và giới hạn so sánh thời gian

Độ phủ thời lượng thay đổi rõ giữa các mùa. Mỗi median chỉ dựa vào số thời lượng có mặt. Các trường stats thiếu có thể có hệ thống theo giải, vì vậy không mặc định dữ liệu thiếu hoàn toàn ngẫu nhiên.''')
    code('''fields = ['minutes','winner_rank','loser_rank','w_svpt','l_svpt','winner_ht','loser_ht']
missing = tables['missingness_by_season']
heat = missing.loc[missing.field.isin(fields)].pivot(index='field',columns='season',values='missing_rate').reindex(fields)
fig, ax = plt.subplots(figsize=(11, 3.5), layout='constrained')
im = ax.imshow(heat.to_numpy(dtype=float), aspect='auto', vmin=0, vmax=1, cmap='YlOrRd')
ax.set_xticks(range(len(heat.columns)), heat.columns.astype(str))
ax.set_yticks(range(len(heat.index)), heat.index)
ax.set_title('Missing values after cleaning (share of retained matches)')
fig.colorbar(im, ax=ax, format=PercentFormatter(1))
plt.show()
coverage = season[['season','n_completed','n_duration']].copy()
coverage['duration_coverage'] = coverage.n_duration / coverage.n_completed
display(coverage)''')
    md('''## Phân phối thời lượng và kiểm tra độ nhạy

Chỉ dùng trận completed có thời lượng. Tách thể thức 3 và 5 set. Giữ các thời lượng cực đoan trong thống kê chính, xuất riêng cờ cần kiểm tra và so sánh với bảng độ nhạy. Hình histogram thứ nhất hiển thị toàn miền, để thấy cả các giá trị đáng ngờ.''')
    code('''completed = m.loc[m.is_completed]
fig, axes = plt.subplots(1, 2, figsize=(12, 4), layout='constrained')
for best_of, g in completed.groupby('best_of'):
    axes[0].hist(g.minutes.dropna().astype(float), bins=np.arange(0, 1201, 20), alpha=.6, label=f'Best of {best_of}')
axes[0].set(title='Completed match duration, all positive values', xlabel='Minutes', ylabel='Matches')
axes[0].legend()
duration = tables['duration_by_surface_format']
pivot = duration.pivot(index='surface_group', columns='best_of', values='median_minutes')
pivot.plot.bar(ax=axes[1], color=['#286c87','#c48842'], rot=0)
axes[1].set(title='Median duration by surface and format', xlabel='Surface', ylabel='Minutes')
axes[1].legend(title='Best of')
plt.show()
display(duration)
display(tables['duration_sensitivity'])
display(tables['duration_review'].loc[tables['duration_review'].score_status.eq('completed')])''')
    md('''## Thứ hạng và tỷ lệ thắng

Upset = người thắng có số rank lớn hơn người thua. Chỉ dùng completed và hai rank khác nhau có mặt. Tỷ lệ thắng theo nhóm rank dùng cả hai phía người chơi. Cùng một người xuất hiện nhiều lần; số liệu không độc lập để dùng kiểm định nhị thức thông thường.''')
    code('''upsets = tables['upsets_by_surface_format']
rank = tables['rank_group_performance'].set_index('rank_group').reindex(['Top 10','11–50','51–100','101+','Unknown']).dropna(how='all')
fig, axes = plt.subplots(1, 2, figsize=(12, 4), layout='constrained')
upsets.pivot(index='surface_group',columns='best_of',values='upset_rate').plot.bar(ax=axes[0], rot=0)
axes[0].set(title='Upset share among ranked completed matches', xlabel='Surface', ylabel='Upset share')
axes[0].legend(title='Best of')
axes[0].yaxis.set_major_formatter(PercentFormatter(1))
axes[0].set_ylim(0, .6)
axes[1].bar(rank.index, rank.win_rate, color='#286c87')
axes[1].set(title='Win rate by pre-event rank group', xlabel='Rank group', ylabel='Win rate', ylim=(0,1))
axes[1].yaxis.set_major_formatter(PercentFormatter(1))
plt.show()
display(upsets[['surface_group','best_of','n_ranked_completed','n_upsets','upset_rate']])
display(rank)''')
    md('''## Giao bóng theo mặt sân

Sử dụng tỷ lệ gộp theo số điểm: tổng ace / tổng điểm giao bóng trên cùng tập lượt có đủ tử và mẫu. Không lấy mean của các tỷ lệ từng trận và không điền stats thiếu. Sự khác biệt chưa điều chỉnh người chơi, thể thức, giải và mùa.''')
    code('''serve = tables['serve_by_surface']
ace = serve.loc[serve.metric.eq('ace_rate')]
fig, ax = plt.subplots(figsize=(7, 4), layout='constrained')
ax.bar(ace.surface_group, ace.rate, color=['#bb7445','#608b47','#286c87'][:len(ace)])
ax.yaxis.set_major_formatter(PercentFormatter(1))
ax.set(title='Pooled ace rate on observed service points', xlabel='Surface', ylabel='Aces / service points')
for i, (_, row) in enumerate(ace.iterrows()):
    ax.text(i, row.rate, f'{row.rate:.2%}', ha='center', va='bottom')
ax.set_ylim(0, float(ace.rate.max())*1.2)
plt.show()
display(serve)
display(tables['numeric_summary'])''')
    md('''## Kết luận và bàn giao

Các kết luận định lượng đầy đủ, mẫu số, bảng độ nhạy và hạn chế nằm trong `reports/eda_findings.md`. C nhận 14 bảng CSV và table_contract.json. Dữ liệu đã xử lý nằm ở data/processed. Mã nguồn và kiểm thử là phần chính; notebook dùng lại các module để tránh hai cách tính khác nhau.

Không suy diễn nhân quả từ khác biệt mặt sân. Không dùng winner/loser hoặc stats hậu trận làm đặc trưng dự đoán trước trận. Chưa có mô hình dự đoán trong phần A B.''')
    code('''ranked = m.loc[m.is_completed & m.rank_pair_available]
print(f"Retained matches: {len(m):,}; completed: {int(m.is_completed.sum()):,}")
print(f"Upsets: {int(ranked.is_upset.sum()):,}/{len(ranked):,} = {ranked.is_upset.mean():.2%}")
print(f"Player appearances (completed): {int(tables['rank_group_performance'].n_appearances.sum()):,}")
assert int(tables['rank_group_performance'].n_appearances.sum()) == 2*int(m.is_completed.sum())
print('All notebook accounting checks passed.')''')
    nb['cells']=cells
    nb['metadata']={'kernelspec':{'display_name':'Python (Tennis A B)','language':'python','name':'tennis-khdl'},'language_info':{'name':'python','version':'3.13'}}
    nbf.write(nb,ROOT/'notebooks/member_b_eda.ipynb')

if __name__=='__main__': build()
