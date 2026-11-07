"""Cơ sở tri thức chăm sóc diên vĩ: triệu chứng, bệnh, chẩn đoán và trả lời dự phòng.
Không phụ thuộc FastAPI hay sklearn. Chỉ là gợi ý tham khảo, không thay thế chuyên gia."""
import re
import unicodedata

SYMPTOM_GROUPS = [
    ("Lá", [
        ("leaf_spots", "Đốm nâu hoặc xám trên lá, có viền vàng"),
        ("leaf_tips_brown", "Đầu lá khô nâu"),
        ("yellow_leaves", "Lá vàng"),
        ("wilting", "Lá héo, rũ, gục"),
        ("water_soaked", "Vệt úng nước (xanh sẫm, nhớt) trên lá"),
        ("holes_in_leaves", "Lá có đường đục hoặc lỗ"),
        ("orange_pustules", "Mụn bột màu cam, nâu gỉ sắt"),
        ("mosaic", "Lá có vệt vàng nhạt dạng khảm"),
    ]),
    ("Củ và rễ", [
        ("soft_rhizome", "Củ (thân rễ) mềm nhũn, có mùi hôi"),
        ("stunted", "Cây còi cọc, lớn chậm"),
    ]),
    ("Hoa", [
        ("no_blooms", "Cây khỏe nhưng không ra hoa"),
        ("distorted_buds", "Nụ biến dạng, không nở, có vệt bạc"),
        ("gray_mold", "Mốc xám trên hoa hoặc nụ"),
    ]),
    ("Sâu bọ", [
        ("sticky_insects", "Rệp nhỏ, chất dính trên lá"),
    ]),
]
SYMPTOMS = {sid: label for _, items in SYMPTOM_GROUPS for sid, label in items}

