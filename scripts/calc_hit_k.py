import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.calibrate_min_score import QUESTIONS
from code_helper.rag.search import search

answerable = [q for q in QUESTIONS if q["expected"] == "answerable"]

h1_count = 0
h3_count = 0
h5_count = 0

print("Hit@K Evaluation on 10 Answerable Target Analysis Questions:")
print("=" * 70)

for q in answerable:
    matches = search(question=q["question"], top_k=5, min_score=0.0)
    files = [Path(m["path"]).name for m in matches]
    exp = [Path(ef).name.lower() for ef in q["expected_files"]]

    h1 = any(files[0].lower() == ef for ef in exp) if len(files) >= 1 else False
    h3 = any(f.lower() in exp for f in files[:3])
    h5 = any(f.lower() in exp for f in files[:5])

    if h1:
        h1_count += 1
    if h3:
        h3_count += 1
    if h5:
        h5_count += 1

    print(f"{q['id']} | hit@1={h1!s:<5} | hit@3={h3!s:<5} | hit@5={h5!s:<5} | retrieved={files} | expected={exp}")

print("=" * 70)
print(f"Total Hit@1: {h1_count}/{len(answerable)} ({h1_count/len(answerable)*100:.1f}%)")
print(f"Total Hit@3: {h3_count}/{len(answerable)} ({h3_count/len(answerable)*100:.1f}%)")
print(f"Total Hit@5: {h5_count}/{len(answerable)} ({h5_count/len(answerable)*100:.1f}%)")
