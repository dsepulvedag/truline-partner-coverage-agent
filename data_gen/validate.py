import sys, time
import numpy as np, pandas as pd
import truline_gen as tg


def run(folder, n, n_real=0, real_df=None):
    t0 = time.time()
    tg.generate(tg.csv_sink(folder), real_df=real_df, log=lambda m: None, N_ACCOUNTS=n, N_REAL=n_real)
    return time.time() - t0


def report(d):
    am = pd.read_csv(f"{d}/ACCOUNT_MONTHLY.csv", parse_dates=["MONTH"])
    sm = pd.read_csv(f"{d}/SUBSCRIPTION_MONTHLY.csv", parse_dates=["MONTH"])
    cm = pd.read_csv(f"{d}/CONSUMPTION_MONTHLY.csv", parse_dates=["MONTH"])
    ac = pd.read_csv(f"{d}/ACCOUNTS.csv", parse_dates=["CHURN_MONTH"])
    pr = pd.read_csv(f"{d}/PRODUCTS.csv")
    out = {"rows": {k: len(x) for k, x in [("accounts", ac), ("account_monthly", am), ("sub_monthly", sm), ("consumption_monthly", cm)]}}
    br = (am.START_ARR + am.NEW_ARR + am.EXPANSION_ARR - am.CONTRACTION_ARR - am.CHURN_ARR
          - am.MIGRATED_OUT_ARR + am.MIGRATED_IN_ARR - am.END_ARR).abs().max()
    sb = (sm.groupby(["MONTH", "ACCOUNT_ID"]).ARR.sum() - am.set_index(["MONTH", "ACCOUNT_ID"]).END_ARR).abs().max()
    sbr = (sm.groupby(["MONTH", "ACCOUNT_ID"])[["NEW_ARR", "EXPANSION_ARR", "CONTRACTION_ARR", "CHURN_ARR"]].sum().sum(1)).shape
    out["bridge_max_err"], out["sub_vs_acct_max_err"] = round(br, 2), round(sb, 2)
    last = am.MONTH.max()
    for lbl, m0, m1 in [("FY-1", last - pd.DateOffset(years=2), last - pd.DateOffset(years=1)), ("FY0", last - pd.DateOffset(years=1), last)]:
        b = am[(am.MONTH == m0) & (am.END_ARR > 0)][["ACCOUNT_ID", "END_ARR", "BILLING_MODEL"]]
        e = am[am.MONTH == m1][["ACCOUNT_ID", "END_ARR"]]
        j = b.merge(e, on="ACCOUNT_ID", how="left", suffixes=("0", "1")).fillna({"END_ARR1": 0}).merge(ac[["ACCOUNT_ID", "SEGMENT"]])
        res = {}
        for seg, g in [("ALL", j)] + list(j.groupby("SEGMENT")) + list(j.groupby("BILLING_MODEL")):
            res[seg] = dict(NRR=round(g.END_ARR1.sum() / g.END_ARR0.sum(), 3),
                            GRR=round(np.minimum(g.END_ARR1, g.END_ARR0).sum() / g.END_ARR0.sum(), 3),
                            logo_churn=round((g.END_ARR1 == 0).mean(), 3), n=len(g))
        out[lbl] = res
    la = am[am.MONTH == last]
    arr = la.END_ARR.sum()
    out["ending_ARR_$B_scaled_to_300k"] = round(arr / len(ac) * 300_000 / 1e9, 2)
    out["consumption_share_of_ARR"] = round(la.CONSUMPTION_ARR.sum() / arr, 3)
    out["billing_mix_accounts"] = la.BILLING_MODEL.value_counts(normalize=True).round(3).to_dict()
    out["billing_mix_by_segment"] = (la.merge(ac[["ACCOUNT_ID", "SEGMENT"]]).groupby("SEGMENT").BILLING_MODEL
                                     .apply(lambda s: round((s != "Seats").mean(), 3)).to_dict())
    out["migration_uplift_in_over_out"] = round(am.MIGRATED_IN_ARR.sum() / max(am.MIGRATED_OUT_ARR.sum(), 1), 3)
    l12 = cm[cm.MONTH > last - pd.DateOffset(years=1)]
    cons_arr_avg = l12.groupby("MONTH").COMMIT_ARR.sum().mean()
    out["overage_rev_pct_of_consumption_ARR"] = round(l12.OVERAGE_REVENUE.sum() / cons_arr_avg, 3)
    out["expired_value_pct_of_consumption_ARR"] = round((l12.EXPIRED_CREDITS * l12.PRICE_PER_CREDIT_USD).sum() / cons_arr_avg, 3)
    out["topup_value_pct_of_consumption_ARR"] = round((l12.TOP_UP_CREDITS * l12.PRICE_PER_CREDIT_USD).sum() / cons_arr_avg, 3)
    out["burn_status_last"] = cm[cm.MONTH == last].BURN_STATUS.value_counts(normalize=True).round(3).to_dict()
    out["ARR_by_segment"] = (la.merge(ac[["ACCOUNT_ID", "SEGMENT"]]).groupby("SEGMENT").END_ARR.sum() / arr).round(3).to_dict()
    out["band_mix_last"] = la.RISK_BAND.value_counts(normalize=True).round(3).to_dict()
    out["avg_score_last"] = round(la.HEALTH_SCORE.mean(), 1)
    out["drivers_top"] = la.DRIVER_1.value_counts().head(8).to_dict()
    out["status"] = ac.STATUS.value_counts().to_dict()
    return out


