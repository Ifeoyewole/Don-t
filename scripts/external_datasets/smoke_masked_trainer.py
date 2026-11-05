"""CPU assertions in the exact worker runtime; no cloud media or credentials needed."""
import sys
sys.path.insert(0, '/workspace/training')
import torch
from inspect_view_representation import macro_metrics, tune_thresholds

truth = torch.tensor([[1.], [0.], [-1.]])
logits = torch.tensor([[10.], [-10.], [10.]])
assert macro_metrics(truth, logits)['macro_f1'] == 1.0
assert tune_thresholds(torch.tensor([[0.], [-1.]]), torch.zeros(2,1)) == [0.5]
x = torch.tensor([[0.1,0.2,0.3]], requires_grad=True)
y = torch.tensor([[1.,0.,-1.]])
mask = y >= 0
loss = (torch.nn.functional.binary_cross_entropy_with_logits(x,y.clamp_min(0),reduction='none')*mask).sum()/mask.sum()
loss.backward()
assert x.grad[0,2].item() == 0
print({'status':'PASS','torch':torch.__version__,'unknown_gradient':x.grad[0,2].item()})
