import csv
import io
import json
from pathlib import Path


def csv_text(report):
    stream = io.StringIO(newline='')
    fields = ['rank','episode','start_timestamp','end_timestamp','duration','score','hook','cliffhanger','why']
    writer = csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore')
    writer.writeheader()
    for promo in report['promos']:
        row = dict(promo)
        for k in fields:
            # Keep exported text from becoming a spreadsheet formula.
            if isinstance(row.get(k),str) and row[k].lstrip().startswith(('=','+','-','@')):
                row[k] = "'" + row[k]
        writer.writerow(row)
    return stream.getvalue()


def save_report(report, directory):
    folder = Path(directory)
    # A new folder per run preserves unedited outputs and avoids accidental overwrite.
    folder.mkdir(parents=True,exist_ok=False)
    (folder/'results.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    (folder/'promos.csv').write_text(csv_text(report),encoding='utf-8')
    (folder/'raw_responses.json').write_text(json.dumps(report['raw_responses'],indent=2,ensure_ascii=False),encoding='utf-8')
