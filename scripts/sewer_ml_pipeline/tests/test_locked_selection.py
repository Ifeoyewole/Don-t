from pathlib import Path
import sys
from extract_locked_test_v2 import selection

def test_locked_selection_is_deterministic_and_capped():
    rows=[{'Filename':f'{i}.png','FS':str(i%3==0),'ND':str(i%3!=0)} for i in range(100)]
    assert selection(rows,cap=30)==selection(list(reversed(rows)),cap=30)
    assert len(selection(rows,cap=30))==30