# signs: triệu chứng -> trọng số (1 đến 3)
DISEASES = [
    {
        "id": "leaf_spot", "name": "Bệnh đốm lá do nấm", "severity": "Trung bình",
        "cause": "Nấm lây qua nước bắn và tàn dư lá cũ, nặng hơn khi ẩm và ít thông thoáng.",
        "signs": {"leaf_spots": 3, "yellow_leaves": 1, "leaf_tips_brown": 1},
        "treat": ["Cắt bỏ lá có đốm, bỏ vào túi rác, không ủ phân.",
                  "Tưới vào gốc, tránh làm ướt lá, tưới vào buổi sáng.",
                  "Nếu lan rộng, phun thuốc trừ nấm gốc đồng hoặc mancozeb theo đúng nhãn."],
        "prevent": ["Tỉa thưa, giữ khoảng cách để gió lùa.", "Dọn sạch lá rụng vào cuối mùa."],
    },
    {
        "id": "soft_rot", "name": "Thối mềm thân rễ", "severity": "Cao",
        "cause": "Vi khuẩn xâm nhập qua vết thương hoặc vết sâu đục, nặng khi đất úng.",
        "signs": {"soft_rhizome": 3, "wilting": 2, "yellow_leaves": 1, "water_soaked": 2},
        "treat": ["Đào củ lên, cắt bỏ toàn bộ phần mềm nhũn đến chỗ thịt củ còn trắng và cứng.",
                  "Dụng cụ cắt cần lau cồn hoặc nước tẩy loãng sau mỗi lần cắt.",
                  "Phơi củ nơi nắng và khô vài giờ, trồng lại vào đất thoát nước tốt.",
                  "Củ thối hoàn toàn thì bỏ đi, không trồng lại chỗ cũ."],
        "prevent": ["Không trồng sâu, để lộ nửa trên của củ.", "Đảm bảo thoát nước, không tưới quá nhiều."],
    },
    {
        "id": "borer", "name": "Sâu đục lá và củ", "severity": "Cao",
        "cause": "Sâu non đục vào lá rồi xuống củ, tạo vết thương cho vi khuẩn gây thối.",
        "signs": {"holes_in_leaves": 3, "water_soaked": 2, "soft_rhizome": 1, "wilting": 1},
        "treat": ["Bóp nhẹ dọc lá có vết đục để diệt sâu non, hoặc cắt bỏ lá đó.",
                  "Kiểm tra củ, loại bỏ phần bị đục và xử lý như bệnh thối mềm nếu có.",
                  "Dọn sạch tàn dư lá cũ vì trứng qua đông ở đó."],
        "prevent": ["Dọn lá khô vào cuối thu.", "Kiểm tra lá non mỗi tuần vào đầu mùa xuân."],
    },
    {
        "id": "rust", "name": "Bệnh gỉ sắt", "severity": "Thấp đến trung bình",
        "cause": "Nấm gỉ sắt phát triển khi lá ẩm lâu, thường vào thời tiết mát ẩm.",
        "signs": {"orange_pustules": 3, "yellow_leaves": 1, "leaf_spots": 1},
        "treat": ["Cắt bỏ lá nhiễm nặng và tiêu hủy.",
                  "Giữ lá khô, tưới vào gốc.",
                  "Phun thuốc trừ nấm theo nhãn nếu bệnh tái phát nhiều lần."],
        "prevent": ["Tăng độ thông thoáng.", "Không bón thừa đạm."],
    },
    {
        "id": "botrytis", "name": "Thối xám (nấm Botrytis)", "severity": "Trung bình",
        "cause": "Nấm phát triển trên hoa tàn và mô yếu khi trời ẩm, lạnh, ít nắng.",
        "signs": {"gray_mold": 3, "distorted_buds": 1, "leaf_spots": 1},
        "treat": ["Ngắt hoa tàn và phần có mốc ngay, không để rơi xuống gốc.",
                  "Giảm ẩm, tưới ít hơn, tăng thông thoáng.",
                  "Phun thuốc trừ nấm theo nhãn khi mùa ẩm kéo dài."],
        "prevent": ["Ngắt hoa tàn thường xuyên.", "Tránh trồng quá dày."],
    },
    {
        "id": "thrips", "name": "Bọ trĩ", "severity": "Thấp đến trung bình",
        "cause": "Côn trùng rất nhỏ hút nhựa nụ và lá non, làm nụ méo, hoa có vệt bạc.",
        "signs": {"distorted_buds": 3, "no_blooms": 1, "leaf_tips_brown": 1},
        "treat": ["Cắt bỏ nụ hỏng nặng.",
                  "Xịt nước mạnh hoặc phun xà phòng côn trùng, dầu neem theo nhãn.",
                  "Lặp lại sau 5 đến 7 ngày vì bọ trĩ sinh sản nhanh."],
        "prevent": ["Kiểm tra nụ non thường xuyên.", "Dọn cỏ dại quanh gốc."],
    },
    {
        "id": "aphids", "name": "Rệp và nguy cơ truyền virus", "severity": "Trung bình",
        "cause": "Rệp hút nhựa, tiết chất dính và có thể truyền virus giữa các cây.",
        "signs": {"sticky_insects": 3, "stunted": 1, "yellow_leaves": 1, "mosaic": 1},
        "treat": ["Xịt nước mạnh để rửa trôi rệp.",
                  "Phun xà phòng côn trùng hoặc dầu neem theo nhãn, nhắc lại sau một tuần.",
                  "Cách ly cây nếu có vệt khảm vì có thể đã nhiễm virus."],
        "prevent": ["Khuyến khích thiên địch như bọ rùa.", "Hạn chế bón thừa đạm tạo lá non mềm."],
    },
    {
        "id": "mosaic", "name": "Virus khảm", "severity": "Cao",
        "cause": "Virus lây qua rệp và dụng cụ cắt, không có thuốc chữa.",
        "signs": {"mosaic": 3, "stunted": 2, "yellow_leaves": 1},
        "treat": ["Cách ly cây, khử trùng dụng cụ sau khi dùng.",
                  "Cây nhiễm nặng nên nhổ bỏ và tiêu hủy để tránh lây sang cây khác.",
                  "Diệt rệp để chặn đường lây."],
        "prevent": ["Dùng dụng cụ sạch.", "Mua giống từ nguồn đáng tin."],
    },
    {
        "id": "overwater", "name": "Tưới quá nhiều hoặc đất úng", "severity": "Trung bình",
        "cause": "Rễ thiếu oxy, lá vàng và héo dù đất vẫn ướt. Thường dẫn tới thối củ nếu kéo dài.",
        "signs": {"yellow_leaves": 2, "wilting": 2, "soft_rhizome": 1, "stunted": 1},
        "treat": ["Ngưng tưới cho tới khi lớp đất mặt khô.",
                  "Kiểm tra củ, nếu mềm thì xử lý như bệnh thối mềm.",
                  "Cải tạo đất thoát nước, trồng chậu có lỗ thoát."],
        "prevent": ["Chỉ tưới khi lớp đất mặt khô.", "Trồng ở nền cao hoặc đất tơi xốp."],
    },
    {
        "id": "scorch", "name": "Cháy đầu lá (khô hạn hoặc thừa phân)", "severity": "Thấp",
        "cause": "Thường do thiếu nước, nắng gắt, hoặc muối từ phân bón tích tụ.",
        "signs": {"leaf_tips_brown": 3, "yellow_leaves": 1, "stunted": 1},
        "treat": ["Cắt phần khô, tưới đẫm đều khi đất khô sâu.",
                  "Xả nước nhiều để rửa muối nếu mới bón phân.",
                  "Giảm lượng phân, nhất là phân đạm."],
        "prevent": ["Tưới đều đặn.", "Bón phân ít và chia nhỏ lần."],
    },
    {
        "id": "no_bloom", "name": "Cây không ra hoa do điều kiện trồng", "severity": "Thấp",
        "cause": "Thiếu nắng (cần ít nhất 6 giờ), trồng quá sâu, bón thừa đạm hoặc củ quá dày cần chia.",
        "signs": {"no_blooms": 3, "stunted": 1},
        "treat": ["Chuyển sang chỗ có nắng trực tiếp ít nhất 6 giờ mỗi ngày.",
                  "Kiểm tra để phần trên của củ lộ ra mặt đất.",
                  "Chia củ sau 3 đến 4 năm, đổi sang phân nhiều lân và kali, ít đạm."],
        "prevent": ["Chia củ định kỳ.", "Chọn vị trí nhiều nắng."],
    },
]

