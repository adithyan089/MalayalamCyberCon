import csv
from pathlib import Path

annotations = {
    'A1619': ('0','','','',''),
    'A1620': ('0','','','',''),
    'A1621': ('1','2','1','1','ninte thanthaye kandu + 2 pottikkalum koduth - threat/slap insult at commenter'),
    'A1622': ('1','1','1','1','anthem mathramano ariyullu - mild dismissal of commenter knowledge'),
    'A1623': ('0','','','',''),
    'A1624': ('1','2','3','1','ninte achana pulli - vulgar sexual reference at commenter'),
    'A1625': ('0','','','',''),
    'A1626': ('0','','','',''),
    'A1627': ('0','','','',''),
    'A1628': ('0','','','',''),
    'A1629': ('0','','','',''),
    'A1630': ('0','','','',''),
    'A1631': ('0','','','',''),
    'A1632': ('0','','','',''),
    'A1633': ('0','','','',''),
    'A1634': ('0','','','',''),
    'A1635': ('0','','','',''),
    'A1636': ('0','','','',''),
    'A1637': ('1','1','2','3','sankikal - dismissive label toward political/religious group'),
    'A1638': ('1','1','1','1','pavade - condescending dismissal in Dileep case debate'),
    'A1639': ('0','','','',''),
    'A1640': ('1','2','2','1','shudda mandatharam + parents jawab nalkeendath - religious attack on commenter and family'),
    'A1641': ('0','','','',''),
    'A1642': ('1','3','1','1','myran lalappan fansyyinu - severe slur at fan group/commenter'),
    'A1643': ('0','','','',''),
    'A1644': ('0','','','',''),
    'A1645': ('0','','','',''),
    'A1646': ('0','','','',''),
    'A1647': ('1','1','1','1','cry more mone - mild mockery of fan in movie debate'),
    'A1648': ('0','','','',''),
    'A1649': ('0','','','',''),
    'A1650': ('0','','','',''),
    'A1651': ('0','','','',''),
    'A1652': ('0','','','',''),
    'A1653': ('1','1','1','2','mega achar mockery of Dulquer Salman - mild fan rivalry insult at public figure'),
    'A1654': ('0','','','',''),
    'A1655': ('0','','','',''),
    'A1656': ('0','','','',''),
    'A1657': ('1','1','1','2','listing Mohanlal flops mockingly - mild attack on public figure'),
    'A1658': ('0','','','',''),
    'A1659': ('0','','','',''),
    'A1660': ('0','','','',''),
    'A1661': ('0','','','',''),
    'A1662': ('0','','','',''),
    'A1663': ('0','','','',''),
    'A1664': ('0','','','',''),
    'A1665': ('0','','','',''),
    'A1666': ('0','','','',''),
    'A1667': ('1','2','1','1','kundi aan + onnu poyeda - vulgar dismissal at commenter'),
    'A1668': ('0','','','',''),
    'A1669': ('0','','','',''),
    'A1670': ('0','','','',''),
    'A1671': ('0','','','',''),
    'A1672': ('0','','','',''),
}

path = Path('D:/Nlp/data/annotations/annotation_batch_adithyanr5.csv')
rows = list(csv.DictReader(path.open(encoding='utf-8-sig')))
fieldnames = list(rows[0].keys())

updated = 0
for row in rows:
    bid = row['batch_id']
    if bid in annotations and row['label_conflict'].strip() == '':
        c, s, t, tgt, n = annotations[bid]
        row['label_conflict'] = c
        row['label_severity'] = s
        row['label_type']     = t
        row['label_target']   = tgt
        row['notes']          = n
        updated += 1

with path.open('w', encoding='utf-8-sig', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f'Updated {updated} rows')

rows2 = list(csv.DictReader(path.open(encoding='utf-8-sig')))
unlabeled = sum(1 for r in rows2 if r['label_conflict'].strip() == '')
c1 = sum(1 for r in rows2 if r['label_conflict'] == '1')
c0 = sum(1 for r in rows2 if r['label_conflict'] == '0')
print(f'Total: {len(rows2)}  conflict=1: {c1}  conflict=0: {c0}  unlabeled: {unlabeled}')
