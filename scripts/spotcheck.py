import json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

threads = []
for i, l in enumerate(open("data/raw_threads.jsonl", encoding="utf-8"), 1):
    l = l.strip()
    if not l:
        continue
    try:
        threads.append(json.loads(l))
    except json.JSONDecodeError as e:
        print(f"[WARN] Skipping malformed line {i}: {e}", file=sys.stderr)
conflict = sum(1 for t in threads if t["likely_conflict"])
avg_msgs = sum(len(t["messages"]) for t in threads) / len(threads)

# Intensity distribution
intensity_counts = {i: 0 for i in range(6)}
for t in threads:
    intensity_counts[t.get("conflict_intensity", 0)] += 1

print(f"Total threads:           {len(threads)}")
print(f"likely_conflict=True:    {conflict}")
print(f"likely_conflict=False:   {len(threads) - conflict}")
print(f"Avg messages per thread: {avg_msgs:.1f}")
print()
print("Intensity distribution:")
labels = {0: "none", 1: "mild", 2: "insult", 3: "political", 4: "slur", 5: "threat"}
for i in range(6):
    print(f"  [{i}] {labels[i]:<12} {intensity_counts[i]:>4} threads")
print()

# Show 5 non-conflict + 5 highest-intensity threads for comparison
non_conflict = [t for t in threads if not t["likely_conflict"]][:5]
high_conflict = sorted([t for t in threads if t["likely_conflict"]],
                       key=lambda t: t.get("conflict_intensity", 0), reverse=True)[:5]

for label, sample in [("NON-CONFLICT SAMPLE", non_conflict), ("HIGH-INTENSITY SAMPLE", high_conflict)]:
    print(f"{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    for i, t in enumerate(sample):
        intensity = t.get("conflict_intensity", 0)
        print(f"\n--- {i+1} | video={t['video_id']} | intensity={intensity} | msgs={len(t['messages'])} ---")
        for j, msg in enumerate(t["messages"]):
            marker = "[TARGET]" if j == t["target_index"] else "        "
            print(f"  {marker} {msg[:120]}")
    print()