if __name__ == "__main__":
    import json
    folder, n = sys.argv[1], int(sys.argv[2])
    secs = run(folder, n)
    r = report(folder)
    r["seconds"] = round(secs, 1)
    print(json.dumps(r, indent=1, default=str))


def fit(d):
    """Fit churn_prob_90d = sigmoid(a - b*score + c*renew90) to simulated outcomes."""
    am = pd.read_csv(f"{d}/ACCOUNT_MONTHLY.csv", parse_dates=["MONTH"])
    ac = pd.read_csv(f"{d}/ACCOUNTS.csv", parse_dates=["CHURN_MONTH"])
    last = am.MONTH.max()
    x = am[(am.MONTH >= am.MONTH.min() + pd.DateOffset(months=6)) & (am.MONTH <= last - pd.DateOffset(months=3))]
    x = x.merge(ac[["ACCOUNT_ID", "CHURN_MONTH", "CONTRACT_TERM"]])
    y = ((x.CHURN_MONTH > x.MONTH) & (x.CHURN_MONTH <= x.MONTH + pd.DateOffset(months=3))).to_numpy(float)
    r90 = ((x.CONTRACT_TERM == "Monthly") | x.MONTHS_TO_RENEWAL.between(1, 3)).to_numpy(float)
    full_r90 = r90.copy()
    keep = r90 > 0
    X = np.c_[np.ones(keep.sum()), -x.HEALTH_SCORE.to_numpy(float)[keep]]
    yk = y[keep]
    w = np.zeros(2)
    for _ in range(30):
        p = 1 / (1 + np.exp(-X @ w)); g = X.T @ (yk - p); H = (X * (p * (1 - p))[:, None]).T @ X
        w += np.linalg.solve(H + 1e-6 * np.eye(2), g)
    y, r90 = yk, full_r90[keep]
    s = x.HEALTH_SCORE.to_numpy()[keep]; order = np.argsort(s)
    ranks = np.empty(len(s)); ranks[order] = np.arange(len(s))
    auc = 1 - (ranks[y == 1].mean() - (y.sum() - 1) / 2) / (len(y) - y.sum())
    tab = pd.DataFrame({"band": x.RISK_BAND.to_numpy()[keep], "y": y}).groupby("band").y.mean().round(3)
    return dict(A=round(w[0], 3), B=round(w[1], 4), renewal_window_AUC=round(auc, 3), churn90_in_renewal_window=tab.to_dict())
