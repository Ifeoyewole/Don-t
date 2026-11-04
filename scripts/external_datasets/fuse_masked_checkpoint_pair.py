"""Tune a two-checkpoint mixture on tuning only and report independent development metrics."""
import argparse,json
from pathlib import Path
import numpy as np


def read(path):return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]

def score(y,p,t):
    observed=y>=0;y=y[observed];p=p[observed]>=t
    tp=int(((y==1)&p).sum());fp=int(((y==0)&p).sum());fn=int(((y==1)&~p).sum())
    return {'support':int((y==1).sum()),'tp':tp,'fp':fp,'fn':fn,
            'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.,
            'f2':5*tp/(5*tp+fp+4*fn) if 5*tp+fp+4*fn else 0.}

def run(root):
    data={v:{s:read(root/f'{v}-{s}.jsonl') for s in ['threshold_tune','development_report']} for v in ['r4','r5']}
    for s in ['threshold_tune','development_report']:
        a,b=data['r4'][s],data['r5'][s]
        if len(a)!=len(b) or any(x['sha256']!=y['sha256'] or x['truth']!=y['truth'] for x,y in zip(a,b)):
            raise ValueError('Identity/truth mismatch')
    labels=list(data['r4']['threshold_tune'][0]['truth'])
    selection={};reports={v:{} for v in ['r4','r5','fusion']};misses=[]
    for label in labels:
        y=np.array([r['truth'][label] for r in data['r4']['threshold_tune']])
        probabilities={v:np.array([r['probabilities'][label] for r in data[v]['threshold_tune']]) for v in ['r4','r5']}
        dev_y=np.array([r['truth'][label] for r in data['r4']['development_report']])
        dev_p={v:np.array([r['probabilities'][label] for r in data[v]['development_report']]) for v in ['r4','r5']}
        if not (y==1).any():
            selection[label]={'status':'UNSUPPORTED_NO_TUNING_POSITIVES'};continue
        candidates=[]
        for w in [0.,.25,.5,.75,1.]:
            p=w*probabilities['r4']+(1-w)*probabilities['r5']
            options=[(score(y,p,t/100),t/100) for t in range(5,96,5)]
            m,t=max(options,key=lambda x:(x[0]['f1'],x[0]['f2'],-x[1]))
            candidates.append((m,t,w))
        single=max([x for x in candidates if x[2] in (0.,1.)],key=lambda x:(x[0]['f1'],x[0]['f2']))
        best=max(candidates,key=lambda x:(x[0]['f1'],x[0]['f2']))
        if best[2] not in (0.,1.) and (best[0]['f1']<single[0]['f1']+.02 or best[0]['f2']<=single[0]['f2']):best=single
        m,t,w=best
        selection[label]={'r4_weight':w,'r5_weight':1-w,'threshold':t,'tuning':m}
        reports['fusion'][label]=score(dev_y,w*dev_p['r4']+(1-w)*dev_p['r5'],t)
        for v,weight in [('r4',1.),('r5',0.)]:
            _,threshold,_=next(x for x in candidates if x[2]==weight)
            reports[v][label]=score(dev_y,dev_p[v],threshold)
        if label=='INFILTRATION':
            for i,r in enumerate(data['r4']['development_report']):
                if r['truth'][label]==1:
                    misses.append({'sha256':r['sha256'],'original_media_id':r['original_media_id'],
                        'r4_probability':float(dev_p['r4'][i]),'r5_probability':float(dev_p['r5'][i]),
                        'fusion_probability':float(w*dev_p['r4'][i]+(1-w)*dev_p['r5'][i]),'threshold':t})
    summary={}
    for v,classes in reports.items():
        supported=[m for m in classes.values() if m['support']>0]
        summary[v]={'macro_f1':float(np.mean([m['f1'] for m in supported])),
            'macro_f2':float(np.mean([m['f2'] for m in supported])),'evaluated_classes':len(supported),'per_class':classes}
    accepted=all(summary['fusion'][k]>max(summary[v][k] for v in ['r4','r5']) for k in ['macro_f1','macro_f2'])
    out={'selection':selection,'reports':summary,'acceptance_gate':{'accepted':accepted,'rule':'Exceed both standalone models on macro-F1 and macro-F2'},'infiltration_review':misses,'production_approved':False,'locked_test_evaluated':False}
    (root/'pair_fusion_report.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'metrics':{v:{k:x for k,x in m.items() if k!='per_class'} for v,m in summary.items()},'accepted':accepted,'infiltration_review':misses},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input-dir',type=Path,required=True);run(p.parse_args().input_dir)
