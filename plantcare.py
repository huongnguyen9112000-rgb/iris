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
        ("dry_wilt", "Thân hoặc lá khô dần, úa từ ngọn"),
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
        "id": "leaf_spot", "check": "Đốm có viền vàng và lan dần từ lá dưới lên không?", "name": "Bệnh đốm lá do nấm", "severity": "Trung bình",
        "cause": "Nấm lây qua nước bắn và tàn dư lá cũ, nặng hơn khi ẩm và ít thông thoáng.",
        "signs": {"leaf_spots": 3, "yellow_leaves": 1, "leaf_tips_brown": 1},
        "treat": ["Cắt bỏ lá có đốm, bỏ vào túi rác, không ủ phân.",
                  "Tưới vào gốc, tránh làm ướt lá, tưới vào buổi sáng.",
                  "Nếu lan rộng, phun thuốc trừ nấm gốc đồng hoặc mancozeb theo đúng nhãn."],
        "prevent": ["Tỉa thưa, giữ khoảng cách để gió lùa.", "Dọn sạch lá rụng vào cuối mùa."],
    },
    {
        "id": "soft_rot", "check": "Bạn thử nhẹ tay bới đất xem củ có mềm, nhớt hoặc có mùi hôi không?", "name": "Thối mềm thân rễ", "severity": "Cao",
        "cause": "Vi khuẩn xâm nhập qua vết thương hoặc vết sâu đục, nặng khi đất úng.",
        "signs": {"soft_rhizome": 3, "wilting": 2, "dry_wilt": 1, "yellow_leaves": 1, "water_soaked": 2},
        "treat": ["Đào củ lên, cắt bỏ toàn bộ phần mềm nhũn đến chỗ thịt củ còn trắng và cứng.",
                  "Dụng cụ cắt cần lau cồn hoặc nước tẩy loãng sau mỗi lần cắt.",
                  "Phơi củ nơi nắng và khô vài giờ, trồng lại vào đất thoát nước tốt.",
                  "Củ thối hoàn toàn thì bỏ đi, không trồng lại chỗ cũ."],
        "prevent": ["Không trồng sâu, để lộ nửa trên của củ.", "Đảm bảo thoát nước, không tưới quá nhiều."],
    },
    {
        "id": "borer", "check": "Có đường đục hoặc vệt nhớt dọc lá, và có sâu non màu hồng nhạt trong lá không?", "name": "Sâu đục lá và củ", "severity": "Cao",
        "cause": "Sâu non đục vào lá rồi xuống củ, tạo vết thương cho vi khuẩn gây thối.",
        "signs": {"holes_in_leaves": 3, "water_soaked": 2, "soft_rhizome": 1, "wilting": 1, "dry_wilt": 1},
        "treat": ["Bóp nhẹ dọc lá có vết đục để diệt sâu non, hoặc cắt bỏ lá đó.",
                  "Kiểm tra củ, loại bỏ phần bị đục và xử lý như bệnh thối mềm nếu có.",
                  "Dọn sạch tàn dư lá cũ vì trứng qua đông ở đó."],
        "prevent": ["Dọn lá khô vào cuối thu.", "Kiểm tra lá non mỗi tuần vào đầu mùa xuân."],
    },
    {
        "id": "rust", "check": "Mặt dưới lá có bột màu cam hoặc nâu gỉ sắt, chạm vào dính tay không?", "name": "Bệnh gỉ sắt", "severity": "Thấp đến trung bình",
        "cause": "Nấm gỉ sắt phát triển khi lá ẩm lâu, thường vào thời tiết mát ẩm.",
        "signs": {"orange_pustules": 3, "yellow_leaves": 1, "leaf_spots": 1},
        "treat": ["Cắt bỏ lá nhiễm nặng và tiêu hủy.",
                  "Giữ lá khô, tưới vào gốc.",
                  "Phun thuốc trừ nấm theo nhãn nếu bệnh tái phát nhiều lần."],
        "prevent": ["Tăng độ thông thoáng.", "Không bón thừa đạm."],
    },
    {
        "id": "botrytis", "check": "Hoa tàn có phủ lớp mốc xám và gần đây trời ẩm, nhiều sương không?", "name": "Thối xám (nấm Botrytis)", "severity": "Trung bình",
        "cause": "Nấm phát triển trên hoa tàn và mô yếu khi trời ẩm, lạnh, ít nắng.",
        "signs": {"gray_mold": 3, "distorted_buds": 1, "leaf_spots": 1},
        "treat": ["Ngắt hoa tàn và phần có mốc ngay, không để rơi xuống gốc.",
                  "Giảm ẩm, tưới ít hơn, tăng thông thoáng.",
                  "Phun thuốc trừ nấm theo nhãn khi mùa ẩm kéo dài."],
        "prevent": ["Ngắt hoa tàn thường xuyên.", "Tránh trồng quá dày."],
    },
    {
        "id": "thrips", "check": "Nụ có vệt bạc, méo hoặc không nở, và có côn trùng rất nhỏ trong nụ không?", "name": "Bọ trĩ", "severity": "Thấp đến trung bình",
        "cause": "Côn trùng rất nhỏ hút nhựa nụ và lá non, làm nụ méo, hoa có vệt bạc.",
        "signs": {"distorted_buds": 3, "no_blooms": 1, "leaf_tips_brown": 1},
        "treat": ["Cắt bỏ nụ hỏng nặng.",
                  "Xịt nước mạnh hoặc phun xà phòng côn trùng, dầu neem theo nhãn.",
                  "Lặp lại sau 5 đến 7 ngày vì bọ trĩ sinh sản nhanh."],
        "prevent": ["Kiểm tra nụ non thường xuyên.", "Dọn cỏ dại quanh gốc."],
    },
    {
        "id": "aphids", "check": "Có đàn côn trùng nhỏ bám ở lá non hoặc nụ, và lá có dính tay không?", "name": "Rệp và nguy cơ truyền virus", "severity": "Trung bình",
        "cause": "Rệp hút nhựa, tiết chất dính và có thể truyền virus giữa các cây.",
        "signs": {"sticky_insects": 3, "stunted": 1, "yellow_leaves": 1, "mosaic": 1},
        "treat": ["Xịt nước mạnh để rửa trôi rệp.",
                  "Phun xà phòng côn trùng hoặc dầu neem theo nhãn, nhắc lại sau một tuần.",
                  "Cách ly cây nếu có vệt khảm vì có thể đã nhiễm virus."],
        "prevent": ["Khuyến khích thiên địch như bọ rùa.", "Hạn chế bón thừa đạm tạo lá non mềm."],
    },
    {
        "id": "mosaic", "check": "Vệt khảm vàng nhạt có xuất hiện ở nhiều cây, cây có còi cọc hẳn không?", "name": "Virus khảm", "severity": "Cao",
        "cause": "Virus lây qua rệp và dụng cụ cắt, không có thuốc chữa.",
        "signs": {"mosaic": 3, "stunted": 2, "yellow_leaves": 1},
        "treat": ["Cách ly cây, khử trùng dụng cụ sau khi dùng.",
                  "Cây nhiễm nặng nên nhổ bỏ và tiêu hủy để tránh lây sang cây khác.",
                  "Diệt rệp để chặn đường lây."],
        "prevent": ["Dùng dụng cụ sạch.", "Mua giống từ nguồn đáng tin."],
    },
    {
        "id": "overwater", "check": "Đất dưới gốc đang ướt hay khô, và gần đây bạn tưới bao nhiêu lần mỗi tuần?", "name": "Tưới quá nhiều hoặc đất úng", "severity": "Trung bình",
        "cause": "Rễ thiếu oxy, lá vàng và héo dù đất vẫn ướt. Thường dẫn tới thối củ nếu kéo dài.",
        "signs": {"yellow_leaves": 2, "wilting": 2, "dry_wilt": 1, "soft_rhizome": 1, "stunted": 1},
        "treat": ["Ngưng tưới cho tới khi lớp đất mặt khô.",
                  "Kiểm tra củ, nếu mềm thì xử lý như bệnh thối mềm.",
                  "Cải tạo đất thoát nước, trồng chậu có lỗ thoát."],
        "prevent": ["Chỉ tưới khi lớp đất mặt khô.", "Trồng ở nền cao hoặc đất tơi xốp."],
    },
    {
        "id": "scorch", "check": "Đất đã khô sâu chưa, cây có bị nắng gắt buổi trưa hoặc mới bón phân không?", "name": "Khô héo do thiếu nước, nắng gắt hoặc thừa phân", "severity": "Thấp",
        "cause": "Thường do thiếu nước, nắng gắt, hoặc muối từ phân bón tích tụ.",
        "signs": {"leaf_tips_brown": 3, "dry_wilt": 3, "yellow_leaves": 1, "stunted": 1},
        "treat": ["Cắt phần khô, tưới đẫm đều khi đất khô sâu.",
                  "Xả nước nhiều để rửa muối nếu mới bón phân.",
                  "Giảm lượng phân, nhất là phân đạm."],
        "prevent": ["Tưới đều đặn.", "Bón phân ít và chia nhỏ lần."],
    },
    {
        "id": "no_bloom", "check": "Cây được bao nhiêu giờ nắng mỗi ngày, và đã chia củ lần nào chưa?", "name": "Cây không ra hoa do điều kiện trồng", "severity": "Thấp",
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
            "cause": d["cause"], "check": d["check"], "treat": d["treat"], "prevent": d["prevent"],
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
    "yellow_leaves": ["la vang", "vang la", "vang", "ua", "vang ua", "la ua"],
    "wilting": ["heo", "ru", "guc", "xi", "heo ru", "heo ua", "la rung"],
    "dry_wilt": ["bi kho", "dang kho", "kho het", "kho queo", "kho cung", "kho dan", "kho ngon", "than kho", "cay kho", "chet kho", "chet ngon", "kho heo", "kho khoe"],
    "water_soaked": ["nhot", "ung nuoc", "nhao"],
    "holes_in_leaves": ["duc la", "lo tren la", "sau duc", "co sau", "sau an"],
    "orange_pustules": ["gi sat", "mun cam", "bot cam", "bot nau"],
    "mosaic": ["kham", "vet vang nhat"],
    "soft_rhizome": ["than mem", "than nhun", "goc thoi", "goc mem", "cu mem", "cu thoi", "thoi cu", "nhun", "mui hoi", "thoi re", "re thoi", "cu hu"],
    "stunted": ["coi coc", "lon cham", "khong lon", "chua lon"],
    "no_blooms": ["khong ra hoa", "khong ra nut", "khong ra bong", "khong tro hoa", "khong no hoa", "khong co hoa", "it hoa", "chua ra hoa"],
    "distorted_buds": ["nut meo", "nut bien dang", "hoa meo", "vet bac", "nut khong no"],
    "gray_mold": ["moc xam", "moc hoa"],
    "sticky_insects": ["rep", "sau bo", "kien", "bo tri", "con trung", "chat dinh", "kien bo", "con trung nho"],
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


YES_WORDS = ["co", "roi", "dung", "phai", "vang", "u", "uh", "du"]
NO_WORDS = ["khong", "ko", "k", "chua", "chang", "khong co"]
WET_WORDS = ["uot", "nhieu", "hang ngay", "moi ngay", "suot", "sinh", "dam"]
DRY_WORDS = ["kho", "it", "thua", "hiem"]

# Phản hồi khi người dùng trả lời câu hỏi kiểm tra của từng bệnh. Khóa: yes hoặc no.
BRANCHES = {
    "leaf_spot": {
        "yes": "Vậy gần như chắc là đốm lá do nấm. Cắt bỏ lá có đốm và bỏ vào túi rác, dọn sạch lá rụng quanh gốc, tưới vào gốc thay vì lên lá. Nếu lan nhanh, phun thuốc trừ nấm gốc đồng theo đúng nhãn.",
        "no": "Đốm không lan và không có viền vàng thì có thể chỉ là cháy nắng hoặc vết sâu cắn. Cắt lá hỏng, theo dõi thêm 1 đến 2 tuần, nếu đốm lan ra thì xử lý như nấm đốm lá.",
    },
    "soft_rot": {
        "yes": "Củ mềm, nhớt hoặc có mùi hôi là dấu hiệu thối mềm, cần xử lý sớm. Đào củ lên, cắt bỏ phần thối đến chỗ thịt trắng và cứng, lau dụng cụ bằng cồn, phơi củ khô vài giờ rồi trồng lại ở chỗ thoát nước tốt.",
        "no": "Củ còn cứng và không hôi thì khả năng thối mềm thấp. Lá héo lúc này thường do thiếu hoặc thừa nước. Bạn kiểm tra độ ẩm đất và tình trạng rễ nhé.",
    },
    "borer": {
        "yes": "Rất có thể là sâu đục lá. Bóp nhẹ dọc vệt đục để diệt sâu non, cắt bỏ phần lá hỏng, rồi kiểm tra củ xem có bị đục hoặc thối không.",
        "no": "Không thấy sâu thì ít khả năng là sâu đục. Bạn thử xem lại bệnh đốm lá hoặc úng nước.",
    },
    "rust": {
        "yes": "Đúng là bệnh gỉ sắt rồi. Cắt bỏ lá nhiễm nặng, giữ lá khô khi tưới, và phun thuốc trừ nấm theo nhãn nếu bệnh lan.",
        "no": "Không có bột cam hoặc nâu gỉ sắt thì không phải gỉ sắt. Bạn xem lại đốm lá do nấm hoặc thiếu dinh dưỡng.",
    },
    "botrytis": {
        "yes": "Vậy là thối xám. Ngắt hoa tàn và phần có mốc ngay, không để rơi xuống gốc, giảm ẩm và tăng thông thoáng. Phun thuốc trừ nấm theo nhãn nếu trời ẩm kéo dài.",
        "no": "Không thấy mốc xám thì ít khả năng là Botrytis. Bạn xem lại bọ trĩ nếu nụ méo hoặc không nở.",
    },
    "thrips": {
        "yes": "Có thể là bọ trĩ. Cắt bỏ nụ hỏng nặng, xịt nước mạnh hoặc phun xà phòng côn trùng hoặc dầu neem theo nhãn, rồi lặp lại sau 5 đến 7 ngày.",
        "no": "Không thấy côn trùng thì nụ méo có thể do thiếu nước hoặc nhiệt độ thay đổi đột ngột. Bạn theo dõi thêm vài ngày nhé.",
    },
    "aphids": {
        "yes": "Vậy là rệp. Xịt nước mạnh để rửa trôi rệp, phun xà phòng côn trùng hoặc dầu neem theo nhãn, nhắc lại sau một tuần.",
        "no": "Không thấy rệp thì lá vàng hoặc còi cọc có thể do nguyên nhân khác như thiếu dinh dưỡng hoặc nước. Bạn mô tả thêm về đất và cách tưới nhé.",
    },
    "mosaic": {
        "yes": "Nhiều cây cùng có vệt khảm và còi cọc thì rất có thể là virus. Cách ly cây, khử trùng dụng cụ, diệt rệp. Cây nhiễm nặng nên nhổ bỏ và tiêu hủy.",
        "no": "Chỉ một cây, vệt nhẹ và cây vẫn khỏe thì có thể do thiếu dinh dưỡng. Bạn theo dõi thêm và bón phân cân đối.",
    },
    "overwater": {
        "yes": "Đất ướt liên tục là nguyên nhân chính. Ngưng tưới đến khi lớp đất mặt khô, kiểm tra xem củ có mềm không, và cải tạo đất cho thoát nước. Nếu trồng chậu, đảm bảo lỗ thoát không bị nghẹt.",
        "no": "Đất khô mà lá vẫn vàng thì ít khả năng do úng. Bạn kiểm tra thiếu nước, thiếu dinh dưỡng hoặc rễ yếu.",
    },
    "scorch": {
        "yes": "Vậy nhiều khả năng do khô hạn, nắng gắt hoặc thừa phân. Tưới đẫm và đều khi đất khô sâu, xả nước để rửa muối nếu mới bón phân, và giảm lượng phân đạm.",
        "no": "Nếu đất đủ ẩm và không bón phân gần đây thì kiểm tra rễ và củ xem có bị thối hoặc sâu đục không.",
    },
}


def _answer_kind(m, disease_id):
    if disease_id == "overwater":
        if _has(m, WET_WORDS):
            return "yes"
        if _has(m, DRY_WORDS):
            return "no"
    if _has(m, NO_WORDS):
        return "no"
    if _has(m, YES_WORDS):
        return "yes"
    return None


def _last_disease(last_bot):
    if not last_bot:
        return None
    for d in DISEASES:
        if d["check"] in last_bot:
            return d["id"]
    return None


def _followup(message, last_bot):
    did = _last_disease(last_bot)
    if not did:
        return None
    m = _padded(message)
    if did == "no_bloom":
        hours = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:h|gio|tieng)\b", message.lower().replace("giờ", "gio").replace("tiếng", "tieng"))
        not_split = _has(m, ["chua", "khong", "ko"])
        if hours:
            h = float(hours.group(1).replace(",", "."))
            if h >= 6:
                out = f"{h:g} giờ nắng là đủ rồi, nên thiếu nắng không phải nguyên nhân."
                if not_split:
                    out += " Vì chưa chia củ lần nào, khả năng cao là củ đã mọc dày và chen nhau nên không ra hoa. Sau khi hoa tàn (hoặc vào mùa mát), đào lên, cắt bỏ phần củ già và hư, chia ra rồi trồng lại thưa hơn."
                else:
                    out += " Bạn kiểm tra tiếp hai thứ: phần trên của củ có lộ ra mặt đất không (trồng sâu thì khó ra hoa) và có bón thừa đạm không (lá xanh tốt nhưng ít hoa). Đổi sang phân nhiều lân và kali."
                return out
            return f"{h:g} giờ nắng là hơi ít, diên vĩ cần ít nhất 6 giờ nắng trực tiếp để ra hoa. Bạn thử dời cây sang chỗ nhiều nắng hơn, năm sau cây sẽ ra hoa tốt hơn."
        if not_split:
            return "Chưa chia củ lần nào thì khả năng củ đã mọc dày. Cây trồng quá 3 đến 4 năm nên được chia. Nắng của cây mỗi ngày được khoảng bao nhiêu giờ?"
        return None
    kind = _answer_kind(m, did)
    return BRANCHES.get(did, {}).get(kind) if kind else None


