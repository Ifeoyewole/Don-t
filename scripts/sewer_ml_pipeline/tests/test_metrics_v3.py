from pathlib import Path
import sys
import numpy as np
import pytest
from metrics_v3 import confusion, metrics, calibration, tune_thresholds, complete_report

def test_known_counts_and_f2():
    a=metrics([1,1,0,0],[1,0,1,0])
    assert {k:a[k] for k in ('tp','fp','fn','tn')}==dict(tp=1,fp=1,fn=1,tn=1)
    assert a['f1']==.5 and a['f2']==.5

def test_calibration_vs_positive_frequency():
    a=calibration(np.array([[0],[1]]),np.array([[.1],[.9]]),bins=2)
    assert a['ece_macro']==pytest.approx(.1)

def test_threshold_from_separate_calibration_set():
    t=np.array([[0,0],[1,0],[1,1]]); p=np.array([[.2,.1],[.4,.2],[.6,.3]])
    assert tune_thresholds(t,p,[.25,.5])==[.25,.25]

def test_counts_macro_and_micro_real():
    t=np.array([[1,0],[0,1]]); p=np.array([[.9,.2],[.2,.8]])
    a=complete_report(t,p,['FS','ND'],[.5,.5])
    assert a['micro']['tp']==2 and a['micro']['tn']==2
    assert a['macro_f1']==1

def test_shape_mismatch_fail_closed():
    with pytest.raises(ValueError): complete_report(np.array([[1,0]]),np.array([[.7]]),['FS','ND'],[.5,.5])
