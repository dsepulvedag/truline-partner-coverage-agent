import json, pandas as pd, numpy as np
import truline_gen as tg, validate as v
real = pd.DataFrame([  # well-known firms (names/domains real; all Truline data about them is synthetic)
 ("AECOM","aecom.com","civil engineering","10001+","united states"),("Jacobs","jacobs.com","civil engineering","10001+","united states"),
 ("Bechtel","bechtel.com","construction","10001+","united states"),("Skanska","skanska.com","construction","10001+","sweden"),
 ("Turner Construction Company","turnerconstruction.com","construction","5001-10000","united states"),
 ("Gensler","gensler.com","architecture & planning","5001-10000","united states"),("Arup","arup.com","civil engineering","10001+","united kingdom"),
 ("Kiewit","kiewit.com","construction","10001+","united states"),("Stantec","stantec.com","civil engineering","10001+","canada"),
 ("WSP","wsp.com","civil engineering","10001+","canada"),("HOK","hok.com","architecture & planning","1001-5000","united states"),
 ("Caterpillar","caterpillar.com","machinery","10001+","united states"),("Deere & Company","deere.com","machinery","10001+","united states"),
 ("Bosch","bosch.com","automotive","10001+","germany"),("Komatsu","komatsu.com","machinery","10001+","japan"),
 ("Ubisoft","ubisoft.com","computer games","10001+","france"),("Framestore","framestore.com","media production","1001-5000","united kingdom"),
 ("DNEG","dneg.com","media production","5001-10000","united kingdom"),("Fluor","fluor.com","construction","10001+","united states"),
 ("VINCI","vinci.com","construction","10001+","france")], columns=["NAME","DOMAIN","INDUSTRY","SIZE_BAND","COUNTRY"])
import os
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_1k")
v.run(D, 1000, n_real=17, real_df=real)
r = v.report(D)
print(json.dumps({k: r[k] for k in ["rows","bridge_max_err","sub_vs_acct_max_err","consumption_share_of_ARR","billing_mix_accounts","burn_status_last","band_mix_last","status"]}, default=str))
ac = pd.read_csv(f"{D}/ACCOUNTS.csv")
print(ac[ac.IS_REAL_COMPANY][["ACCOUNT_NAME","BILLING_MODEL","CURRENT_SEAT_ARR","CURRENT_CONSUMPTION_ARR","CURRENT_HEALTH_SCORE","STATUS"]].head(8).to_string(index=False))
print(ac[~ac.IS_REAL_COMPANY][["ACCOUNT_NAME","DOMAIN","INDUSTRY","COUNTRY"]].head(5).to_string(index=False))
print(pd.read_csv(f"{D}/PARTNERS.csv").head(3).to_string(index=False))
