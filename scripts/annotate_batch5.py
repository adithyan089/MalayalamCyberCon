import csv
from pathlib import Path

annotations = {
    'A1485': ('1','1','1','1','da manda - mild insult at commenter correcting film detail'),
    'A1486': ('0','','','',''),
    'A1487': ('0','','','',''),
    'A1488': ('1','1','2','1','religious targeting of commenter based on assumed belief'),
    'A1489': ('0','','','',''),
    'A1490': ('0','','','',''),
    'A1491': ('0','','','',''),
    'A1492': ('0','','','',''),
    'A1493': ('0','','','',''),
    'A1494': ('0','','','',''),
    'A1495': ('0','','','',''),
    'A1496': ('1','3','2,3','1','extreme slur + sexual insult invoking Muslim-Hindu tension'),
    'A1497': ('0','','','',''),
    'A1498': ('0','','','',''),
    'A1499': ('0','','','',''),
    'A1500': ('0','','','',''),
    'A1501': ('1','1','1','1','mandatharam - calling comment nonsense, mild dismissal'),
    'A1502': ('0','','','',''),
    'A1503': ('0','','','',''),
    'A1504': ('0','','','',''),
    'A1505': ('0','','','',''),
    'A1506': ('0','','','',''),
    'A1507': ('0','','','',''),
    'A1508': ('0','','','',''),
    'A1509': ('0','','','',''),
    'A1510': ('0','','','',''),
    'A1511': ('0','','','',''),
    'A1512': ('0','','','',''),
    'A1513': ('1','2','1','1','insulting fans by lineage - ketta pala thanthakku piranna'),
    'A1514': ('0','','','',''),
    'A1515': ('0','','','',''),
    'A1516': ('0','','','',''),
    'A1517': ('0','','','',''),
    'A1518': ('1','3','1','2','Tovino mairaan - severe slur at public figure'),
    'A1519': ('0','','','',''),
    'A1520': ('0','','','',''),
    'A1521': ('1','2','3','2','pennungalude pole ulla kattatam - gendered insult about Akhil'),
    'A1522': ('0','','','',''),
    'A1523': ('0','','','',''),
    'A1524': ('0','','','',''),
    'A1525': ('0','','','',''),
    'A1526': ('0','','','',''),
    'A1527': ('0','','','',''),
    'A1528': ('0','','','',''),
    'A1529': ('0','','','',''),
    'A1530': ('0','','','',''),
    'A1531': ('0','','','',''),
    'A1532': ('0','','','',''),
    'A1533': ('0','','','',''),
    'A1534': ('0','','','',''),
    'A1535': ('1','2','2','3','myratheram + Hindu-Muslim Sharia debate, political attack on community'),
    'A1536': ('1','3','3','1','andi oombi kodu mairan + thevidichikal - severe sexual slurs between commenters'),
    'A1537': ('0','','','',''),
    'A1538': ('0','','','',''),
    'A1539': ('0','','','',''),
    'A1540': ('1','1','1','1','kaashu poyathu nallathin - mocking commenter for watching bad movie'),
    'A1541': ('0','','','',''),
    'A1542': ('0','','','',''),
    'A1543': ('1','2','1','1','ninnaku janichappozhe vivaram illa - you had no sense since birth'),
    'A1544': ('1','2','2','2','Sujith oru kaafir alle - religious slur at public figure'),
    'A1545': ('0','','','',''),
    'A1546': ('0','','','',''),
    'A1547': ('0','','','',''),
    'A1548': ('0','','','',''),
    'A1549': ('1','1','1','1','ninte appuppan aavanum - mild comeback insult'),
    'A1550': ('0','','','',''),
    'A1551': ('0','','','',''),
    'A1552': ('0','','','',''),
    'A1553': ('1','1','1','1','nee kananda vachitt podo - mild dismissal between commenters'),
    'A1554': ('0','','','',''),
    'A1555': ('0','','','',''),
    'A1556': ('0','','','',''),
    'A1557': ('1','2','3','2','monkey emoji + village girl in Dileep assault case context - derogatory'),
    'A1558': ('0','','','',''),
    'A1559': ('0','','','',''),
    'A1560': ('0','','','',''),
    'A1561': ('0','','','',''),
    'A1562': ('0','','','',''),
    'A1563': ('0','','','',''),
    'A1564': ('0','','','',''),
    'A1565': ('0','','','',''),
    'A1566': ('0','','','',''),
    'A1567': ('1','1','2','3','bhagodo - dismissive at religious converts, political/religious tension'),
    'A1568': ('0','','','',''),
    'A1569': ('0','','','',''),
    'A1570': ('0','','','',''),
    'A1571': ('1','2','1','1','ninte achan edhire - bringing in commenters father, aggressive'),
    'A1572': ('0','','','',''),
    'A1573': ('0','','','',''),
    'A1574': ('0','','','',''),
    'A1575': ('0','','','',''),
    'A1576': ('0','','','',''),
    'A1577': ('0','','','',''),
    'A1578': ('0','','','',''),
    'A1579': ('1','1','1','2','vomit emojis at actress Muktha - mild mockery of public figure'),
    'A1580': ('0','','','',''),
    'A1581': ('1','2','1','1','ninte achante with fist emojis - expletive at commenter'),
    'A1582': ('0','','','',''),
    'A1583': ('0','','','',''),
    'A1584': ('0','','','',''),
    'A1585': ('0','','','',''),
    'A1586': ('0','','','',''),
    'A1587': ('0','','','',''),
    'A1588': ('0','','','',''),
    'A1589': ('1','1','1','1','nalla tholikkati ullavaraa - mild mockery of fans'),
    'A1590': ('1','1','2','1','udappikale sukipikkal + german shepherd follower - mild political insults'),
    'A1591': ('0','','','',''),
    'A1592': ('0','','','',''),
    'A1593': ('0','','','',''),
    'A1594': ('1','2','1','1','pooda mara manda + umbi - direct insults at commenter'),
    'A1595': ('0','','','',''),
    'A1596': ('0','','','',''),
    'A1597': ('1','2','3','2','lalunnik kompundo - crude sexual question about actor'),
    'A1598': ('0','','','',''),
    'A1599': ('0','','','',''),
    'A1600': ('0','','','',''),
    'A1601': ('0','','','',''),
    'A1602': ('0','','','',''),
    'A1603': ('0','','','',''),
    'A1604': ('0','','','',''),
    'A1605': ('0','','','',''),
    'A1606': ('0','','','',''),
    'A1607': ('0','','','',''),
    'A1608': ('1','1','1','1','vala panikkum podo manda - go do useful work, stupid'),
    'A1609': ('0','','','',''),
    'A1610': ('1','1','1','2','thadiyan lalunda - fat-shaming Mohanlal, mild body mockery'),
    'A1611': ('0','','','',''),
    'A1612': ('0','','','',''),
    'A1613': ('0','','','',''),
    'A1614': ('0','','','',''),
    'A1615': ('0','','','',''),
    'A1616': ('0','','','',''),
    'A1617': ('1','1','1','1','kannu komali - you blind fool, mild insult at commenter'),
    'A1618': ('0','','','',''),
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
