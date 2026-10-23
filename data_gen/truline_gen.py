"""Truline synthetic data generator.

Truline is a FICTIONAL B2B design-software vendor: 15 products, fictional reseller
partners, N customer accounts (an optional slice uses real company names; everything
about them is invented), and 36 months of account x product usage, ARR movements and an
illustrative pre-computed health score. Python 3.9+, numpy, pandas. Deterministic per SEED.
"""
import datetime as dt
import warnings
import numpy as np
import pandas as pd

CFG = dict(N_ACCOUNTS=300_000, N_REAL=5_000, N_PARTNERS=500,
           START="2023-10-01", N_MONTHS=36, SEED=42, CHUNK=25_000)

# ------------------------------------------------------------------ catalog (fictional)
PRODUCTS = [  # code, name, family, annual list price per seat (USD), description
    ("DRAFT", "Truline Draft", "Core Design", 1950, "2D/3D drafting and documentation"),
    ("DLITE", "Truline Draft Lite", "Core Design", 520, "2D-only drafting"),
    ("BUILD", "Truline Build", "Building & Infrastructure", 2950, "Building information modeling (BIM)"),
    ("CIVIL", "Truline Civil", "Building & Infrastructure", 3100, "Civil and infrastructure design"),
    ("COORD", "Truline Coordinate", "Building & Infrastructure", 1650, "Model review and clash detection"),
    ("SITE", "Truline Site", "Building & Infrastructure", 1150, "Cloud construction management"),
    ("BSUITE", "Truline Building Suite", "Building & Infrastructure", 3650, "Bundle of building products"),
    ("FORM", "Truline Form", "Manufacturing", 1780, "3D product design"),
    ("MACH", "Truline Machine", "Manufacturing", 2450, "CAM and toolpath programming"),
    ("PDM", "Truline PDM", "Manufacturing", 940, "Product data management"),
    ("MSUITE", "Truline Manufacturing Suite", "Manufacturing", 3350, "Bundle of manufacturing products"),
    ("MOTION", "Truline Motion", "Media & Entertainment", 1920, "3D animation"),
    ("RENDER", "Truline Render", "Media & Entertainment", 1080, "Rendering and visualization"),
    ("MESUITE", "Truline Media Suite", "Media & Entertainment", 2750, "Bundle of media products"),
    ("COLLAB", "Truline Collaborate", "Cross-Platform", 590, "Cloud collaboration and file sharing"),
]
CODES = [p[0] for p in PRODUCTS]
PI = {c: i for i, c in enumerate(CODES)}
FAMILY = np.array([p[2] for p in PRODUCTS])
LIST_PRICE = np.array([p[3] for p in PRODUCTS], float)
NPROD = len(PRODUCTS)

GROUPS = ["Building & Infrastructure", "Manufacturing", "Media & Entertainment", "General Engineering & Other"]
GROUP_SHARE = [0.46, 0.27, 0.07, 0.20]
INDUSTRIES = [
    ["Construction", "Architecture & Planning", "Civil Engineering", "Real Estate Development", "Building Materials"],
    ["Industrial Machinery", "Automotive", "Aerospace", "Consumer Products", "Electronics Manufacturing"],
    ["Animation", "Film & TV Production", "Video Games", "Advertising & Design"],
    ["Engineering Services", "Utilities", "Energy", "Education", "Government"],
]
W_GROUP = np.array([  # product propensity by industry group (column order = PRODUCTS)
    [3, 3, 4, 2, 1.5, 1.5, 4, 0, 0, 0, 0, 0, .3, 0, 1.2],
    [3, 2, 0, 0, 0, 0, 0, 4, 2, 1.5, 4, 0, .3, 0, 1.0],
    [.5, .5, 0, 0, 0, 0, 0, .2, 0, 0, 0, 4, 2.5, 3.5, .8],
    [5, 4, .5, 1, .3, .3, .5, .8, .2, .2, .3, .1, .2, 0, 1.0],
])
SEGS = ["SMB", "Mid-Market", "Enterprise"]
SEG_SHARE = [0.84, 0.14, 0.02]
SEG_MULT = np.ones((3, NPROD))
_SUITES = [PI["BSUITE"], PI["MSUITE"], PI["MESUITE"]]
SEG_MULT[0, _SUITES] = .25
SEG_MULT[0, PI["DLITE"]] = 2.5
SEG_MULT[0, PI["COLLAB"]] = .6
SEG_MULT[2, _SUITES] = 2.5
SEG_MULT[2, PI["DLITE"]] = .2
for _c in ("PDM", "COORD", "COLLAB"):
    SEG_MULT[2, PI[_c]] = 1.5
DISCOUNT = np.array([[0, .05], [.05, .15], [.15, .30]])
SEATS_LOGN = [(np.log(3), .7, 1, 40), (np.log(22), .6, 8, 300), (np.log(140), .8, 40, 4000)]
EMP_BANDS = [(["1-10", "11-50", "51-200"], [.45, .40, .15]),
             (["51-200", "201-500", "501-1000"], [.30, .45, .25]),
             (["1001-5000", "5001-10000", "10001+"], [.60, .25, .15])]
TERMS = ["Monthly", "Annual", "3-Year"]
TERM_P = [[.20, .75, .05], [.08, .77, .15], [0, .70, .30]]
SEG_H0 = np.array([0.0, 0.2, 0.35])
SEG_CHURN_ADJ = np.array([0.65, 0.0, -0.9])
TOUCH_RATE = np.array([0.15, 0.5, 1.6])
TRAJ = np.array(["growing", "steady", "declining"])
TRAJ_P = np.array([.25, .57, .18])
TRAJ_MU = np.array([.020, .005, -.015])  # monthly log growth of user demand
CHURN_B0 = -2.9
# ---- consumption (prepaid credits + overage)
CREDIT_LIST_PRICE = 1.00   # USD per credit at list; overage is billed at list
CREDIT_RATE = 1.45         # sizes credit burn so a typical active user costs about what a seat did
MIG_BASE = np.array([.06, .14, .22])  # chance per renewal that a seat account moves to credits (by segment, at full ramp)
NATIVE_SHARE = .25         # share of new logos in the last 18 months that start on credits
HEALTH_B0 = 1.25
PROB_A, PROB_B, PROB_OFF_CYCLE = -.63, .040, .1  # churn_prob_90d = sigmoid(A - B*score), x0.1 if no renewal within 90d

REGIONS = ["Americas", "EMEA", "APAC"]
REGION_SHARE = [.44, .39, .17]
COUNTRIES = [
    [("United States", .74, ["Inc.", "LLC", "Corp."]), ("Canada", .12, ["Inc.", "Ltd."]),
     ("Mexico", .07, ["S.A. de C.V."]), ("Brazil", .07, ["Ltda."])],
    [("Germany", .22, ["GmbH", "AG"]), ("United Kingdom", .22, ["Ltd", "plc"]), ("France", .14, ["SAS", "SA"]),
     ("Italy", .09, ["S.p.A.", "S.r.l."]), ("Netherlands", .08, ["B.V."]), ("Spain", .08, ["S.L.", "S.A."]),
     ("Sweden", .05, ["AB"]), ("United Arab Emirates", .06, ["LLC"]), ("South Africa", .06, ["(Pty) Ltd"])],
    [("Japan", .34, ["K.K.", "Co., Ltd."]), ("Australia", .20, ["Pty Ltd"]), ("India", .15, ["Pvt. Ltd."]),
     ("South Korea", .12, ["Co., Ltd."]), ("Singapore", .09, ["Pte. Ltd."]), ("China", .10, ["Co., Ltd."])],
]
_EXTRA_REGION = {"ireland": 1, "switzerland": 1, "austria": 1, "belgium": 1, "denmark": 1, "norway": 1,
                 "finland": 1, "poland": 1, "israel": 1, "saudi arabia": 1, "turkey": 1, "portugal": 1,
                 "new zealand": 2, "hong kong": 2, "taiwan": 2, "indonesia": 2, "malaysia": 2,
                 "thailand": 2, "vietnam": 2, "philippines": 2, "argentina": 0, "chile": 0, "colombia": 0, "peru": 0}
