# MalayalamCyberCon — Pilot Annotation Guidelines

**Project:** Conflict and Cyberbullying Detection in Malayalam/Manglish YouTube Comment Threads  
**Version:** 1.0 (Pilot)  
**Language:** Manglish (Malayalam written in Roman script, or mixed Malayalam script + Roman)

---

## Your Task

You will be given **30 comment threads** from YouTube (`pilot_annotation.csv`).  
Each thread is a real back-and-forth conversation between users, anonymised so no real names appear.

For each thread you must fill in **three columns**:

| Column | What to fill |
|---|---|
| `label_conflict` | `0` = no conflict &nbsp;&nbsp; `1` = conflict |
| `label_severity` | `0` = none &nbsp;&nbsp; `1` = mild &nbsp;&nbsp; `2` = moderate &nbsp;&nbsp; `3` = severe |
| `label_type` | `1` = personal insult &nbsp;&nbsp; `2` = political &nbsp;&nbsp; `3` = sexual/gendered &nbsp;&nbsp; `4` = threat |
| `notes` | Optional. Write anything that helped or confused you. |

> **Rule:** If `label_conflict = 0`, leave `label_severity` and `label_type` blank.  
> **Rule:** If `label_conflict = 1`, `label_severity` must be 1, 2, or 3 and `label_type` must be 1, 2, 3, or 4.

---

## What Is a Conflict Thread?

A thread is a **conflict** if it contains **direct interpersonal hostility** — one user attacking, insulting, threatening, or degrading another user (not a public figure or topic).

The thread as a whole is the unit of judgment, but pay special attention to the message marked **★** (the final message), as that is what the model will predict.

### Conflict = YES if the thread contains:
- Direct insults aimed at another commenter (`poda`, `mandan`, `myre`, slurs)
- Personal attacks on someone's intelligence, character, appearance, or family
- Threats — physical, sexual, or social (`veettil keri thallum`, `naattil irakkilla`)
- Sexual harassment or objectification directed at a person
- Targeted political abuse aimed at a specific commenter (not just criticism of a party)
- Deliberate humiliation or public shaming of a commenter

### Conflict = NO if the thread contains:
- Disagreement about opinions, films, politics, or public figures — **without** targeting the other commenter personally
- Mild sarcasm or frustration with no personal attack
- Strong language used as an exclamation, not at a person (`myre` said to the air, not at a user)
- One-sided negative comment with no reply (no exchange = no thread conflict)
- Criticism of a public figure, politician, or celebrity (they are not the commenter)

---

## Severity Scale

Rate severity based on the **worst single message** in the thread.

---

## Conflict Type Scale

Rate type based on the **dominant form of hostility** in the thread. If multiple types exist, pick the most severe one.

| Level | Label | Description | Examples |
|---|---|---|---|
| 1 | Personal insult | Attack on intelligence, character, appearance, or family | `mandan`, `pottan`, `kalla`, `koothara`, "get a life", mocking someone's reasoning |
| 2 | Political/ideological | Targeted political abuse directed at a commenter (not just criticism of a party) | `chanakam`, calling a commenter a traitor, targeted political slur at a user |
| 3 | Sexual/gendered | Sexual harassment, objectification, or gendered abuse directed at a person | `charakku`, `vedi` used as slur, sexual comments about a user |
| 4 | Threat | Physical, social, or doxxing threat | `veettil keri thallum`, `naattil irakkilla`, any threat of harm |

**Priority rule:** If the thread contains a threat (type 4), label it 4 regardless of other types present. Threats override all other types.

| Level | Label | Description | Examples |
|---|---|---|---|
| 0 | None | No conflict at all | Regular disagreement, neutral conversation |
| 1 | Mild | Dismissive or rude, but no clear insult | `poda`, `poyi`, `get a life`, passive-aggressive tone |
| 2 | Moderate | Direct insult or personal attack | `mandan`, `pottan`, `kalla`, `koothara`, mocking intelligence or character |
| 3 | Severe | Slurs, sexual harassment, or threats | `myre`, `thayoli`, `charakku`, `vedi` used as slur, any physical or sexual threat |

**When in doubt between two levels, pick the lower one.** Consistency matters more than precision at this stage.

---

## Worked Examples