def offline_reply(message, species=None, symptoms=None, last_bot=None):
    """Trả lời dự phòng khi không có AI: bám vào triệu chứng, nhận câu trả lời của người dùng cho câu hỏi kiểm tra."""
    m = _padded(message)
    said = detect_symptoms(message)
    if not said:
        fu = _followup(message, last_bot)
        if fu:
            return fu
    found = list(dict.fromkeys(said + [s for s in (symptoms or []) if s not in said]))
    if said or (found and not any(_has(m, k) for k, _ in FAQ)):
        dx = diagnose(found, limit=2)
        if dx:
            top = dx[0]
            mention = "; ".join(SYMPTOMS[s].lower() for s in said) if said else "các triệu chứng bạn đã chọn"
            lines = [f"Với mô tả \"{mention}\", mình nghĩ nhiều khả năng nhất là **{top['name']}**."]
            lines.append(top["cause"])
            if len(dx) > 1:
                lines.append(f"Cũng có thể là **{dx[1]['name']}**, nên bạn kiểm tra thêm để phân biệt.")
            lines.append("Nên làm trước:")
            lines += [f"- {t}" for t in top["treat"][:3]]
            lines.append("Để mình nói chính xác hơn: " + top["check"])
            return "\n".join(lines)
    for keys, answer in FAQ:
        if _has(m, keys):
            return answer
    if _last_disease(last_bot):
        return ("Mình chưa hiểu rõ câu trả lời của bạn cho câu hỏi vừa rồi. Bạn trả lời ngắn gọn có hoặc không, "
                "hoặc nói rõ hơn (ví dụ số giờ nắng, đất ướt hay khô) giúp mình nhé.")
    return ("Mình chưa hiểu rõ bạn đang gặp vấn đề gì. Bạn mô tả giúp mình cụ thể hơn nhé, ví dụ: "
            "lá vàng hay đốm nâu, củ có mềm hoặc hôi không, cây bao lâu chưa ra hoa, "
            "đất thường ướt hay khô. Bạn cũng có thể chọn triệu chứng ở tab Chẩn đoán bệnh.")


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