COUNTRY_REGION = dict(_EXTRA_REGION, **{c[0].lower(): r for r, lst in enumerate(COUNTRIES) for c in lst})
MOY_W = np.array([.06, .06, .10, .06, .06, .10, .06, .06, .10, .08, .09, .17])
MOY_W = MOY_W / MOY_W.sum()
SEASON = np.ones((3, 12))
SEASON[:, 11], SEASON[:, 0] = .86, .96
SEASON[0, 7], SEASON[1, 7], SEASON[2, 7], SEASON[2, 1] = .95, .82, .96, .93

W1 = sorted(set("""Alder Ashford Avery Bancroft Barrow Beacon Bellamy Benning Birch Blackwell Bradford Brennan
Brighton Calder Camden Carver Castell Cedar Chandler Chapman Clayton Colby Cole Cooper Copeland Crane Crawford
Dalton Danforth Delaney Denham Drake Dunmore Easton Elliott Ellison Emerson Everett Fairfax Falk Fenwick Finch
Fleming Forrester Fowler Garrison Gibbs Gilmore Graham Granger Grayson Hadley Hale Halvorsen Harlan Harper Hartley
Hastings Hawthorne Hayes Hendricks Holloway Hughes Ingram Irving Jansen Jarvis Kearney Keller Kendall Kerr Kingsley
Knox Lambert Langley Larsen Lawson Lennox Lindqvist Lockhart Lowell Lyons Maddox Mallory Marlow Mercer Merritt
Monroe Morrow Nash Newell Norris Oakley Ogden Osborne Pace Paxton Pemberton Pierce Porter Prescott Quinlan
Radcliffe Ramsey Reed Rhodes Ridley Rowe Royce Russo Sawyer Schaefer Sexton Shelby Sinclair Slater Spencer
Stafford Sterling Stratton Sutton Talbot Tanaka Thorne Tillman Townsend Tremaine Tucker Vance Vaughn Vela Wade
Walsh Warren Watts Webb Wexler Whitaker Whitmore Winslow Wolfe Yates Yorke Zeller Abbott Ainsley Barlow Beckett
Bishop Bowman Carrow Darrow Ferris Holt Kemp Lund Mayer Novak Pruitt Sato""".split()))
W2 = """Ridge Valley Harbor Point Creek Summit Bay Field Stone Lake River Park Gate Crest Brook Grove Hill Mesa
Pine Oak North West Union Pacific Atlantic Central Metro Coastal Prairie Alpine""".split()
SFX = [
    "Construction Builders Architects Engineering Design-Group Contractors Civil Structural Development Partners Infrastructure Building-Co.".split(),
    "Manufacturing Industries Machine-Works Fabrication Precision Components Engineering Systems Technologies Tooling Robotics Products".split(),
    "Studios Animation Pictures Media Productions Interactive Visual-Effects Games Creative Entertainment Motion Digital".split(),
    "Engineering Consulting Energy Utilities Services Group Solutions Technical Associates Labs Systems Works".split(),
]
SFX = [[s.replace("-", " ") for s in g] for g in SFX]
PFX = """Cascade Pinnacle Summit Keystone Apex Vertex Northstar Bluepeak Ironwood Silverline Clearview Brightpath
Redwood Granite Horizon Lakeshore Evergreen Tidewater Highmark Crestline Frontier Harborview Skyline Trailhead
Westbridge Eastgate Riverbend Stonegate Lighthouse Pathfinder Truenorth Cornerstone Benchmark Landmark Bluewater
Copperline Fieldstone Ridgeway Sunline Waypoint""".split()
PCORE = ["CAD", "Design", "Digital", "BIM", "Engineering", "Tech", "3D", "Systems"]
PSFX = ["Solutions", "Technologies", "Partners", "Group", "Consulting", "Labs"]
TIERS = np.array(["Platinum", "Gold", "Silver", "Authorized"])
SPECS = np.array(["Building & Infrastructure", "Manufacturing", "Media & Entertainment", "Multi-industry"])

NEG = np.array(["Low seat utilization", "Utilization declining", "Active users declining",
                "Low partner engagement", "Renewal soon with low usage", "Still onboarding", "Credit burn below pace"])
POS = np.array(["High seat utilization", "Utilization rising", "Active users growing",
                "Strong partner engagement", "", "", "Credits burning ahead of pace"])
CREDITS_PER_HOUR = LIST_PRICE / (12 * 48) * CREDIT_RATE  # credits per usage hour when a product is billed on credits


def _sig(x):
    return 1.0 / (1.0 + np.exp(-x))


def products_df():
    seat = pd.DataFrame({"PRODUCT_CODE": CODES, "PRODUCT_NAME": [p[1] for p in PRODUCTS],
                         "PRODUCT_FAMILY": FAMILY, "PRICING_MODEL": "Per seat", "PRICE_UNIT": "seat per year",
                         "LIST_PRICE_USD": LIST_PRICE, "CREDITS_PER_USAGE_HOUR": CREDITS_PER_HOUR.round(3),
                         "DESCRIPTION": [p[4] for p in PRODUCTS]})
    credits = pd.DataFrame({"PRODUCT_CODE": ["CREDITS"], "PRODUCT_NAME": ["Truline Cloud Credits"],
                            "PRODUCT_FAMILY": ["Consumption"], "PRICING_MODEL": ["Prepaid credits"],
                            "PRICE_UNIT": ["credit"], "LIST_PRICE_USD": [CREDIT_LIST_PRICE],
                            "CREDITS_PER_USAGE_HOUR": [np.nan],
                            "DESCRIPTION": ["Annual prepaid credit pool usable across any product; overage billed at list"]})
    return pd.concat([seat, credits], ignore_index=True)


def _countries(rng, reg):
    country = np.empty(len(reg), dtype=object)
    legal = np.empty(len(reg), dtype=object)
    for r, lst in enumerate(COUNTRIES):
        m = np.nonzero(reg == r)[0]
        w = np.array([c[1] for c in lst])
        ci = rng.choice(len(lst), len(m), p=w / w.sum())
        country[m] = [lst[i][0] for i in ci]
        legal[m] = [lst[i][2][int(u * len(lst[i][2]))] for i, u in zip(ci, rng.random(len(m)))]
    return country, legal


def build_partners(rng, n):
    nt = [round(n * .05), round(n * .15), round(n * .30)]
    nt.append(n - sum(nt))
    tier = np.repeat(np.arange(4), nt)
    idx = rng.choice(len(PFX) * len(PCORE) * len(PSFX), n, replace=False)
    a, r = np.divmod(idx, len(PCORE) * len(PSFX))
    b, c = np.divmod(r, len(PSFX))
    reg = rng.choice(3, n, p=REGION_SHARE)
    spec = rng.choice(4, n, p=[.40, .28, .07, .25])
    q = rng.normal(np.array([.5, .25, 0, -.2])[tier], .8)
    cap = np.array([30, 12, 5, 1.5])[tier] * rng.lognormal(0, .5, n)
    country, _ = _countries(rng, reg)
    df = pd.DataFrame({
        "PARTNER_ID": [f"P{i + 1:04d}" for i in range(n)],
        "PARTNER_NAME": [f"{PFX[i]} {PCORE[j]} {PSFX[k]}" for i, j, k in zip(a, b, c)],
        "TIER": TIERS[tier], "REGION": np.array(REGIONS)[reg], "HQ_COUNTRY": country,
        "SPECIALIZATION": SPECS[spec], "PARTNER_SINCE_YEAR": rng.integers(1998, 2023, n),
        "SIM_PARTNER_QUALITY": q.round(2)})
    return df, dict(reg=reg, spec=spec, tier=tier, q=q, cap=cap)


def _group_of(ind):
    s = str(ind).lower()
    if any(k in s for k in ("construct", "architect", "civil", "real estate", "building", "plann")):
        return 0
    if any(k in s for k in ("machin", "manufactur", "automotive", "aviation", "aerospace", "industrial",
                            "mechanical", "electrical", "plastic", "shipbuild", "mining", "furniture")):
        return 1
    if any(k in s for k in ("media", "animation", "entertain", "game", "film", "motion picture", "broadcast")):
        return 2
    return 3


def _seg_of(size):
    s = str(size)
    if any(k in s for k in ("10001", "5001", "1001")):
        return 2
    if any(k in s for k in ("501", "201")):
        return 1
    try:
        v = float(s)
        return 2 if v >= 1000 else (1 if v >= 100 else 0)
    except ValueError:
        return 0