### Example A — Conflict = 0, Severity = 0
```
[1] Annie's cooking style is very different from traditional Kerala style
[2] Yes but she has her own audience who enjoy it
[3★] Athu sathyam aanu, avarude channel avarude choice
```
**Reasoning:** Three users sharing opinions. No personal attack on any commenter. Final message is neutral agreement.

---

### Example B — Conflict = 1, Severity = 1
```
[1] This movie was amazing, best of the year
[2] Overrated. Story had no logic at all
[3] Nee kandille? Climax scene enthu mahaneedham aayirunnu
[4★] Poda, ninte taste level ariyam
```
**Reasoning:** `poda` is directed at commenter [3]. Mild personal dismissal. No slur or threat.  
→ `label_conflict = 1`, `label_severity = 1`

---

### Example C — Conflict = 1, Severity = 2
```
[1] BJP always divides people with religion
[2] Congress did the same for 70 years
[3] Nee oru political mandan aanu, history ariyilla
[4★] Ningal okke oru chanakam party followers aanu, brain use cheyyuvo?
```
**Reasoning:** `mandan` (idiot) and `chanakam` (political slur) are directed at other commenters. Clear personal insults, political degradation.  
→ `label_conflict = 1`, `label_severity = 2`

---

### Example D — Conflict = 1, Severity = 3
```
[1] Jai sree ram
[2] Avanmaar okke terrorist support cheyyunavar
[3] Ninte religion ne parichayapeduthal venam enna illalo
[4] Jai sree ram maire
[5★] ninte Ammayude poor
```
**Reasoning:** Message [5] contains an extreme maternal slur directly targeting a commenter. Severity 3 regardless of what came before.  
→ `label_conflict = 1`, `label_severity = 3`

---

## Important Rules

1. **Label independently.** Do not discuss threads with other annotators until everyone has finished all 30.

2. **Label the thread, not the topic.** A thread about communal politics is not automatically a conflict. A thread about cooking can be a severe conflict. Judge the *interaction*, not the *subject*.

3. **The ★ message is important but not the only signal.** If messages [2] or [3] contain a severe slur, the thread is still severity 3 even if the final message is mild.

4. **Anonymisation means `@user1`, `@user2`, etc.** These are real people whose names have been removed. Treat them as real individuals being attacked or not.

5. **Code-mixed text is normal.** Threads mix Malayalam script, Roman-script Malayalam (Manglish), and English. If you cannot understand a word, note it in the `notes` column — do not guess.

6. **Do not label based on the video topic.** The video ID is shown but do not look up the video. Label only what is in the thread text.

7. **Zero-width spaces and emoji are common** and do not affect meaning. Ignore them.

---

## Quick Reference Card

```
CONFLICT = 1 when:           SEVERITY 3 when:
✓ Insult at a commenter      ✓ Any slur (myre, thayoli, vedi...)
✓ Threat of any kind         ✓ Any physical/sexual threat
✓ Sexual harassment          ✓ Extreme maternal/sexual abuse
✓ Personal degradation
                             SEVERITY 2 when:
CONFLICT = 0 when:           ✓ Clear personal insult (mandan, pottan)
✗ Disagreement only          ✓ Political slur at commenter
✗ Criticism of public figure ✓ Character attack
✗ Strong opinion, no attack
✗ Sarcasm with no target     SEVERITY 1 when:
                             ✓ Mild dismissal (poda, poyi)
                             ✓ Passive-aggressive tone
                             ✓ Rude but no slur/insult

TYPE (only if conflict=1):
  1 = Personal insult        (mandan, character attack, mocking)
  2 = Political/ideological  (chanakam, targeted political slur at user)
  3 = Sexual/gendered        (charakku, vedi as slur, sexual harassment)
  4 = Threat                 (veettil keri thallum — overrides all others)
```

---

## How to Submit

1. Open `pilot_annotation.csv` in Excel or Google Sheets.
2. Fill in `label_conflict`, `label_severity`, and optionally `notes` for all 30 rows.
3. Save as CSV (keep the filename as-is, add your name: e.g. `pilot_annotation_arjun.csv`).
4. Send the completed file to the team lead.

**Deadline:** Confirm with your team lead.  
**Questions:** Contact the team lead — do not discuss specific thread labels with other annotators.