SPECIES_CARE = {
    "setosa": {
        "title": "Iris setosa",
        "summary": "Loài chịu lạnh tốt, thích đất ẩm và nơi mát. Phát triển khỏe ở khí hậu ôn đới.",
        "tips": ["Nắng: từ nắng đầy đủ đến bóng râm nhẹ, tránh nắng gắt kéo dài ở vùng nóng.",
                 "Nước: giữ đất ẩm đều, chịu được đất khá ướt.",
                 "Đất: tơi xốp, giàu mùn, hơi chua đến trung tính.",
                 "Bón phân: một lần vào đầu xuân bằng phân ít đạm."],
    },
    "versicolor": {
        "title": "Iris versicolor",
        "summary": "Còn gọi là blue flag, quen với vùng đất ngập nước nông, rất hợp mép ao hoặc vườn mưa.",
        "tips": ["Nắng: nắng đầy đủ đến bóng râm một phần.",
                 "Nước: chịu được đất ướt và nước nông, không cần để đất khô.",
                 "Đất: giàu mùn, giữ ẩm tốt.",
                 "Chia củ: mỗi 3 đến 4 năm sau khi hoa tàn."],
    },
    "virginica": {
        "title": "Iris virginica",
        "summary": "Loài ưa ẩm ướt, thường mọc ở đầm lầy và ven nước, hoa nở vào đầu hè.",
        "tips": ["Nắng: nắng đầy đủ đến bóng râm một phần.",
                 "Nước: ưa đất ẩm hoặc ướt, ngập nông được.",
                 "Đất: giàu hữu cơ, hơi chua.",
                 "Chăm sóc: ngắt hoa tàn, dọn lá khô cuối mùa để hạn chế sâu bệnh."],
    },
}

