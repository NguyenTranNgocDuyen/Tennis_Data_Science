"""Build the versioned CSV contract (JSON Schema plus lexical CSV rules)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = {"tourney_id", "tourney_name", "tourney_level", "tourney_date", "match_num", "winner_id", "winner_name", "loser_id", "loser_name", "best_of", "round", "source_season", "source_file", "source_row"}
DESCRIPTIONS = {
    "tourney_id": "Mã giải có tiền tố mùa giải; không suy luận cấu trúc phần còn lại.",
    "tourney_name": "Tên giải theo nguồn.", "surface": "Mặt sân; trống là chưa biết.",
    "draw_size": "Quy mô nhánh đấu, có thể làm tròn lên lũy thừa 2.",
    "tourney_level": "G Grand Slam; M Masters; A tour khác; F cuối mùa; D Davis Cup; mã khác giữ trong raw.",
    "tourney_date": "YYYYMMDD ngày bắt đầu/tuần giải; KHÔNG phải ngày thực tế từng trận.",
    "match_num": "Mã trận trong giải; KHÔNG đảm bảo thứ tự thời gian.",
    "score": "Tỷ số nguyên văn; RET bỏ cuộc; W/O không thi đấu; DEF truất quyền.",
    "best_of": "Thể thức tối đa 3 hoặc 5 set.", "round": "Vòng đấu theo mã nguồn.",
    "minutes": "Thời lượng phút; thiếu không được thay bằng 0.",
    "source_season": "Mùa theo tên file, có thể khác năm của tourney_date.",
    "source_file": "Tên CSV gốc dùng truy vết.", "source_row": "Số dòng CSV gốc tính cả header là dòng 1."
}
for role in ("winner", "loser"):
    who = "người thắng" if role == "winner" else "người thua"
    for suffix, desc in {"id":"Mã người chơi ổn định, dùng để join", "seed":"Hạt giống (chuỗi, có thể không chỉ là số)", "entry":"Diện vào giải Q WC LL PR...", "name":"Tên", "hand":"Tay giao bóng R L U", "ht":"Chiều cao cm", "ioc":"Mã quốc gia IOC", "age":"Tuổi ở ngày giải", "rank":"Thứ hạng ATP trước hoặc tại ngày giải; số nhỏ là hạng cao", "rank_points":"Điểm xếp hạng"}.items():
        DESCRIPTIONS[f"{role}_{suffix}"] = f"{desc} của {who}."
for prefix, who in (("w","người thắng"),("l","người thua")):
    for stat, desc in {"ace":"Số ace", "df":"Số lỗi kép", "svpt":"Số điểm giao bóng", "1stIn":"Số giao bóng một vào sân", "1stWon":"Số điểm thắng khi giao bóng một", "2ndWon":"Số điểm thắng khi giao bóng hai", "SvGms":"Số game giao bóng", "bpSaved":"Số break point cứu được", "bpFaced":"Số break point đối mặt"}.items():
        DESCRIPTIONS[f"{prefix}_{stat}"] = f"{desc} của {who}."


def build():
    import csv
    with (ROOT / 'data/raw/atp_matches_2025.csv').open() as f:
        columns = next(csv.reader(f)) + ["source_season", "source_file", "source_row"]
    props = {}
    for col in columns:
        rule = {"dtype":"string", "core":col in CORE}
        if col in {"draw_size", "match_num", "winner_id", "loser_id", "best_of", "minutes", "winner_ht", "loser_ht", "winner_rank", "loser_rank", "winner_rank_points", "loser_rank_points", "source_season", "source_row"} or col.startswith(("w_", "l_")):
            rule.update(dtype="integer", minimum=0)
        if col in {"winner_age", "loser_age"}:
            rule.update(dtype="number", minimum=10, maximum=80)
        if col in {"winner_rank", "loser_rank", "winner_id", "loser_id", "minutes", "draw_size", "source_row"}:
            rule["minimum"] = 1
        if col in {"winner_ht", "loser_ht"}:
            rule.update(minimum=120, maximum=250)
        if col == "source_season":
            rule.update(minimum=1968, maximum=2100)
        if col == "tourney_date":
            rule["dtype"] = "date8"
        enums = {"surface":["Hard", "Clay", "Grass", "Carpet"], "best_of":["3", "5"],
                 "winner_hand":["R", "L", "U"], "loser_hand":["R", "L", "U"]}
        if col in enums:
            rule["enum"] = enums[col]
        props[col] = {"type":["string","null"], "description":DESCRIPTIONS[col], "x-csv":rule}
    schema = {"$schema":"https://json-schema.org/draft/2020-12/schema", "$id":"urn:tennis:input:1.0.0",
              "title":"Tennis CSV input contract 1.0.0", "description":"One raw match per row. CSV lexical strings/null; x-csv defines parsed semantic checks. All columns required, optional VALUES nullable. Dataset-level duplicate policy is in docs/data_contract.md.",
              "type":"object", "required":columns, "additionalProperties":False, "properties":props}
    path = ROOT / "data/schemas/tennis_schema.json"
    path.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n")

if __name__ == "__main__":
    build()