def _fake_names(rng, grp):
    n1, n2 = len(W1), len(W2)
    stems = np.empty(len(grp), dtype=object)
    for g in range(4):
        m = np.nonzero(grp == g)[0]
        ns = len(SFX[g])
        a_tot, b_tot = n1 * n2 * ns * 2, n1 * (n1 - 1) * ns
        nb = int(len(m) * .35)
        ia = rng.choice(a_tot, len(m) - nb, replace=False)
        ib = rng.choice(b_tot, nb, replace=False)
        out = []
        for x in ia:  # "Hale Ridge Construction" or "Haleridge Construction"
            style, x = divmod(x, n1 * n2 * ns)
            i, r = divmod(x, n2 * ns)
            j, k = divmod(r, ns)
            out.append(f"{W1[i]} {W2[j]} {SFX[g][k]}" if style == 0 else f"{W1[i]}{W2[j].lower()} {SFX[g][k]}")
        for x in ib:  # "Hale & Morrow Engineering"
            i, r = divmod(x, (n1 - 1) * ns)
            j, k = divmod(r, ns)
            out.append(f"{W1[i]} & {W1[j if j < i else j + 1]} {SFX[g][k]}")
        out = np.array(out, dtype=object)
        rng.shuffle(out)
        stems[m] = out
    return stems


