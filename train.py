import engine

art = engine.build_and_save()
print("Model saved!")
for m in art["meta"]["models"]:
    print(f"  {m['name']:<24} chính xác {m['cv_mean']*100:.1f}% (±{m['cv_std']*100:.1f})")