GENERAL_TIPS = [
    "Nắng: phần lớn diên vĩ ra hoa tốt khi có ít nhất 6 giờ nắng trực tiếp.",
    "Trồng: giữ phần trên của củ lộ ra mặt đất, trồng sâu dễ thối.",
    "Dọn vườn: dọn lá khô và hoa tàn để hạn chế nấm và sâu đục.",
]


def diagnose(symptom_ids, limit=4):
    ids = set(symptom_ids) & set(SYMPTOMS)
    out = []
    for d in DISEASES:
        hit = [s for s in d["signs"] if s in ids]
        if not hit:
            continue
        got = sum(d["signs"][s] for s in hit)
        score = got / sum(d["signs"].values())
        level = "Cao" if score >= 0.6 else ("Trung bình" if score >= 0.35 else "Thấp")
        out.append((score, got, {
            "id": d["id"], "name": d["name"], "likelihood": level, "severity": d["severity"],
            "cause": d["cause"], "treat": d["treat"], "prevent": d["prevent"],
            "matched": [SYMPTOMS[s] for s in hit],
        }))
    out.sort(key=lambda t: (-t[0], -t[1]))
    return [t[2] for t in out[:limit]]


def norm(text):
    t = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


KEYWORDS = {
    "leaf_spots": ["dom nau", "dom xam", "dom la", "dom den", "vet dom"],
    "leaf_tips_brown": ["kho dau la", "dau la kho", "chay dau la", "kho nau", "chay la"],
    "yellow_leaves": ["la vang", "vang la", "vang"],
    "wilting": ["heo", "ru", "guc", "xi", "heo ru"],
    "water_soaked": ["nhot", "ung nuoc", "nhao"],
    "holes_in_leaves": ["duc la", "lo tren la", "sau duc", "co sau", "sau an"],
    "orange_pustules": ["gi sat", "mun cam", "bot cam", "bot nau"],
    "mosaic": ["kham", "vet vang nhat"],
    "soft_rhizome": ["cu mem", "cu thoi", "thoi cu", "nhun", "mui hoi", "thoi re", "re thoi", "cu hu"],
    "stunted": ["coi coc", "lon cham", "khong lon", "chua lon"],
    "no_blooms": ["khong ra hoa", "khong no hoa", "khong co hoa", "it hoa", "chua ra hoa"],
    "distorted_buds": ["nut meo", "nut bien dang", "hoa meo", "vet bac", "nut khong no"],
    "gray_mold": ["moc xam", "moc hoa"],
    "sticky_insects": ["rep", "chat dinh", "kien bo", "con trung nho"],
}