def build_accounts(rng, n, n_real, real_df, P, T, moy, months):
    # ---- real companies (names only are real; everything else is simulated)
    if real_df is not None and n_real > 0 and len(real_df) > 0:
        r = real_df.copy()
        r.columns = [c.upper() for c in r.columns]
        r = r.dropna(subset=["NAME"]).drop_duplicates("NAME").head(min(n_real, n))
        dom = (r["DOMAIN"].astype(str).str.lower().str.strip()
               .str.replace(r"^https?://", "", regex=True).str.replace(r"^www\.", "", regex=True)
               .str.split("/").str[0])
        real = pd.DataFrame({
            "name": r["NAME"].astype(str).str.strip().values, "domain": dom.values,
            "grp": [_group_of(x) for x in r.get("INDUSTRY", pd.Series([""] * len(r)))],
            "industry": r.get("INDUSTRY", pd.Series([""] * len(r))).astype(str).str.title().values,
            "seg": [_seg_of(x) for x in r.get("SIZE_BAND", pd.Series([""] * len(r)))],
            "emp": r.get("SIZE_BAND", pd.Series([""] * len(r))).astype(str).values,
            "country": r.get("COUNTRY", pd.Series([""] * len(r))).astype(str).str.title().values})
        real["reg"] = [COUNTRY_REGION.get(str(c).lower(), 0) for c in real["country"]]
        real["is_real"] = True
    else:
        real = pd.DataFrame(columns=["name", "domain", "grp", "industry", "seg", "emp", "country", "reg", "is_real"])
    nf = n - len(real)
    # ---- fictional companies
    grp = rng.choice(4, nf, p=GROUP_SHARE)
    seg = rng.choice(3, nf, p=SEG_SHARE)
    reg = rng.choice(3, nf, p=REGION_SHARE)
    country, legal = _countries(rng, reg)
    stems = _fake_names(rng, grp)
    names = pd.Series([f"{s} {l}" for s, l in zip(stems, legal)])
    dup = names.duplicated()
    names[dup] = names[dup] + " Holdings"
    slug = pd.Series(stems).str.lower().str.replace(r"[^a-z0-9]", "", regex=True)
    ind = np.empty(nf, dtype=object)
    for g in range(4):
        m = np.nonzero(grp == g)[0]
        ind[m] = rng.choice(INDUSTRIES[g], len(m))
    emp = np.empty(nf, dtype=object)
    for s in range(3):
        m = np.nonzero(seg == s)[0]
        emp[m] = rng.choice(EMP_BANDS[s][0], len(m), p=EMP_BANDS[s][1])
    fake = pd.DataFrame({"name": names.values, "domain": (slug + ".example").values, "grp": grp,
                         "industry": ind, "seg": seg, "emp": emp, "country": country, "reg": reg,
                         "is_real": False})
    a = pd.concat([real, fake], ignore_index=True)
    a = a.iloc[rng.permutation(len(a))].reset_index(drop=True)
    for c in ("grp", "seg", "reg"):
        a[c] = a[c].astype(int)
    seg, grp, reg = a["seg"].to_numpy(), a["grp"].to_numpy(), a["reg"].to_numpy()
    # ---- lifecycle and contract
    is_new = rng.random(n) < .28
    w = MOY_W[moy[1:]]
    start = np.where(is_new, rng.choice(np.arange(1, T), n, p=w / w.sum()), 0)
    back = 1 + np.minimum(rng.exponential(48, n), 190).astype(int)
    tot_m = months[0].year * 12 + months[0].month - 1 + np.where(is_new, start, -back)
    since = np.array([dt.date(int(v // 12), int(v % 12) + 1, 1) for v in tot_m], dtype=object)
    term = np.empty(n, int)
    for s in range(3):
        m = np.nonzero(seg == s)[0]
        term[m] = rng.choice(3, len(m), p=TERM_P[s])
    rmoy = np.where(is_new, moy[start], rng.choice(12, n, p=MOY_W))
    yr0 = np.array([m.year for m in months])[start]
    phase = np.where(is_new, (-yr0) % 3, rng.integers(0, 3, n))
    # ---- partner assignment (same region, specialization + tier fit)
    p_idx = np.empty(n, int)
    for r in range(3):
        pr = np.nonzero(P["reg"] == r)[0]
        for g in range(4):
            sw = (np.where(P["spec"][pr] == g, 3.0, np.where(P["spec"][pr] == 3, 1.5, .3)) if g < 3
                  else np.where(P["spec"][pr] == 3, 2.0, .8))
            for s in range(3):
                m = np.nonzero((reg == r) & (grp == g) & (seg == s))[0]
                if len(m) == 0:
                    continue
                tw = [np.ones(4), np.array([1.5, 1.3, 1, .8]), np.array([3, 2, 1, .6])][s][P["tier"][pr]]
                wt = P["cap"][pr] * sw * tw
                p_idx[m] = rng.choice(pr, len(m), p=wt / wt.sum())
    q = P["q"][p_idx]

    def traj():
        lg = np.log(TRAJ_P) + np.c_[.5 * q, 0 * q, -.5 * q] + rng.gumbel(size=(n, 3))
        return lg.argmax(1)

    t1, t2 = traj(), traj()
    switch = np.where(rng.random(n) < .35, rng.integers(6, T, n), T + 1)
    surprise = np.where(rng.random(n) < .012, rng.integers(0, T, n), -1)
    mu, sd, lo, hi = zip(*SEATS_LOGN)
    emp_s = a["emp"].astype(str)
    big = np.where(emp_s.str.contains("10001"), 2.5, np.where(emp_s.str.contains("5001-"), 1.5, 1.0))
    seats = np.clip(np.round(rng.lognormal(np.array(mu)[seg], np.array(sd)[seg]) * big),
                    np.array(lo)[seg], np.array(hi)[seg] * big).astype(int)
    native = is_new & (start >= T // 2) & (rng.random(n) < NATIVE_SHARE)
    term = np.where(native, 1, term)
    a = a.assign(native=native, ACCOUNT_ID=[f"A{i + 1:06d}" for i in range(n)], start_m=start, since=since,
                 term=term, renew_moy=rmoy, phase=phase, p_idx=p_idx, traj1=t1, traj2=t2,
                 switch_m=switch, surprise_m=surprise, seats=seats)
    return a


def _sim_chunk(c, T, moy, yr, mdates, part_q, rng):
    n = len(c)
    seg, grp, reg = c["seg"].to_numpy(), c["grp"].to_numpy(), c["reg"].to_numpy()
    start, term = c["start_m"].to_numpy(), c["term"].to_numpy().copy()
    rmoy, phase, native = c["renew_moy"].to_numpy(), c["phase"].to_numpy(), c["native"].to_numpy()
    q = part_q[c["p_idx"].to_numpy()]
    new_logo = start > 0
    # ---- product slots: Gumbel top-k by industry/segment propensity, plus one cross-sell candidate
    k = np.where(seg == 0, 1 + (rng.random(n) < .25),
                 np.where(seg == 1, 1 + rng.binomial(2, .5, n), 2 + rng.binomial(3, .5, n)))
    with np.errstate(divide="ignore"):
        g = np.log(W_GROUP[grp] * SEG_MULT[seg]) + rng.gumbel(size=(n, NPROD))
    order = np.argsort(-g, axis=1)
    gs = np.take_along_axis(g, order, axis=1)
    k = np.minimum(k, np.isfinite(gs).sum(1))
    acct, prod, rank = [], [], []
    for r in range(int(k.max())):
        m = np.nonzero(k > r)[0]
        acct.append(m), prod.append(order[m, r]), rank.append(np.full(len(m), r))
    m = np.nonzero((rng.random(n) < .45) & np.isfinite(gs[np.arange(n), k]))[0]
    acct.append(m), prod.append(order[m, k[m]]), rank.append(np.full(len(m), 99))
    s_a, s_p, s_r = np.concatenate(acct), np.concatenate(prod), np.concatenate(rank)
    S, xs = len(s_a), s_r == 99
    s_start = start[s_a].copy()
    lo = np.maximum(start[s_a[xs]] + 2, 1)
    s_start[xs] = lo + (rng.random(xs.sum()) * np.maximum(T - lo, 1)).astype(int)
    tot = c["seats"].to_numpy()[s_a]
    frac = np.where(s_r == 0, 1.0, np.where(xs, rng.uniform(.05, .25, S), rng.uniform(.2, .7, S)))
    seats = np.maximum(1, np.round(tot * frac)).astype(np.int64)
    disc = rng.uniform(DISCOUNT[seg[s_a], 0], DISCOUNT[seg[s_a], 1])
    price = LIST_PRICE[s_p] * (1 - disc) * np.where(term[s_a] == 0, 1.2, 1.0) * rng.lognormal(0, .03, S)
    pf = rng.uniform(.85, 1.08, S) * np.where(s_p == PI["COLLAB"], .8, 1.0)
    active = (~xs) & (start[s_a] == 0)
    arr_prev = np.where(active, seats * price, 0.0)
    crp = CREDITS_PER_HOUR[s_p]
    # ---- slot billing state (seat vs credits) and account consumption contract state
    cons, vseats, s_cm = np.zeros(S, bool), seats.astype(float), np.full(S, -1)
    a_cons, commit, used, over_ytd = np.zeros(n, bool), np.zeros(n), np.zeros(n), np.zeros(n)
    cstart, cons_since, mig_m = np.full(n, -1), np.full(n, -1), np.full(n, -1)
    cprice = CREDIT_LIST_PRICE * (1 - rng.uniform(DISCOUNT[seg, 0], DISCOUNT[seg, 1]))
    cons_prev = np.zeros(n)
    # ---- demand-driven dynamics: each slot has latent user demand; seats (or credits) follow demand
    mu1, mu2 = TRAJ_MU[c["traj1"].to_numpy()], TRAJ_MU[c["traj2"].to_numpy()]
    sw, surp = c["switch_m"].to_numpy(), c["surprise_m"].to_numpy()
    u0 = np.clip(rng.normal(.74, .13, n) + .04 * q, .3, 1.05)
    d = seats * u0[s_a] * rng.normal(1, .05, S)
    churned, churn_m = np.zeros(n, bool), np.full(n, -1)
    seg_adj = SEG_CHURN_ADJ[seg]
    lam = TOUCH_RATE[seg] * np.exp(.45 * q)
    p_true_up = np.clip(.30 + .10 * q, .10, .60)
    HS, HA, HH, HR, HP, HC = (np.zeros((T, S)) for _ in range(6))
    HK = np.zeros((T, S), bool)
    AV, KC = np.zeros((T, n), bool), np.zeros((T, n), bool)
    A = {key: np.zeros((T, n)) for key in (
        "st", "new", "exp", "con", "churn", "mout", "min", "end", "seat_arr", "cons_arr", "seats", "au",
        "au_seat", "touch", "mtr", "ren", "dem", "fill", "eq", "credits", "used", "over", "expired",
        "topup", "commit", "cstart")}
    for t in range(T):
        lo3 = max(0, t - 3)
        if t == 0:
            s_u3, a_u3 = np.clip(d / np.maximum(seats, 1), 0, 1), np.full(n, .74)
        else:
            s_u3 = HA[lo3:t].sum(0) / np.maximum(HS[lo3:t].sum(0), 1)
            a_u3 = A["fill"][lo3:t].sum(0) / np.maximum(A["eq"][lo3:t].sum(0), 1)
        utrend = (a_u3 - A["fill"][max(0, t - 6):t - 3].sum(0) / np.maximum(A["eq"][max(0, t - 6):t - 3].sum(0), 1)
                  if t >= 6 else np.zeros(n))
        dtrend = (np.log(np.maximum(A["dem"][t - 1], .1) / np.maximum(A["dem"][t - 7], .1)) if t >= 7 else np.zeros(n))
        onboard = new_logo & (t - start >= 0) & (t - start < 6)
        d = d * np.exp(np.where(t >= sw, mu2, mu1)[s_a] + .05 * onboard[s_a] + rng.normal(0, .03, S))
        alive = (start <= t) & ~churned
        act = (~xs) & (start[s_a] == t) & (start[s_a] > 0)
        xa = xs & (s_start == t) & alive[s_a] & (a_u3[s_a] > .65) & (rng.random(S) < .6)
        d = np.where(act | xa, seats * rng.uniform(.4, .7, S), d)
        # consumption-native new logos and cross-sells into credit accounts start on credits
        nat = act & native[s_a]
        xc = xa & a_cons[s_a]
        to_c = nat | xc
        cons |= to_c
        vseats = np.where(to_c, seats * .8, vseats)
        plan_cr = np.bincount(s_a, np.where(to_c, seats * .6 * LIST_PRICE[s_p] * CREDIT_RATE * rng.uniform(.9, 1.05, S), 0), n)
        nl = native & (start == t)
        a_cons |= nl
        cstart[nl], cons_since[nl], used[nl], over_ytd[nl] = t, t, 0, 0
        commit = commit + plan_cr
        active = active | act | xa
        # renewals: churn decision for the whole account
        ren = alive & (t > start) & ((term == 0) | ((rmoy == moy[t]) & ((term == 1) | ((yr[t] + phase) % 3 == 0))))
        x = CHURN_B0 + seg_adj + np.where(term == 0, -2.2, 0.0) - 6.0 * (a_u3 - .62) - 5.0 * utrend - 3.0 * dtrend - .3 * q
        ch = ren & ((rng.random(n) < _sig(x)) | ((surp >= 0) & (t >= surp)))
        churned |= ch
        churn_m[ch] = t
        active &= ~ch[s_a]
        ok = ren & ~ch
        # credit contracts renew annually: unused credits expire; new commit sized on trailing usage
        rc = ok & a_cons & (t > cstart)
        expired = np.where(rc, np.maximum(0, commit - used), 0)
        trail = A["credits"][max(0, t - 12):t].sum(0) * 12 / np.clip(t - cons_since, 1, 12)
        commit = np.where(rc, trail * rng.uniform(.98, 1.12, n), commit)
        used, over_ytd, cstart = np.where(rc, 0, used), np.where(rc, 0, over_ytd), np.where(rc, t, cstart)
        vseats = np.where(cons & rc[s_a], np.maximum(1, d * 1.15), vseats)
        # migration: at renewal some seat accounts move part or all of their products onto credits
        mig = ok & ~a_cons & (term > 0) & (rng.random(n) < MIG_BASE[seg] * (.3 + .7 * t / (T - 1)))
        conv = mig[s_a] & active & ~cons & (t > s_start) & ((s_r == 0) | (rng.random(S) < .6))
        mig_out_s = np.where(conv, arr_prev, 0)
        mig_cr = np.bincount(s_a, np.where(conv, d * LIST_PRICE[s_p] * CREDIT_RATE * rng.uniform(.88, 1.0, S), 0), n)
        a_cons |= mig
        commit = np.where(mig, mig_cr, commit)
        cstart[mig], cons_since[mig], mig_m[mig], used[mig], over_ytd[mig], term[mig] = t, t, t, 0, 0, 1
        cons |= conv
        s_cm[conv] = t
        vseats = np.where(conv, np.maximum(1, d * 1.15), vseats)
        mig_in = np.where(mig, mig_cr * cprice, 0)
        # seat renewals: drop unused secondary products, right-size seats, price uplift
        rs = ren[s_a] & ~ch[s_a] & active & ~cons & (t > s_start)
        drop = rs & (s_r > 0) & (((s_u3 < .35) & (rng.random(S) < .5)) | (rng.random(S) < .02))
        active &= ~drop
        right = np.maximum(1, np.ceil(d * rng.uniform(1.05, 1.2, S)))
        low = rs & ~drop & (s_u3 < .65) & (rng.random(S) < np.where(term[s_a] == 0, .3, .7)) & (right < seats)
        seats = np.where(low, right, seats).astype(np.int64)
        price = np.where(rs & ~drop & (term[s_a] > 0), price * 1.03, price)
        # mid-term: seat true-ups, and credit top-ups when burning well ahead of pace
        ex = active & ~cons & ~act & ~xa & (d > seats * .92) & (rng.random(S) < p_true_up[s_a])
        seats = np.where(ex, np.maximum(seats, right), seats).astype(np.int64)
        el_prev = t - cstart
        pace_prev = used / np.maximum(commit * np.maximum(el_prev, 1) / 12, 1)
        top = a_cons & ~churned & (el_prev >= 3) & (el_prev <= 9) & (pace_prev > 1.15) & (rng.random(n) < .5 * p_true_up)
        topx = np.where(top, commit * rng.uniform(.25, .5, n), 0)
        commit = commit + topx
        # usage: seat products capped by seats; credit products scale with actual demand
        season = SEASON[reg[s_a], moy[t]]
        fill = np.clip(d / np.maximum(seats, 1), .02, 1.0)
        util = np.clip(fill * season * rng.normal(1, .04, S), .02, 1.0)
        au = np.where(active, np.where(cons, rng.poisson(np.maximum(d, 0) * season * .95), rng.binomial(seats, util)), 0)
        hrs = au * rng.lognormal(np.log(48), .25, S) * (.85 + .15 * np.where(cons, 1.0, fill)) * season
        cred = np.where(active & cons, hrs * crp, 0.0)
        seat_arr = np.where(active & ~cons, seats * price, 0.0)
        acr = np.bincount(s_a, cred, n)
        used = used + acr
        over_t = np.maximum(0, np.maximum(0, used - commit) - over_ytd)
        over_ytd = over_ytd + over_t
        cons_arr = np.where(a_cons & ~churned, commit * cprice, 0.0)
        HS[t], HA[t], HH[t], HR[t], HP[t], HC[t] = np.where(active & ~cons, seats, 0), au, hrs, seat_arr, arr_prev, cred
        HK[t] = active & cons
        # account ARR bridge: START + NEW + EXP - CON - CHURN - MIGRATED_OUT + MIGRATED_IN = END
        seat_st, seat_en = np.bincount(s_a, arr_prev, n), np.bincount(s_a, seat_arr, n)
        st, en = seat_st + cons_prev, seat_en + cons_arr
        dd = np.where(conv, 0, seat_arr - arr_prev)
        dc = cons_arr - cons_prev - mig_in
        pos = np.bincount(s_a, np.maximum(dd, 0), n) + np.maximum(dc, 0)
        neg = np.bincount(s_a, np.maximum(-dd, 0), n) + np.maximum(-dc, 0)
        is_new = (start == t) & (start > 0)
        keep = ~is_new & ~ch
        A["st"][t], A["end"][t] = st, en
        A["new"][t], A["churn"][t] = np.where(is_new, en, 0), np.where(ch, st, 0)
        A["exp"][t], A["con"][t] = np.where(keep, pos, 0), np.where(keep, neg, 0)
        A["mout"][t], A["min"][t] = np.where(keep, np.bincount(s_a, mig_out_s, n), 0), np.where(keep, mig_in, 0)
        A["seat_arr"][t], A["cons_arr"][t] = seat_en, cons_arr
        AV[t] = (start <= t) & ((churn_m == -1) | (churn_m == t))
        KC[t] = AV[t] & (cons_arr > 0)
        A["seats"][t], A["au"][t] = np.bincount(s_a, HS[t], n), np.bincount(s_a, au, n)
        A["au_seat"][t] = np.bincount(s_a, np.where(cons, 0, au), n)
        A["dem"][t] = np.bincount(s_a, np.where(active, d, 0), n)
        cap = np.where(cons, vseats, seats)
        A["eq"][t] = np.bincount(s_a, np.where(active, cap, 0), n)
        A["fill"][t] = np.bincount(s_a, np.where(active, np.minimum(d, cap), 0), n)  # season-free usage
        A["credits"][t], A["used"][t], A["over"][t] = acr, used, over_t
        A["expired"][t], A["topup"][t], A["commit"][t], A["cstart"][t] = expired, topx, np.where(KC[t], commit, 0), cstart
        base = (rmoy - moy[t]) % 12
        add = (-(yr[t] + (moy[t] + base) // 12 + phase)) % 3
        A["mtr"][t] = np.where(term == 0, 0, np.where(term == 2, base + 12 * add, base))
        A["ren"][t] = ren
        A["touch"][t] = rng.poisson(lam * np.where((A["mtr"][t] <= 2) & (term > 0), 1.6, 1.0)) * AV[t]
        arr_prev, cons_prev = seat_arr, cons_arr
    # ---- illustrative health model (pre-computed score, reason codes, churn probability)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        U = np.where(AV & (A["eq"] > 0), A["fill"] / np.maximum(A["eq"], 1), np.nan)  # season-adjusted usage
        u3 = np.vstack([np.nanmean(U[max(0, t - 2):t + 1], axis=0) for t in range(T)])
    u3f = np.where(np.isnan(u3), .5, u3)

    def lag(x, k=3, fill=np.nan):
        return np.vstack([np.full((k, x.shape[1]), fill), x[:-k]])

    dtr = np.nan_to_num(u3 - lag(u3))
    au_l = lag(A["fill"])
    au_tr = np.clip(np.where(au_l > 0, A["fill"] / np.where(au_l > 0, au_l, 1) - 1, 0), -.6, .6)
    tch3 = A["touch"] + np.nan_to_num(lag(A["touch"], 1)) + np.nan_to_num(lag(A["touch"], 2))
    tt = np.arange(T)[:, None]
    onb = new_logo & (tt - start < 6)
    el = np.where(KC, tt - A["cstart"] + 1, 0)
    pace = np.where(KC, A["used"] / np.maximum(A["commit"] * np.maximum(el, 1) / 12, 1), np.nan)
    share = A["cons_arr"] / np.maximum(A["seat_arr"] + A["cons_arr"], 1)
    C = np.stack([np.where(onb, 3.0, 6.0) * (u3f - .80), 8.0 * dtr, 2.5 * au_tr,
                  .3 * np.clip(tch3 - 3 * lam, -2, 2),
                  np.where((A["mtr"] <= 3) & (term > 0) & (u3f < .65), -.4, 0.0),
                  np.where(new_logo & (tt - start < 4), -.3, 0.0),
                  np.where(KC & (el >= 3), 1.5 * np.clip(np.nan_to_num(pace) - 1, -.5, .5) * share, 0.0)], axis=-1)
    e = np.zeros((T, n))
    for t in range(T):
        e[t] = (.6 * e[t - 1] if t else 0) + rng.normal(0, .25, n)
    score = np.where(AV, np.clip(np.round(100 * _sig(HEALTH_B0 + C.sum(-1) + e)), 1, 99), np.nan)
    dscore = score - lag(score)
    # ---- ACCOUNT_MONTHLY
    ids = c["ACCOUNT_ID"].to_numpy()
    pid = np.array([f"P{i + 1:04d}" for i in c["p_idx"]])
    ti, ai = np.nonzero(AV)
    sc = score[ti, ai]
    Cv = C[ti, ai]
    r90 = ((term[ai] == 0) | ((A["mtr"][ti, ai] >= 1) & (A["mtr"][ti, ai] <= 3))).astype(float)
    neg_o, pos_o = np.argsort(Cv, axis=1)[:, :2], np.argsort(-Cv, axis=1)[:, :2]
    healthy, seatless = sc >= 70, A["seats"][ti, ai] == 0
    drv = []
    for j in range(2):
        nv = np.take_along_axis(Cv, neg_o[:, j:j + 1], 1)[:, 0]
        pv = np.take_along_axis(Cv, pos_o[:, j:j + 1], 1)[:, 0]
        lab = np.where(healthy, np.where(pv > .05, POS[pos_o[:, j]], ""), np.where(nv < -.05, NEG[neg_o[:, j]], ""))
        lab = np.where(seatless & (lab == "Low seat utilization"), "Low active usage", lab)
        drv.append(np.where(seatless & (lab == "High seat utilization"), "High active usage", lab))
    sa, ca = A["seat_arr"][ti, ai], A["cons_arr"][ti, ai]
    billing = np.select([(sa > 0) & (ca > 0), ca > 0, sa > 0], ["Hybrid", "Consumption", "Seats"], "None")
    band = np.select([sc >= 70, sc >= 50, sc >= 30], ["Healthy", "Watch", "At Risk"], "Critical")
    se = A["seats"][ti, ai]
    R = lambda key: A[key][ti, ai].round(2)  # noqa: E731
    am = pd.DataFrame({
        "MONTH": mdates[ti], "ACCOUNT_ID": ids[ai], "PARTNER_ID": pid[ai], "BILLING_MODEL": billing,
        "START_ARR": R("st"), "NEW_ARR": R("new"), "EXPANSION_ARR": R("exp"), "CONTRACTION_ARR": R("con"),
        "CHURN_ARR": R("churn"), "MIGRATED_OUT_ARR": R("mout"), "MIGRATED_IN_ARR": R("min"), "END_ARR": R("end"),
        "SEAT_ARR": R("seat_arr"), "CONSUMPTION_ARR": R("cons_arr"),
        "OVERAGE_REVENUE": (A["over"][ti, ai] * CREDIT_LIST_PRICE).round(2),
        "SEATS": se.astype(int), "ACTIVE_USERS": A["au"][ti, ai].astype(int),
        "SEAT_UTILIZATION": np.where(se > 0, np.round(A["au_seat"][ti, ai] / np.maximum(se, 1), 3), np.nan),
        "CREDITS_CONSUMED": A["credits"][ti, ai].round(0),
        "PARTNER_TOUCHES": A["touch"][ti, ai].astype(int), "MONTHS_TO_RENEWAL": A["mtr"][ti, ai].astype(int),
        "IS_RENEWAL_MONTH": A["ren"][ti, ai].astype(bool),
        "HEALTH_SCORE": sc.astype(int), "HEALTH_SCORE_CHANGE_3M": dscore[ti, ai], "RISK_BAND": band,
        "CHURN_PROB_90D": np.round(_sig(PROB_A - PROB_B * sc) * np.where(r90 > 0, 1.0, PROB_OFF_CYCLE), 3),
        "DRIVER_1": drv[0], "DRIVER_2": drv[1], "MODEL_VERSION": "health-v3.0 (illustrative)"})
    # ---- CONSUMPTION_MONTHLY (credit contract tracking for accounts on credits)
    tk, ak = np.nonzero(KC)
    pk = pace[tk, ak]
    cm = pd.DataFrame({
        "MONTH": mdates[tk], "ACCOUNT_ID": ids[ak], "PARTNER_ID": pid[ak],
        "CONTRACT_MONTH": el[tk, ak].astype(int), "ANNUAL_COMMIT_CREDITS": A["commit"][tk, ak].round(0),
        "PRICE_PER_CREDIT_USD": cprice[ak].round(4), "COMMIT_ARR": A["cons_arr"][tk, ak].round(2),
        "TOP_UP_CREDITS": A["topup"][tk, ak].round(0), "CREDITS_CONSUMED": A["credits"][tk, ak].round(0),
        "CREDITS_USED_CONTRACT_YTD": A["used"][tk, ak].round(0),
        "CREDITS_REMAINING": np.maximum(0, A["commit"][tk, ak] - A["used"][tk, ak]).round(0),
        "BURN_PACE": pk.round(3),
        "BURN_STATUS": np.select([el[tk, ak] <= 2, pk > 1.15, pk < .80],
                                 ["Early in contract", "Ahead of pace", "Below pace"], "On pace"),
        "OVERAGE_CREDITS": A["over"][tk, ak].round(0),
        "OVERAGE_REVENUE": (A["over"][tk, ak] * CREDIT_LIST_PRICE).round(2),
        "EXPIRED_CREDITS": A["expired"][tk, ak].round(0)})
    # ---- SUBSCRIPTION_MONTHLY: product rows (usage, seat ARR, credits consumed) + one CREDITS row per account
    tj, sj = np.nonzero((HR > 0) | (HP > 0) | HK)
    cur, prv = HR[tj, sj], HP[tj, sj]
    migrated = s_cm[sj] == tj
    sub_id = np.char.add(np.char.add(ids[s_a].astype(str), "-"), np.array(CODES)[s_p])
    hk = HK[tj, sj]
    sm_p = pd.DataFrame({
        "MONTH": mdates[tj], "SUBSCRIPTION_ID": sub_id[sj], "ACCOUNT_ID": ids[s_a[sj]],
        "PRODUCT_CODE": np.array(CODES)[s_p[sj]], "BILLING_MODEL": np.where(hk, "Consumption", "Seat"),
        "SEATS": HS[tj, sj].astype(int), "ACTIVE_USERS": HA[tj, sj].astype(int),
        "SEAT_UTILIZATION": np.where(hk, np.nan, np.round(HA[tj, sj] / np.maximum(HS[tj, sj], 1), 3)),
        "USAGE_HOURS": HH[tj, sj].round(1), "CREDITS_CONSUMED": HC[tj, sj].round(0), "ARR": cur.round(2),
        "NEW_ARR": np.where((prv == 0) & (cur > 0), cur, 0).round(2),
        "EXPANSION_ARR": np.where((prv > 0) & (cur > prv), cur - prv, 0).round(2),
        "CONTRACTION_ARR": np.where((cur > 0) & (cur < prv), prv - cur, 0).round(2),
        "CHURN_ARR": np.where((prv > 0) & (cur == 0) & ~migrated, prv, 0).round(2),
        "MIGRATED_OUT_ARR": np.where(migrated, prv, 0).round(2), "MIGRATED_IN_ARR": 0.0})
    ca_all, ca_prev = A["cons_arr"], lag(A["cons_arr"], 1, 0.0)
    tc, ac = np.nonzero((ca_all > 0) | (ca_prev > 0))
    cc, cp, mi = ca_all[tc, ac], ca_prev[tc, ac], A["min"][tc, ac]
    dcn = cc - cp - mi
    newc = (cp == 0) & (cc > 0) & (mi == 0)
    sm_c = pd.DataFrame({
        "MONTH": mdates[tc], "SUBSCRIPTION_ID": np.char.add(ids[ac].astype(str), "-CREDITS"), "ACCOUNT_ID": ids[ac],
        "PRODUCT_CODE": "CREDITS", "BILLING_MODEL": "Consumption", "SEATS": 0, "ACTIVE_USERS": 0,
        "SEAT_UTILIZATION": np.nan, "USAGE_HOURS": 0.0, "CREDITS_CONSUMED": 0.0, "ARR": cc.round(2),
        "NEW_ARR": np.where(newc, cc, 0).round(2),
        "EXPANSION_ARR": np.where(~newc & (cc > 0), np.maximum(dcn, 0), 0).round(2),
        "CONTRACTION_ARR": np.where(cc > 0, np.maximum(-dcn, 0), 0).round(2),
        "CHURN_ARR": np.where((cp > 0) & (cc == 0), cp, 0).round(2),
        "MIGRATED_OUT_ARR": 0.0, "MIGRATED_IN_ARR": mi.round(2)})
    sm = pd.concat([sm_p, sm_c], ignore_index=True)
    # ---- SUBSCRIPTIONS (current state)
    ever = ((HR > 0) | (HP > 0) | HK).any(0)
    first_on = np.where(((HR > 0) | HK).any(0), ((HR > 0) | HK).argmax(0), -1)
    hk_prev = np.vstack([np.zeros((1, S), bool), HK[:-1]])
    off = ((HP > 0) & (HR == 0) & ~HK) | (hk_prev & ~HK)
    end_m = np.where(off.any(0), off.argmax(0), -1)
    pre = (HP[0] > 0) & ~xs
    since = c["since"].to_numpy()
    status = np.where(HK[-1], "Active (credits)", np.where(HR[-1] > 0, "Active", "Cancelled"))
    subs_p = pd.DataFrame({
        "SUBSCRIPTION_ID": sub_id, "ACCOUNT_ID": ids[s_a], "PRODUCT_CODE": np.array(CODES)[s_p],
        "BILLING_MODEL": np.where(cons, "Consumption", "Seat"), "CONTRACT_TERM": np.array(TERMS)[term[s_a]],
        "START_MONTH": np.where(pre, since[s_a], mdates[np.maximum(first_on, 0)]),
        "END_MONTH": np.where(end_m >= 0, mdates[np.maximum(end_m, 0)], None),
        "CONVERTED_TO_CREDITS_MONTH": np.where(s_cm >= 0, mdates[np.maximum(s_cm, 0)], None),
        "STATUS": status, "CURRENT_SEATS": HS[-1].astype(int), "UNIT_PRICE_USD": price.round(2),
        "ANNUAL_COMMIT_CREDITS": np.nan, "CURRENT_ARR": HR[-1].round(2)})[ever]
    hc = cons_since >= 0
    subs_c = pd.DataFrame({
        "SUBSCRIPTION_ID": np.char.add(ids[hc].astype(str), "-CREDITS"), "ACCOUNT_ID": ids[hc], "PRODUCT_CODE": "CREDITS",
        "BILLING_MODEL": "Consumption", "CONTRACT_TERM": "Annual", "START_MONTH": mdates[cons_since[hc]],
        "END_MONTH": np.where(churned[hc], mdates[np.maximum(churn_m[hc], 0)], None),
        "CONVERTED_TO_CREDITS_MONTH": None,
        "STATUS": np.where(churned[hc], "Cancelled", "Active"), "CURRENT_SEATS": 0,
        "UNIT_PRICE_USD": cprice[hc].round(4), "ANNUAL_COMMIT_CREDITS": np.where(churned[hc], 0, commit[hc]).round(0),
        "CURRENT_ARR": A["cons_arr"][-1][hc].round(2)})
    subs = pd.concat([subs_p, subs_c], ignore_index=True)
    # ---- account summary
    last_t = T - 1 - np.argmax(AV[::-1], axis=0)
    ref_t = np.where(churned, np.maximum(last_t - 1, start), last_t)
    sa_r, ca_r = A["seat_arr"][ref_t, np.arange(n)], A["cons_arr"][ref_t, np.arange(n)]
    traj_now = np.where(sw < T, c["traj2"].to_numpy(), c["traj1"].to_numpy())
    summ = pd.DataFrame({
        "ACCOUNT_ID": ids, "STATUS": np.where(churned, "Churned", "Active"),
        "CHURN_MONTH": np.where(churned, mdates[np.maximum(churn_m, 0)], None),
        "BILLING_MODEL": np.select([(sa_r > 0) & (ca_r > 0), ca_r > 0], ["Hybrid", "Consumption"], "Seats"),
        "CONSUMPTION_NATIVE": native.astype(bool),
        "CONVERTED_TO_CREDITS_MONTH": np.where(mig_m >= 0, mdates[np.maximum(mig_m, 0)], None),
        "CURRENT_ARR": A["end"][-1].round(2), "CURRENT_SEAT_ARR": A["seat_arr"][-1].round(2),
        "CURRENT_CONSUMPTION_ARR": A["cons_arr"][-1].round(2),
        "CURRENT_HEALTH_SCORE": score[last_t, np.arange(n)],
        "SIM_TRAJECTORY": np.where(surp >= 0, "surprise churn", TRAJ[traj_now])})
    return subs, sm, am, cm, summ


# ---- coverage: Truline Partner Account Managers (PAMs) and partner sales reps (labels only; no effect on outcomes)
COV_DEDICATED, COV_SHARED, COV_SHARED_RATIO = 50, 250, 20
REP_CAPACITY = np.array([250, 40, 10])  # active accounts per partner rep: SMB, Mid-Market, Enterprise
REP_TITLE = np.array(["Inside Sales Representative", "Account Executive", "Strategic Account Manager"])
FIRST = """Aaron Abby Adrian Aisha Alex Amara Ana Andre Angela Arjun Ben Bianca Carlos Chloe Daniel Diana Elena Emeka
Erik Fatima Felix Grace Hannah Hiro Ines Isaac Jada Jamal Jin Julia Kai Kenji Lara Leo Lucia Maya Mei Mohammed Nadia
Noah Olivia Omar Priya Rafael Ravi Rosa Ryan Sara Sofia Tariq Tomas Uma Victor Wei Yara Yusuf Zoe Liam Emma Lena""".split()


def _slug(x):
    return "".join(ch for ch in str(x).lower() if ch.isalnum())


def build_coverage(rng, accounts, partners):
    """PAM coverage for partners (ranked by active ARR) and partner reps owning customer accounts."""
    act = accounts.STATUS == "Active"
    p = partners.copy()
    p["CURRENT_MANAGED_ARR"] = p.PARTNER_ID.map(accounts[act].groupby("PARTNER_ID").CURRENT_ARR.sum()).fillna(0).round(2)
    p["PARTNER_ARR_RANK"] = p.CURRENT_MANAGED_ARR.rank(ascending=False, method="first").astype(int)
    p["COVERAGE_MODEL"] = np.select([p.PARTNER_ARR_RANK <= COV_DEDICATED, p.PARTNER_ARR_RANK <= COV_DEDICATED + COV_SHARED],
                                    ["Dedicated PAM", "Shared PAM"], "Long tail (no PAM)")
    # ---- partner rep teams: generalists at small partners, segment specialists at larger ones
    a = accounts[["ACCOUNT_ID", "PARTNER_ID", "SEGMENT", "CURRENT_ARR"]].copy()
    a["seg"] = a.SEGMENT.map({s: i for i, s in enumerate(SEGS)}).astype(int)
    a["active"] = act.to_numpy()
    cnt_act = a[a.active].groupby(["PARTNER_ID", "seg"]).size().unstack(fill_value=0).reindex(
        index=p.PARTNER_ID, columns=[0, 1, 2], fill_value=0)
    cnt_all = a.groupby(["PARTNER_ID", "seg"]).size().unstack(fill_value=0).reindex(
        index=p.PARTNER_ID, columns=[0, 1, 2], fill_value=0)
    units = (cnt_act / REP_CAPACITY).sum(1)
    general = units <= 1.5
    teams = [pd.DataFrame({"PARTNER_ID": units.index[general], "seg": -1,
                           "n": np.maximum(1, np.ceil(units[general])).astype(int)})]
    for sg in range(3):
        m = ~general & (cnt_all[sg] > 0)
        teams.append(pd.DataFrame({"PARTNER_ID": units.index[m], "seg": sg,
                                   "n": np.maximum(1, np.ceil(cnt_act[sg][m] / REP_CAPACITY[sg])).astype(int)}))
    teams = pd.concat(teams, ignore_index=True)
    reps = teams.loc[teams.index.repeat(teams.n)].reset_index(drop=True)
    reps["j"] = reps.groupby(["PARTNER_ID", "seg"]).cumcount()
    # ---- unique fictional people for PAMs and reps
    sh = p[p.COVERAGE_MODEL == "Shared PAM"]
    n_sh = {r: int(np.ceil((sh.REGION == r).sum() / COV_SHARED_RATIO)) for r in REGIONS}
    n_pam = int((p.COVERAGE_MODEL == "Dedicated PAM").sum()) + sum(n_sh.values())
    idx = rng.choice(len(FIRST) * len(W1), n_pam + len(reps), replace=False)
    f, l = np.divmod(idx, len(W1))
    people = np.array([f"{FIRST[i]} {W1[j]}" for i, j in zip(f, l)], dtype=object)
    # ---- PAMs: one per dedicated partner; shared PAMs cover ~20 partners each within a region (balanced by ARR)
    p["PAM_ID"] = None
    pam_rows, k = [], 0
    for _, row in p[p.COVERAGE_MODEL == "Dedicated PAM"].sort_values("PARTNER_ARR_RANK").iterrows():
        pam_rows.append(("Dedicated", row.REGION))
        p.loc[p.PARTNER_ID == row.PARTNER_ID, "PAM_ID"] = f"TP{k + 1:03d}"
        k += 1
    for r in REGIONS:
        g = sh[sh.REGION == r].sort_values("CURRENT_MANAGED_ARR", ascending=False)
        if not len(g):
            continue
        n, pos = n_sh[r], np.arange(len(g))
        kk = pos % (2 * n)
        slot = np.where(kk < n, kk, 2 * n - 1 - kk)
        p.loc[g.index, "PAM_ID"] = [f"TP{k + s + 1:03d}" for s in slot]
        pam_rows += [("Shared", r)] * n
        k += n
    pams = pd.DataFrame(pam_rows, columns=["COVERAGE_MODEL", "REGION"])
    pams.insert(0, "PAM_ID", [f"TP{i + 1:03d}" for i in range(len(pams))])
    pams.insert(1, "PAM_NAME", people[:len(pams)])
    pams["EMAIL"] = [n.lower().replace(" ", ".") + "@truline.example" for n in pams.PAM_NAME]
    cov = p.dropna(subset=["PAM_ID"]).groupby("PAM_ID").agg(PARTNERS_COVERED=("PARTNER_ID", "size"),
                                                         CURRENT_MANAGED_ARR=("CURRENT_MANAGED_ARR", "sum"))
    pams = pams.merge(cov, left_on="PAM_ID", right_index=True, how="left")
    # ---- reps and account ownership (snake-draft by ARR so books are balanced)
    reps["REP_ID"] = [f"R{i + 1:05d}" for i in range(len(reps))]
    reps["REP_NAME"] = people[len(pams):len(pams) + len(reps)]
    pinfo = p.set_index("PARTNER_ID")
    reps["REGION"] = pinfo.REGION.reindex(reps.PARTNER_ID).to_numpy()
    reps["TITLE"] = np.where(reps.seg < 0, "Account Manager", REP_TITLE[reps.seg.clip(0)])
    reps["SEGMENT_FOCUS"] = np.where(reps.seg < 0, "All segments", np.array(SEGS)[reps.seg.clip(0)])
    dom = pinfo.PARTNER_NAME.reindex(reps.PARTNER_ID).map(_slug).to_numpy()
    reps["EMAIL"] = [n.lower().replace(" ", ".") + "@" + d + ".example" for n, d in zip(reps.REP_NAME, dom)]
    a["team_seg"] = np.where(general.reindex(a.PARTNER_ID).to_numpy(), -1, a.seg)
    a = a.sort_values(["PARTNER_ID", "team_seg", "active", "CURRENT_ARR"], ascending=[True, True, False, False])
    a["pos"] = a.groupby(["PARTNER_ID", "team_seg"]).cumcount()
    a = a.merge(teams.rename(columns={"seg": "team_seg"}), on=["PARTNER_ID", "team_seg"], how="left")
    kk = a.pos % (2 * a.n)
    a["j"] = np.where(kk < a.n, kk, 2 * a.n - 1 - kk)
    a = a.merge(reps[["PARTNER_ID", "seg", "j", "REP_ID"]].rename(columns={"seg": "team_seg"}),
                on=["PARTNER_ID", "team_seg", "j"], how="left")
    book = a[a.active].groupby("REP_ID").agg(BOOK_ACTIVE_ACCOUNTS=("ACCOUNT_ID", "size"), BOOK_ARR=("CURRENT_ARR", "sum"))
    reps = reps.merge(book, left_on="REP_ID", right_index=True, how="left").fillna(
        {"BOOK_ACTIVE_ACCOUNTS": 0, "BOOK_ARR": 0})
    reps["BOOK_ACTIVE_ACCOUNTS"] = reps.BOOK_ACTIVE_ACCOUNTS.astype(int)
    reps["BOOK_ARR"] = reps.BOOK_ARR.round(2)
    reps = reps[["REP_ID", "PARTNER_ID", "REP_NAME", "TITLE", "SEGMENT_FOCUS", "REGION", "EMAIL",
                 "BOOK_ACTIVE_ACCOUNTS", "BOOK_ARR"]]
    owner = a.set_index("ACCOUNT_ID").REP_ID
    return p, pams, reps, owner


def generate(sink, real_df=None, log=print, **overrides):
    """sink(table_name, dataframe, first_write) persists each batch (CSV locally, write_pandas in Snowflake)."""
    cfg = dict(CFG, **overrides)
    N, T = cfg["N_ACCOUNTS"], cfg["N_MONTHS"]
    rng = np.random.default_rng(cfg["SEED"])
    months = pd.date_range(cfg["START"], periods=T, freq="MS")
    mdates = np.array([d.date() for d in months], dtype=object)
    moy, yr = months.month.to_numpy() - 1, months.year.to_numpy()
    written = set()

    def put(name, df):
        if len(df):
            sink(name, df.reset_index(drop=True), name not in written)
            written.add(name)

    put("PRODUCTS", products_df())
    pdf, P = build_partners(rng, cfg["N_PARTNERS"])
    acc = build_accounts(rng, N, cfg["N_REAL"], real_df, P, T, moy, months)
    summaries = []
    for ci, lo in enumerate(range(0, N, cfg["CHUNK"])):
        chunk = acc.iloc[lo:lo + cfg["CHUNK"]]
        subs, sm, am, cm, summ = _sim_chunk(chunk, T, moy, yr, mdates, P["q"],
                                            np.random.default_rng([cfg["SEED"], ci + 1]))
        for name, df in (("SUBSCRIPTIONS", subs), ("SUBSCRIPTION_MONTHLY", sm), ("ACCOUNT_MONTHLY", am),
                         ("CONSUMPTION_MONTHLY", cm)):
            put(name, df)
        summaries.append(summ)
        log(f"chunk {ci + 1}: {lo + len(chunk):,}/{N:,} accounts")
    out = pd.DataFrame({
        "ACCOUNT_ID": acc["ACCOUNT_ID"], "ACCOUNT_NAME": acc["name"], "DOMAIN": acc["domain"],
        "IS_REAL_COMPANY": acc["is_real"].astype(bool), "INDUSTRY": acc["industry"],
        "INDUSTRY_GROUP": np.array(GROUPS)[acc["grp"]], "SEGMENT": np.array(SEGS)[acc["seg"]],
        "EMPLOYEE_BAND": acc["emp"], "COUNTRY": acc["country"], "REGION": np.array(REGIONS)[acc["reg"]],
        "PARTNER_ID": pdf["PARTNER_ID"].to_numpy()[acc["p_idx"]], "CUSTOMER_SINCE": acc["since"],
        "CONTRACT_TERM": np.array(TERMS)[acc["term"]],
        "RENEWAL_MONTH_OF_YEAR": acc["renew_moy"] + 1}).merge(pd.concat(summaries), on="ACCOUNT_ID")
    out.loc[out.BILLING_MODEL != "Seats", "CONTRACT_TERM"] = "Annual"
    out["CURRENT_RISK_BAND"] = np.select(
        [out.CURRENT_HEALTH_SCORE >= 70, out.CURRENT_HEALTH_SCORE >= 50, out.CURRENT_HEALTH_SCORE >= 30],
        ["Healthy", "Watch", "At Risk"], "Critical")
    pdf2, pams, reps, owner = build_coverage(np.random.default_rng([cfg["SEED"], 777]), out, pdf)
    out.insert(out.columns.get_loc("PARTNER_ID") + 1, "PARTNER_REP_ID", out.ACCOUNT_ID.map(owner).to_numpy())
    put("PARTNERS", pdf2)
    put("TRULINE_PAMS", pams)
    put("PARTNER_REPS", reps)
    put("ACCOUNTS", out)
    return out


def csv_sink(folder):
    import os
    os.makedirs(folder, exist_ok=True)

    def _s(name, df, first):
        df.to_csv(f"{folder}/{name}.csv", mode="w" if first else "a", header=first, index=False)
    return _s


def snowflake_sink(session, database, schema):
    def _s(name, df, first):
        session.write_pandas(df.reset_index(drop=True), name, database=database, schema=schema,
                             auto_create_table=True, overwrite=first)
    return _s
