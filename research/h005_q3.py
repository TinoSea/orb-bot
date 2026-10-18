"""H-005 Q3: what distinguishes the moments she trades? (her aligned days only: 2025-10-31, 2025-11-03)"""
import numpy as np, pandas as pd, json
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from h005 import load_seconds, load_m1, Context, features_day, FEATURES, tsec
from h005_q1 import HER
days = load_seconds(); C = Context(load_m1())
F = pd.concat([features_day(days[d], C, d) for d in ['2025-10-31', '2025-11-03']], ignore_index=True)
F['y'] = 0
for d, t, tol, side, _ in HER:
    c = tsec(t); k = F[(F.date == d) & (F.side == side) & (F.close_t <= c)].close_t.max()
    F.loc[(F.date == d) & (F.side == side) & (F.close_t == k), 'y'] = 1
print('candidates', len(F), 'positives', F.y.sum())
# univariate: her percentile per feature, and univariate AUC
uni = []
for f in FEATURES:
    a = roc_auc_score(F.y, F[f]) if F[f].nunique() > 1 else 0.5
    uni.append(dict(feature=f, her_mean=F[F.y == 1][f].mean(), all_mean=F[F.y == 0][f].mean(), auc=a))
U = pd.DataFrame(uni); U['strength'] = (U.auc - 0.5).abs(); U = U.sort_values('strength', ascending=False)
print(U.round(3).to_string(index=False))
# L1 logistic, leave-one-day-out
X = (F[FEATURES] - F[FEATURES].mean()) / F[FEATURES].std().replace(0, 1)
pred = np.zeros(len(F))
for d in F.date.unique():
    tr, te = F.date != d, F.date == d
    m = LogisticRegression(penalty='l1', C=0.5, solver='liblinear', class_weight='balanced').fit(X[tr], F.y[tr])
    pred[te] = m.decision_function(X[te])
auc = roc_auc_score(F.y, pred)
rng = np.random.default_rng(1); boots = []
pos, neg = np.where(F.y == 1)[0], np.where(F.y == 0)[0]
for _ in range(2000):
    p, n = rng.choice(pos, len(pos)), rng.choice(neg, len(neg))
    boots.append(roc_auc_score(np.r_[np.ones(len(p)), np.zeros(len(n))], np.r_[pred[p], pred[n]]))
print(f'L1 logistic leave-one-day-out AUC {auc:.3f} (bootstrap 95% {np.percentile(boots,2.5):.2f}-{np.percentile(boots,97.5):.2f})')
full = LogisticRegression(penalty='l1', C=0.5, solver='liblinear', class_weight='balanced').fit(X, F.y)
coef = pd.Series(full.coef_[0], FEATURES).sort_values(key=abs, ascending=False)
print('full-sample L1 coefficients:'); print(coef.round(3).to_string())
F.to_csv('results/h005/q3_candidates.csv', index=False); U.to_csv('results/h005/q3_univariate.csv', index=False)
json.dump(dict(auc_lodo=auc, auc_ci=[float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
               coef=coef.to_dict(), positives=int(F.y.sum()), candidates=len(F)), open('results/h005/q3.json', 'w'), indent=1)
