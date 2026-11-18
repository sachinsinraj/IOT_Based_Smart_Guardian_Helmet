"""Evaluate rule-based detector vs ML classifiers and create all result figures."""
import json, numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, precision_score, recall_score, f1_score,
                             confusion_matrix, roc_curve, auc, classification_report)
from detector import is_accident
from generate_dataset import CLASSES

R = "../results/"
df = pd.read_csv("../data/helmet_features.csv")
FEATS = [c for c in df.columns if c not in ("label", "class_name")]
X, y5 = df[FEATS], df["label"]
y = (y5 == 4).astype(int)
Xtr, Xte, ytr, yte, y5tr, y5te = train_test_split(X, y, y5, test_size=0.3, stratify=y5, random_state=7)

res, preds, probs = {}, {}, {}
# 1) rule-based (proposal logic) - no training needed
p = np.array([is_accident(r.acc_peak, r.tilt_change, r.speed_pre, r.speed_drop) for r in Xte.itertuples()]).astype(int)
preds["Rule-based"] = p
# 1b) rule-based with thresholds calibrated on the TRAINING split (grid search, max F1)
import itertools
from sklearn.metrics import f1_score as _f1
def rule(df_, g, tdeg, sd, minspd=15.0):
    return ((df_.acc_peak >= g) & (df_.tilt_change >= tdeg) & (df_.speed_pre >= minspd) & (df_.speed_drop >= sd)).astype(int).values
best = max(itertools.product([3.0, 3.5, 4.0, 5.0], [15, 20, 25, 30, 35, 45], [8, 10, 12, 15]),
           key=lambda p: _f1(ytr, rule(Xtr, *p)))
preds["Rule-based (calibrated)"] = rule(Xte, *best)
CAL = dict(IMPACT_G=best[0], TILT_DEG=best[1], SPEED_DROP=best[2])
print("calibrated thresholds:", CAL)
# 2) ML models
models = {
    "Logistic Regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, class_weight="balanced")),
    "Decision Tree": DecisionTreeClassifier(max_depth=5, class_weight="balanced", random_state=0),
    "Random Forest": RandomForestClassifier(n_estimators=200, max_depth=8, class_weight="balanced", random_state=0),
}
skf = StratifiedKFold(5, shuffle=True, random_state=1)
cv = {}
for n, m in models.items():
    cv[n] = cross_val_score(m, Xtr, ytr, cv=skf, scoring="f1")
    m.fit(Xtr, ytr); preds[n] = m.predict(Xte); probs[n] = m.predict_proba(Xte)[:, 1]
for n, p in preds.items():
    tn, fp, fn, tp = confusion_matrix(yte, p).ravel()
    res[n] = dict(accuracy=accuracy_score(yte, p), precision=precision_score(yte, p),
                  recall=recall_score(yte, p), f1=f1_score(yte, p), TP=int(tp), FP=int(fp), FN=int(fn), TN=int(tn),
                  false_alarm_rate=fp / (fp + tn), cv_f1_mean=float(cv[n].mean()) if n in cv else None,
                  cv_f1_std=float(cv[n].std()) if n in cv else None)
# 5-class Random Forest
rf5 = RandomForestClassifier(n_estimators=200, max_depth=8, class_weight="balanced", random_state=0).fit(Xtr, y5tr)
p5 = rf5.predict(Xte)
res["_multiclass_rf_accuracy"] = accuracy_score(y5te, p5)
res["_multiclass_report"] = classification_report(y5te, p5, target_names=CLASSES, output_dict=True)
res["_n_train"], res["_n_test"] = len(Xtr), len(Xte); res["_calibrated_thresholds"] = CAL
# error analysis for rule-based: missed accidents
miss = Xte[(yte == 1) & (preds["Rule-based"] == 0)]
res["_rule_missed_accidents"] = dict(n=len(miss), mean_tilt=float(miss.tilt_change.mean()), mean_peak=float(miss.acc_peak.mean()))
fa = Xte[(yte == 0) & (preds["Rule-based"] == 1)]
res["_rule_false_alarms_by_class"] = y5te[fa.index].map(dict(enumerate(CLASSES))).value_counts().to_dict()
json.dump(res, open(R + "metrics.json", "w"), indent=2, default=float)
print(pd.DataFrame({k: v for k, v in res.items() if not k.startswith("_")}).T.round(4).to_string())
print("5-class RF accuracy:", round(res["_multiclass_rf_accuracy"], 4))
print("rule missed:", res["_rule_missed_accidents"], "false alarms:", res["_rule_false_alarms_by_class"])

