import re, sys

import os
log_path = os.environ.get('TEMP', '/tmp') + '/legacy_train.log'
with open(log_path, 'rb') as f:
    content = f.read().decode('utf-8', errors='replace')

lines = re.split(r'[\r\n]+', content)
summaries = [l.strip() for l in lines if re.search(r'Epoch \d+/25 \| Train Loss', l)]
for s in summaries:
    print(s)
print(f'\nEpochs logged so far: {len(summaries)}/25')

non_tqdm = [l.strip() for l in reversed(lines)
            if l.strip() and 'it/s' not in l and '%|' not in l]
if non_tqdm:
    print('Last line:', non_tqdm[0])
