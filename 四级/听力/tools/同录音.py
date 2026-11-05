"""按能量包络判断哪些音频文件是同一段录音（不看文件名）。
用法：python3 同录音.py 指纹.json 输出.json
两两找最佳错位（±120 秒），算重叠部分包络的相关系数；≥ 0.9 判为同一段录音。"""
import json, sys
import numpy as np
fp = json.load(open(sys.argv[1]))
E = [np.maximum(np.array(x['env']), -60.0) for x in fp]
def sim(a, b, maxlag=2400):
    best = (-1, 0)
    # 用前 6 分钟找错位，再在整段重叠上算相关
    A, B = a[:7200] - a[:7200].mean(), b[:7200] - b[:7200].mean()
    n = 1 << int(np.ceil(np.log2(len(A) + len(B))))
    c = np.fft.irfft(np.fft.rfft(A, n) * np.conj(np.fft.rfft(B, n)), n)
    lags = np.r_[np.arange(0, maxlag), np.arange(-maxlag, 0)]
    lag = int(lags[np.argmax(c[lags])])
    if lag >= 0: x, y = a[lag:], b
    else: x, y = a, b[-lag:]
    m = min(len(x), len(y))
    r = float(np.corrcoef(x[:m], y[:m])[0, 1])
    return r, lag * 0.05, m * 0.05
N = len(fp); par = list(range(N))
def find(i):
    while par[i] != i: i = par[i]
    return i
pairs = []
for i in range(N):
    for j in range(i + 1, N):
        if abs(fp[i]['decoded_dur'] - fp[j]['decoded_dur']) > 240: continue
        r, lag, ov = sim(E[i], E[j])
        if r >= 0.6: pairs.append([i, j, round(r, 3), round(lag, 2), round(ov, 1)])
        if r >= 0.9: par[find(i)] = find(j)
groups = {}
for i in range(N): groups.setdefault(find(i), []).append(i)
res = {'pairs': pairs, 'groups': [[fp[i]['file'] for i in g] for g in groups.values()]}
json.dump(res, open(sys.argv[2], 'w'), ensure_ascii=False, indent=1)
print(len(groups), 'groups'); 
for p in pairs:
    if p[2] < 0.9: print('边界', p, fp[p[0]]['file'][-40:], fp[p[1]]['file'][-40:])