plt.rcParams.update({"font.size": 10, "figure.dpi": 130})
# Fig: raw signal examples
d = np.load("../data/raw_examples.npz"); t = np.arange(200) / 50
fig, ax = plt.subplots(4, 2, figsize=(10, 8), sharex=True)
for i, c in enumerate(["normal_riding", "hard_braking", "pothole_bump", "accident"]):
    ax[i, 0].plot(t, np.linalg.norm(d[c + "_acc"], axis=1), lw=1); ax[i, 0].set_ylabel("|a| (g)")
    ax[i, 1].plot(t, np.linalg.norm(d[c + "_gyro"], axis=1), color="C1", lw=1); ax[i, 1].set_ylabel("|w| (deg/s)")
    ax[i, 0].set_title(c.replace("_", " "), loc="left", fontsize=9)
ax[3, 0].set_xlabel("time (s)"); ax[3, 1].set_xlabel("time (s)")
plt.tight_layout(); plt.savefig(R + "fig_signals.png"); plt.close()
# Fig: class distribution
fig, a = plt.subplots(figsize=(6, 3.5)); df.class_name.value_counts().plot.bar(ax=a, color="#2b6cb0")
a.set_ylabel("windows"); a.set_title("Dataset class distribution"); plt.xticks(rotation=20); plt.tight_layout(); plt.savefig(R + "fig_class_dist.png"); plt.close()
# Fig: feature separation
fig, a = plt.subplots(1, 3, figsize=(11, 3.5))
for k, (fx, fy) in enumerate([("acc_peak", "tilt_change"), ("speed_drop", "acc_peak"), ("gyro_peak", "speed_drop")]):
    for ci, cn in enumerate(CLASSES):
        s = df[df.label == ci].sample(min(250, (df.label == ci).sum()), random_state=0)
        a[k].scatter(s[fx], s[fy], s=6, label=cn, alpha=.6)
    a[k].set_xlabel(fx); a[k].set_ylabel(fy)
a[0].legend(fontsize=7, markerscale=2); plt.tight_layout(); plt.savefig(R + "fig_features.png"); plt.close()
# Fig: confusion matrices
names = list(preds)
fig, a = plt.subplots(1, 5, figsize=(16, 3.2))
for ax_, n in zip(a, names):
    cm = confusion_matrix(yte, preds[n]); ax_.imshow(cm, cmap="Blues")
    for (i, j), v in np.ndenumerate(cm): ax_.text(j, i, v, ha="center", va="center", color="black")
    ax_.set_title(n, fontsize=9); ax_.set_xticks([0, 1], ["No acc.", "Accident"]); ax_.set_yticks([0, 1], ["No acc.", "Accident"])
    ax_.set_xlabel("Predicted"); ax_.set_ylabel("Actual")
plt.tight_layout(); plt.savefig(R + "fig_confusion.png"); plt.close()
# Fig: metric comparison
fig, a = plt.subplots(figsize=(9, 3.8)); w = 0.2
for i, m in enumerate(["accuracy", "precision", "recall", "f1"]):
    a.bar(np.arange(5) + i * w, [res[n][m] for n in names], w, label=m)
a.set_xticks(np.arange(5) + 1.5 * w, [n.replace(" (", "\n(") for n in names], fontsize=7); a.set_ylim(0.4, 1.02); a.legend(ncol=4, fontsize=8); a.set_title("Model comparison (test set)")
plt.tight_layout(); plt.savefig(R + "fig_metrics.png"); plt.close()
# Fig: ROC
fig, a = plt.subplots(figsize=(4.6, 4))
for n, pr in probs.items():
    fpr, tpr, _ = roc_curve(yte, pr); a.plot(fpr, tpr, label=f"{n} (AUC={auc(fpr, tpr):.3f})")
a.plot([0, 1], [0, 1], "k--", lw=.6); a.set_xlabel("False positive rate"); a.set_ylabel("True positive rate"); a.legend(fontsize=7); a.set_title("ROC curves")
plt.tight_layout(); plt.savefig(R + "fig_roc.png"); plt.close()
# Fig: feature importance
imp = pd.Series(models["Random Forest"].feature_importances_, FEATS).sort_values()
fig, a = plt.subplots(figsize=(5.5, 4)); imp.plot.barh(ax=a, color="#2f855a"); a.set_title("Random Forest feature importance")
plt.tight_layout(); plt.savefig(R + "fig_importance.png"); plt.close()
# Fig: 5-class confusion
cm = confusion_matrix(y5te, p5); fig, a = plt.subplots(figsize=(5.5, 4.5)); a.imshow(cm, cmap="Greens")
for (i, j), v in np.ndenumerate(cm): a.text(j, i, v, ha="center", va="center", fontsize=8)
a.set_xticks(range(5), CLASSES, rotation=30, fontsize=7); a.set_yticks(range(5), CLASSES, fontsize=7); a.set_title("5-class Random Forest")
plt.tight_layout(); plt.savefig(R + "fig_confusion5.png"); plt.close()