FAQ = [
    (["tuoi", "nuoc", "uot"],
     "Diên vĩ không thích đất úng kéo dài (trừ loài ưa ẩm như versicolor và virginica). Tưới khi lớp đất mặt khô, "
     "tưới vào gốc và vào buổi sáng. Mùa nóng tưới 1 đến 2 lần mỗi tuần, mùa mát thưa hơn."),
    (["anh nang", "nhieu nang", "thieu nang", "nang gat", "du nang", "bong ram", "anh sang", "che nang"],
     "Cần ít nhất 6 giờ nắng trực tiếp để ra hoa tốt. Chỗ nắng gắt buổi chiều ở vùng nóng thì che nhẹ."),
    (["phan", "bon phan", "phan bon", "bon"],
     "Bón một lần vào đầu xuân bằng phân ít đạm, nhiều lân và kali. Thừa đạm khiến lá xanh tốt nhưng ít hoa và dễ thối củ."),
    (["chia cu", "chia", "nhan giong", "thay chau"],
     "Chia củ sau 3 đến 4 năm, tốt nhất sau khi hoa tàn. Đào lên, cắt bỏ phần già và hư, "
     "tỉa lá còn khoảng một phần ba, trồng lại với phần trên của củ lộ ra mặt đất."),
    (["chau", "trong chau"],
     "Chọn chậu rộng, có lỗ thoát nước, đất tơi xốp. Đặt củ gần sát mặt đất, không lấp kín."),
    (["cach trong", "trong cay", "mua nao", "khi nao trong", "thoi diem trong"],
     "Thời điểm trồng hoặc chia củ thích hợp là sau khi hoa tàn, khi trời mát. Chọn nơi nhiều nắng, đất thoát nước tốt."),
    (["cat tia", "ngat hoa", "hoa tan"],
     "Ngắt hoa tàn để tránh nấm. Cuối mùa cắt lá khô, nhưng chừa lá xanh để cây tích lũy dinh dưỡng."),
]


def _padded(text):
    return " " + re.sub(r"[^a-z0-9]+", " ", norm(text)) + " "


def _has(padded, keys):
    return any(" " + k + " " in padded for k in keys)


def detect_symptoms(message):
    m = _padded(message)
    return [sid for sid, kws in KEYWORDS.items() if _has(m, kws)]


def offline_reply(message, species=None, symptoms=None):
    found = list(dict.fromkeys((symptoms or []) + detect_symptoms(message)))
    m = _padded(message)
    if found:
        dx = diagnose(found, limit=2)
        if dx:
            lines = ["Dựa trên mô tả, mình thấy có thể là:"]
            for d in dx:
                lines.append(f"- **{d['name']}** (khả năng {d['likelihood'].lower()}): {d['cause']}")
            lines.append("Nên làm trước:")
            lines += [f"- {s}" for s in dx[0]["treat"][:3]]
            lines.append("Đây chỉ là gợi ý. Nếu cây xấu đi nhanh, hãy gặp người bán cây hoặc cán bộ bảo vệ thực vật địa phương.")
            return "\n".join(lines)
    for keys, answer in FAQ:
        if _has(m, keys):
            return answer
    if species in SPECIES_CARE:
        c = SPECIES_CARE[species]
        return c["summary"] + "\n" + "\n".join(f"- {t}" for t in c["tips"])
    return ("Mình chưa hiểu rõ câu hỏi. Bạn có thể mô tả triệu chứng (ví dụ lá vàng, củ mềm, không ra hoa), "
            "hoặc hỏi về tưới nước, ánh sáng, bón phân, chia củ.")


def system_prompt(species=None, symptoms=None):
    parts = [
        "Bạn là chuyên gia chăm sóc hoa diên vĩ (Iris) cho một ứng dụng bán hàng, trả lời bằng tiếng Việt, "
        "thân thiện, ngắn gọn (tối đa khoảng 150 từ), dùng gạch đầu dòng khi liệt kê các bước. "
        "Chỉ trả lời về cây cảnh và chăm sóc cây. Nếu câu hỏi ngoài chủ đề, lịch sự từ chối ngắn gọn. "
        "Không khẳng định chắc chắn về bệnh khi chưa đủ thông tin, hãy hỏi thêm triệu chứng. "
        "Với thuốc bảo vệ thực vật, luôn nhắc dùng theo nhãn. Không đưa liều lượng cụ thể."
    ]
    if species in SPECIES_CARE:
        parts.append(f"Loài của người dùng (theo mô hình nhận diện): {SPECIES_CARE[species]['title']}.")
    dx = diagnose(symptoms or [], limit=3)
    if dx:
        parts.append("Chẩn đoán sơ bộ từ hệ thống: " + "; ".join(f"{d['name']} (khả năng {d['likelihood']})" for d in dx) + ".")
    return " ".join(parts)
