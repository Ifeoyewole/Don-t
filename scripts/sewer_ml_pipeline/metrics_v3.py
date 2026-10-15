"""Statistical metrics, including true count totals, for multi-label sewer defects."""
from __future__ import annotations
import numpy as np


def confusion(y, predicted):
    y=np.asarray(y,dtype=bool); predicted=np.asarray(predicted,dtype=bool)
    if y.shape!=predicted.shape: raise ValueError('Truth/prediction shape mismatch')
    return {'tp':int((y&predicted).sum()),'fp':int((~y&predicted).sum()),
            'fn':int((y&~predicted).sum()),'tn':int((~y&~predicted).sum())}


def metrics(y,predicted):
    c=confusion(y,predicted)
    tp,fp,fn=(c[k] for k in ('tp','fp','fn'))
    precision=tp/(tp+fp) if tp+fp else 0.0
    recall=tp/(tp+fn) if tp+fn else 0.0
    f1=2*precision*recall/(precision+recall) if precision+recall else 0.0
    f2=5*precision*recall/(4*precision+recall) if 4*precision+recall else 0.0
    return {**c,'precision':precision,'recall':recall,'f1':f1,'f2':f2,
            'false_positive_rate':fp/(fp+c['tn']) if fp+c['tn'] else 0.0,
            'false_negative_rate':fn/(fn+tp) if fn+tp else 0.0}


def tune_thresholds(truth,probabilities,grid=None):
    t=np.asarray(truth);p=np.asarray(probabilities)
    if t.ndim!=2 or p.shape!=t.shape: raise ValueError('Expected [N,C] same shape')
    if not np.isfinite(p).all() or ((p<0)|(p>1)).any(): raise ValueError('Invalid probabilities')
    grid=np.asarray(grid if grid is not None else np.arange(0.1,0.91,0.05))
    return [float(max((metrics(t[:,i],p[:,i]>=cut)['f1'], -float(cut),float(cut)) for cut in grid)[2])
            for i in range(t.shape[1])]


def calibration(truth,probabilities,bins=10):
    t=np.asarray(truth,dtype=float);p=np.asarray(probabilities,dtype=float)
    if t.shape!=p.shape or t.ndim!=2: raise ValueError('Calibration requires [N,C] arrays')
    if not np.isfinite(p).all() or ((p<0)|(p>1)).any(): raise ValueError('Invalid probabilities')
    ec=[]
    for j in range(p.shape[1]):
        class_ece=0.0
        for k in range(bins):
            lo=k/bins; hi=(k+1)/bins
            inside=(p[:,j]>=lo) & (p[:,j]<(hi if k<bins-1 else hi+1e-12))
            if inside.any(): class_ece += inside.mean()*abs(float(p[inside,j].mean()-t[inside,j].mean()))
        ec.append(class_ece)
    return {'ece_macro':float(np.mean(ec)),'brier':float(np.mean((p-t)**2)),
            'ece_per_class':[float(x) for x in ec]}


def complete_report(truth,probabilities,class_names,thresholds):
    t=np.asarray(truth,dtype=int);p=np.asarray(probabilities,dtype=float)
    if t.shape!=p.shape or t.shape[1]!=len(class_names) or len(thresholds)!=t.shape[1]:
        raise ValueError('Label/class/threshold dimensions disagree')
    pred=p>=np.asarray(thresholds)[None,:]
    classes={name:metrics(t[:,i],pred[:,i]) for i,name in enumerate(class_names)}
    return {'sample_count':len(t),'classwise':classes,
            'macro_f1':float(np.mean([x['f1'] for x in classes.values()])),
            'macro_f2':float(np.mean([x['f2'] for x in classes.values()])),
            'micro':metrics(t,pred), 'calibration':calibration(t,p),
            'thresholds':{name:float(thresholds[i]) for i,name in enumerate(class_names)}}
