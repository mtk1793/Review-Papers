from pathlib import Path
import json, math, re
import pandas as pd
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parents[1]
RES=ROOT/'results_v2'; FIG=ROOT/'figures_v2'; REFD=ROOT/'references'; OUTD=ROOT/'manuscript_v2'; OUTD.mkdir(exist_ok=True)
OUT=OUTD/'PG_CARE_Leakage_Free_IEEE_Transactions_Manuscript.docx'
refs=pd.read_csv(REFD/'references_2020_2026_v2.csv').fillna('')
cls=pd.read_csv(RES/'v2_classification_metrics.csv')
cal=pd.read_csv(RES/'v2_calibration_metrics.csv')
cqr=pd.read_csv(RES/'v2_cqr_metrics.csv')
boot=pd.read_csv(RES/'v2_block_bootstrap_ci.csv')
unseen=pd.read_csv(RES/'v2_unseen_ev_metrics.csv')
abl=pd.read_csv(RES/'v2_feature_group_ablation.csv')
stress=pd.read_csv(RES/'v2_schedule_stress.csv')
qsts=pd.read_csv(RES/'v2_ieee33_qsts_summary.csv')
roll=pd.read_csv(RES/'v2_rolling_origin_metrics.csv')
mcn=pd.read_csv(RES/'v2_mcnemar.csv')
cond=pd.read_csv(RES/'v2_conditional_coverage.csv')
summary=json.load(open(RES/'v2_summary.json'))

def row(model): return cls[cls.model==model].iloc[0]
raw=row('LightGBM raw'); phy=row('Leak-free physics projection'); pg=row('PG-CARE v2 conformal+abstention')

# -------------------- Word helpers --------------------
def set_font(run,size=None,bold=None,italic=None,name='Times New Roman'):
    run.font.name=name; run._element.rPr.rFonts.set(qn('w:eastAsia'),name)
    if size: run.font.size=Pt(size)
    if bold is not None: run.bold=bold
    if italic is not None: run.italic=italic

def set_columns(section,num=2,space_twips=360):
    sectPr=section._sectPr; cols=sectPr.xpath('./w:cols')
    cols=cols[0] if cols else OxmlElement('w:cols')
    if not sectPr.xpath('./w:cols'): sectPr.append(cols)
    cols.set(qn('w:num'),str(num)); cols.set(qn('w:space'),str(space_twips)); cols.set(qn('w:equalWidth'),'1')

def keep_next(p):
    pPr=p._p.get_or_add_pPr(); e=OxmlElement('w:keepNext'); e.set(qn('w:val'),'1'); pPr.append(e)

def shade(cell,fill='E6E6E6'):
    tcPr=cell._tc.get_or_add_tcPr(); e=tcPr.find(qn('w:shd'))
    if e is None: e=OxmlElement('w:shd'); tcPr.append(e)
    e.set(qn('w:fill'),fill)

def margins(cell,tw=35):
    tcPr=cell._tc.get_or_add_tcPr(); tcMar=tcPr.first_child_found_in('w:tcMar')
    if tcMar is None: tcMar=OxmlElement('w:tcMar'); tcPr.append(tcMar)
    for k in ('top','start','bottom','end'):
        e=tcMar.find(qn('w:'+k))
        if e is None: e=OxmlElement('w:'+k); tcMar.append(e)
        e.set(qn('w:w'),str(tw)); e.set(qn('w:type'),'dxa')

def add_body(doc,text,indent=True,size=9.15):
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY; p.paragraph_format.line_spacing=1.0; p.paragraph_format.space_after=Pt(1.0)
    if indent: p.paragraph_format.first_line_indent=Inches(.14)
    r=p.add_run(text); set_font(r,size)
    return p

def add_heading(doc,text,level=1):
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER if level==1 else WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before=Pt(4 if level==1 else 2.5); p.paragraph_format.space_after=Pt(1.5); keep_next(p)
    r=p.add_run(text.upper() if level==1 else text); set_font(r,9.3 if level==1 else 9.1,bold=True,italic=(level>=3))
    return p

def add_eq(doc,eq,num):
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before=Pt(1.5); p.paragraph_format.space_after=Pt(1.5)
    r=p.add_run(eq+f'     ({num})'); set_font(r,9.0,name='Cambria Math'); return p

def add_bullet(doc,text):
    p=doc.add_paragraph(); p.style=doc.styles['List Bullet']; p.paragraph_format.left_indent=Inches(.16); p.paragraph_format.first_line_indent=Inches(-.08); p.paragraph_format.space_after=Pt(.7)
    r=p.add_run(text); set_font(r,8.8); return p

def add_caption(doc,text):
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY; p.paragraph_format.space_after=Pt(2.5)
    r=p.add_run(text); set_font(r,7.6); return p

def add_figure(doc,stem,caption,width=3.15):
    p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before=Pt(1.5); p.paragraph_format.space_after=Pt(0)
    p.add_run().add_picture(str(FIG/(stem+'.png')),width=Inches(width)); add_caption(doc,caption)

def add_table(doc,headers,rows,widths=None,caption=None,fs=6.6,repeat_header=True):
    if caption:
        p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_before=Pt(2); p.paragraph_format.space_after=Pt(1); keep_next(p)
        set_font(p.add_run(caption),7.7,bold=True)
    t=doc.add_table(rows=1,cols=len(headers)); t.alignment=WD_TABLE_ALIGNMENT.CENTER; t.autofit=False
    if widths:
        tblPr=t._tbl.tblPr; lay=tblPr.find(qn('w:tblLayout'))
        if lay is None: lay=OxmlElement('w:tblLayout'); tblPr.append(lay)
        lay.set(qn('w:type'),'fixed'); grid=t._tbl.tblGrid
        for ch in list(grid): grid.remove(ch)
        for w in widths:
            gc=OxmlElement('w:gridCol'); gc.set(qn('w:w'),str(int(w*1440))); grid.append(gc)
    hdr=t.rows[0]
    if repeat_header:
        trPr=hdr._tr.get_or_add_trPr(); th=OxmlElement('w:tblHeader'); th.set(qn('w:val'),'true'); trPr.append(th)
    for j,h in enumerate(headers):
        c=hdr.cells[j]; c.text=''; shade(c); margins(c); c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
        if widths: c.width=Inches(widths[j])
        p=c.paragraphs[0]; p.alignment=WD_ALIGN_PARAGRAPH.CENTER; set_font(p.add_run(str(h)),fs,bold=True)
    for rr in rows:
        tr=t.add_row(); tr.height_rule=WD_ROW_HEIGHT_RULE.AT_LEAST
        for j,v in enumerate(rr):
            c=tr.cells[j]; c.text=''; margins(c); c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            if widths: c.width=Inches(widths[j])
            p=c.paragraphs[0]; p.alignment=WD_ALIGN_PARAGRAPH.CENTER if j else WD_ALIGN_PARAGRAPH.LEFT
            set_font(p.add_run(str(v)),fs)
    return t

def add_col_break(doc):
    p=doc.add_paragraph(); p.add_run().add_break(WD_BREAK.COLUMN)

def f3(v): return f'{float(v):.3f}'
def f4(v): return f'{float(v):.4f}'

# -------------------- Document --------------------
doc=Document(); sec=doc.sections[0]
for s in [sec]:
    s.page_width=Inches(8.5); s.page_height=Inches(11); s.top_margin=Inches(.45); s.bottom_margin=Inches(.48); s.left_margin=Inches(.54); s.right_margin=Inches(.54)
normal=doc.styles['Normal']; normal.font.name='Times New Roman'; normal._element.rPr.rFonts.set(qn('w:eastAsia'),'Times New Roman'); normal.font.size=Pt(9.15)
for stname in ['List Bullet','List Number']:
    st=doc.styles[stname]; st.font.name='Times New Roman'; st._element.rPr.rFonts.set(qn('w:eastAsia'),'Times New Roman'); st.font.size=Pt(8.8)
header=sec.header.paragraphs[0]; header.alignment=WD_ALIGN_PARAGRAPH.CENTER; set_font(header.add_run('MANUSCRIPT PREPARED IN IEEE TRANSACTIONS STYLE'),7.2)
footer=sec.footer.paragraphs[0]; footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
run=footer.add_run(); b=OxmlElement('w:fldChar'); b.set(qn('w:fldCharType'),'begin'); i=OxmlElement('w:instrText'); i.set(qn('xml:space'),'preserve'); i.text=' PAGE '; e=OxmlElement('w:fldChar'); e.set(qn('w:fldCharType'),'end'); run._r.extend([b,i,e])

p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_after=Pt(4)
set_font(p.add_run('PG-CARE: Leakage-Free Physics-Guided Conformal Reliability for One-Hour-Ahead EV Flexibility Forecasting and Distribution-Feeder Support'),17,bold=True)
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_after=Pt(1)
set_font(p.add_run('Mahmoud M. Kiasari and Hamed H. Aly'),10.5)
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.paragraph_format.space_after=Pt(4)
set_font(p.add_run('Department of Electrical and Computer Engineering, Dalhousie University, Halifax, NS, Canada'),8.4,italic=True)

ab=("Abstract—Reliable vehicle-to-grid (V2G) operation requires more than accurate electric-vehicle (EV) state classification: a forecast must be issued without access to target-time information, remain physically feasible, quantify uncertainty, and create useful feeder support when the realized fleet differs from expectation. This paper presents PG-CARE, a model-agnostic reliability envelope for one-hour-ahead EV operating-state and flexibility forecasting. The study first reconstructs the supervisory logic of a previously published MATLAB/Simulink controller in a scalable Python digital twin with 100 heterogeneous EVs, 365 days, and 3.504 million EV-time states. A critical leakage pathway in the earlier formulation is removed by separating owner-declared connection schedules from realized future connectivity and forecasting the latter from information available at issuance time. On the full 85-day chronological test interval (203,900 hourly forecasts), raw LightGBM achieves 0.7986 macro-F1 and 0.6700 V2G F1. Leak-free feasibility projection raises these to 0.8140 and 0.7088, while conformal abstention reaches 0.8183 and 0.7155. A paired issue-time block bootstrap gives a macro-F1 improvement of +0.0196 with a 95% confidence interval of [+0.0171,+0.0221]. A separate future-connectivity predictor achieves 0.9702 accuracy and 0.9960 ROC-AUC. Conformalized quantile regression (CQR) provides 0.8996 empirical coverage for upward flexibility. Finally, balanced AC quasi-static time-series analysis on the IEEE 33-bus feeder shows the reliability-value tradeoff: raw mean flexibility supplies stronger voltage support but incurs 8.678 MWh of commitment shortfall, whereas PG-CARE's conservative CQR and reliability-budgeted recovery (RBR) policies produce zero observed shortfall while recovering part of the feeder benefit. Marginal state-set coverage is 0.9117, but V2G conditional coverage is only 0.8016, exposing an important limitation rather than hiding it. The results support a shift from forecast accuracy alone toward leakage-free, uncertainty-aware, physically admissible flexibility commitments.")
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY; p.paragraph_format.left_indent=Inches(.17); p.paragraph_format.right_indent=Inches(.17); p.paragraph_format.space_after=Pt(3); set_font(p.add_run(ab),8.45)
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY; p.paragraph_format.left_indent=Inches(.17); p.paragraph_format.right_indent=Inches(.17); p.paragraph_format.space_after=Pt(3)
set_font(p.add_run('Index Terms—Electric vehicles, V2G, conformal prediction, flexibility forecasting, physical feasibility, uncertainty quantification, distribution feeder, quasi-static time series.'),8.35,italic=True)
# full-width fig
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.add_run().add_picture(str(FIG/'fig1_v2_framework.png'),width=Inches(7.05)); add_caption(doc,'Fig. 1. PG-CARE v2 information flow. Target-time realized connectivity, state, SOC, and flexibility are prohibited from the decision layer; only history, declared schedules, forecasts, deterministic leak-free feasibility rules, conformal uncertainty, and the reliability-budgeted recovery policy are used before feeder evaluation.')
sec2=doc.add_section(WD_SECTION.CONTINUOUS); sec2.top_margin=Inches(.45); sec2.bottom_margin=Inches(.48); sec2.left_margin=Inches(.54); sec2.right_margin=Inches(.54); set_columns(sec2,2,330)

add_heading(doc,'I. Introduction')
add_body(doc,'EV aggregators can transform flexible charging loads into controllable grid resources, but the value of that flexibility depends on whether it is still available when a scheduling or reserve decision is executed. Recent work has therefore moved from deterministic charging schedules toward aggregate flexibility, stochastic model predictive control, user-aware scheduling, safe reinforcement learning, and distribution-network-aware flexibility representations [12], [17], [18], [26]–[29], [37]–[39]. In parallel, EV load forecasting has adopted multi-scale expert systems, spatio-temporal graph models, causal generalization mechanisms, and value-oriented training [11], [19]–[22], [30], [40]. These developments raise a stricter question than “which model has the highest accuracy?”: can a forecast be trusted enough to authorize a physical V2G commitment?')
add_body(doc,'The authors’ earlier MATLAB/Simulink work [1] established owner participation choices, minimum-SOC protection, V2G/G2V/Idle supervisory logic, and a bidirectional charger-oriented controller. Its four-EV/four-household scale was adequate for controller demonstration but not for statistical forecasting. A subsequent large-scale forecasting study exposed a second problem: a physical mask that uses realized future connectivity can silently leak target-time information into the classifier, making an apparent “physics gain” partly an information leak. This paper treats removal of that leak as a non-negotiable design requirement rather than a cosmetic revision.')
add_body(doc,'PG-CARE is therefore positioned as a reliability envelope around a forecasting backbone, not as another claim that a particular deep architecture dominates all alternatives. It separates declared schedule information from realized connectivity; predicts future connectivity explicitly; projects state probabilities through feasibility rules using issuance-time information only; calibrates state prediction sets and flexibility intervals after the projection; and allows the controller to abstain or recover flexibility according to a validation-selected reliability budget. Feeder-level QSTS then measures the operational consequence of conservative versus aggressive commitments.')
add_body(doc,'The main contributions are:',indent=False)
add_bullet(doc,'Leak-free formulation: target-time realized connectivity and state are structurally inaccessible to the feasibility layer. An automated source-code invariant test enforces this condition, and future connectivity is predicted separately from historical and declared information.')
add_bullet(doc,'Dual conformal reliability: split-conformal state sets are calibrated after feasibility projection, while CQR produces uncertainty intervals for upward V2G flexibility. Coverage is reported marginally and conditionally by class/hour rather than as a single favorable number.')
add_bullet(doc,'Reliability-Budgeted Recovery (RBR): a validation-selected recovery rule uses singleton state sets, forecast connectivity, and interval width to recover part of the point forecast above the conservative CQR lower bound without exceeding a preset validation shortfall budget.')
add_bullet(doc,'Transactions-oriented validation: the framework is tested on the complete chronological 85-day period, rolling-origin blocks, never-seen EV identities, corrupted declarations, paired issue-time block bootstrap, and an IEEE 33-bus balanced AC QSTS stress test. No synthetic market settlement is used in the revised headline results.')

add_heading(doc,'II. Related Work and Positioning')
add_heading(doc,'A. EV flexibility and grid services',2)
add_body(doc,'Modern EV aggregation studies increasingly model flexibility as a bounded, uncertain resource rather than a binary charging decision. Learning-based aggregate flexibility and scheduling [12], efficient population envelopes [17], stochastic reserve provision using more than one million charging records [18], user-anxiety-aware frequency regulation [26], carbon-aware flexibility quantification [27], hierarchical disaggregation feasibility [28], and heterogeneous renewable-following flexibility [29] all emphasize that grid service depends on both power and energy feasibility. Analytical polytope aggregation has also been demonstrated on IEEE 33- and 141-bus networks with uncertainty [37], while battery degradation cost materially changes the economically available fleet region [38].')
add_heading(doc,'B. Forecasting, generalization, and operational value',2)
add_body(doc,'The forecasting literature has become substantially more demanding. Multi-scale spatial-temporal GNNs [11], deep expert systems [19], causal generalization [22], robust adaptive uncertainty sets [25], stacked meta-learning for EV charging [30], and 2026 highway forecasting with independent scenario evaluation [40] demonstrate the current emphasis on heterogeneous regimes and external structure. Meanwhile, seamless multi-resolution and value-oriented forecasting show that operational cost can rank models differently from statistical error [20], [21]. This motivates evaluating not just state F1 but also commitment shortfall and feeder response.')
add_heading(doc,'C. Conformal prediction in energy systems',2)
add_body(doc,'Conformal methods provide finite-sample marginal coverage under exchangeability without assuming a correct parametric predictive distribution. Adaptive time-series conformal methods [32] and recent power-system applications to PV, wind, price, and behind-the-meter disaggregation [31], [33]–[35] make the methodology increasingly relevant to grid forecasting. However, marginal validity does not imply conditional validity by EV state, hour, or arbitrary distribution shift. PG-CARE therefore reports the conditional failure modes explicitly and does not claim coverage under unrestricted OOD shift.')
add_table(doc,['Gap','Recent direction','PG-CARE v2 response'],[
('Future availability','Stochastic/user-aware EV models [18],[26]','Predict connectivity; separate declaration from realization'),
('Physical feasibility','Fleet envelopes / safe scheduling [28],[37]–[39]','Leak-free deterministic probability projection'),
('Forecast uncertainty','Conformal energy forecasting [31]–[35]','State sets + CQR, calibrated post-projection'),
('Decision value','Value-oriented forecasting [20],[21]','RBR commitment + IEEE 33-bus QSTS'),
('Generalization','Causal/OOD forecasting [22],[25],[40]','Chronological, rolling, unseen-EV, schedule stress')
],widths=[.80,1.12,1.15],caption='TABLE I  POSITIONING AGAINST 2020–2026 LITERATURE',fs=6.1)

add_heading(doc,'III. Source-Informed Digital Twin and Leak-Free Forecasting Problem')
add_heading(doc,'A. Supervisory reconstruction and data generation',2)
add_body(doc,'The digital twin is a supervisory reconstruction of the logic and operating concepts in [1], not a claim of switching-level equivalence to the original 10-kHz Simulink converter. It models 100 heterogeneous EVs for 365 days at 15-min resolution (3,504,000 EV-time states). Each EV has battery capacity, charger rating, owner policy, minimum SOC, declared arrival/departure schedule, realized connection process, trip energy, and requested departure SOC. System variables include native load, PV, and a price signal. The battery state evolves according to')
add_eq(doc,'SOC_i(t+1) = SOC_i(t) + [eta_c P_c,i(t) - P_d,i(t)/eta_d] Delta_t / E_i',1)
add_body(doc,'with SOC and charging/discharging power clipped to physical bounds. The three operating states are written symbolically as G2V, Idle, and V2G to avoid ambiguity from historical current-sign conventions.')
add_heading(doc,'B. Declared schedule versus realized connectivity',2)
add_body(doc,'The central integrity change is that a declared schedule is not treated as ground truth. Owner-declared arrival and departure times are generated separately from realized connection times; stochastic late arrival, early departure, and timing error create a one-hour-ahead declaration/realization mismatch of about 3.1%. At forecast issue time t, the model may use the declaration and historical connectivity up to t, but not realized connectivity a_t+H. This represents the information structure available to a practical aggregator.')
add_figure(doc,'fig2_schedule_uncertainty','Fig. 2. Separation of owner-declared and realized connection schedules. Realized target-time connectivity is used only to construct labels and evaluate delivery; it never enters the forecast-time feasibility projection.',3.15)
add_heading(doc,'C. Multi-output targets',2)
add_body(doc,'For horizon H=1 h, the framework estimates the target operating state, target connectivity probability, and upward flexibility. The core outputs are')
add_eq(doc,'f_theta(X[t-L:t]) -> {p_hat(y[t+H]), a_hat[t+H], P_up_hat[t+H]}',2)
add_body(doc,'where the history is L=2 h and includes dynamic battery states, current connection/state indicators, declared time-to-departure, requested SOC, load/price context, clock features, and static EV parameters. The test protocol issues forecasts once per hour for all 100 EVs across the full 85-day final interval, yielding 203,900 examples without random subsampling of the test period.')

add_heading(doc,'IV. Formal Information-Safe Problem Formulation')
add_heading(doc,'A. Forecast-time information set',2)
add_body(doc,'Let I_t denote the information available when a one-hour-ahead forecast is issued. I_t contains observations through t, owner-declared schedules, static battery/charger parameters, and exogenous information known or forecast at t. It explicitly excludes realized target-time connectivity a(t+H), realized target state y(t+H), future SOC, and realized target flexibility. Every deterministic rule applied before the forecast is scored must be a function of I_t only. This distinction is more fundamental than model choice because access to a(t+H) collapses much of the Idle/non-Idle uncertainty by construction.')
add_eq(doc,'I_t = sigma{ X(s), s <= t; declared schedule; static parameters; known exogenous inputs }',3)
add_heading(doc,'B. Feasible action set',2)
add_body(doc,'For each EV, the admissible target-state set is defined from forecast-time information. V2G is removed when owner policy forbids export, current/forecast SOC cannot support the minimum-SOC reserve, or predicted connection is below its validated threshold. G2V is removed when the EV is predicted unavailable or charging is unnecessary/forbidden. Idle is always retained as the safe fallback. The role of the physics layer is therefore not to manufacture a label but to exclude actions that conflict with the forecast-time feasible set.')
add_heading(doc,'C. Evaluation objective',2)
add_body(doc,'The statistical objective is deliberately multi-criteria: improve minority-state reliability without degrading calibration, while the decision objective is to reduce commitment shortfall for a useful amount of delivered V2G support. No single scalar metric is sufficient. We therefore report macro-F1 and MCC for state reliability, marginal/conditional coverage for uncertainty, interval coverage/width for flexibility, and feeder losses/voltage/shortfall for operational consequence.')

add_heading(doc,'V. PG-CARE v2 Reliability Envelope')
add_heading(doc,'A. Future-connectivity predictor',2)
add_body(doc,'A binary LightGBM model estimates target connectivity from history and declared schedule information. This forecast, rather than realized a_{t+H}, enters the physical layer. On the chronological test period it attains 0.9702 accuracy, 0.9722 F1, and 0.9960 ROC-AUC. A validation-selected probability threshold of 0.30 is used in the projection.')
add_heading(doc,'B. Leak-free feasibility projection',2)
add_body(doc,'Let p̂=[p_G2V,p_Idle,p_V2G] be the state probabilities. A deterministic mask m(x_t) is constructed only from issuance-time variables and forecasts: current SOC, owner policy, declared schedule, predicted future connectivity, minimum SOC, and requested departure condition. The projected probabilities are')
add_eq(doc,'p_tilde,k = m_k(x_t) p_hat,k / sum_j m_j(x_t) p_hat,j',3)
add_body(doc,'with a safe Idle fallback if the feasible denominator vanishes. The source-code test supplied with the package parses the projection function and fails if target-time realized connectivity/state arrays or t+H indexing appear inside the physical mask.')
add_heading(doc,'C. Split-conformal state sets',2)
add_body(doc,'The class nonconformity score is s(x,y)=1-p̃_y(x). For calibration size n and target miscoverage α, q_α is the ⌈(n+1)(1-α)⌉-th ordered score. The prediction set is')
add_eq(doc,'Gamma_alpha(x) = {k : 1 - p_tilde,k(x) <= q_alpha}',4)
add_body(doc,'A state decision is authorized only when the prediction set is singleton and feasible; otherwise PG-CARE abstains to a conservative fallback. Importantly, calibration is performed after the physical transformation.')
add_heading(doc,'D. Validity statement and boundary',2)
add_body(doc,'Proposition 1 (marginal post-projection validity). Suppose the feasibility projection g(x) is a deterministic measurable function only of information available at forecast issuance, and the calibration and test pairs are exchangeable. If the conformal score is computed from g(x) and calibrated on the resulting scores, then the standard split-conformal marginal guarantee P{Y∈Γ_α(X)}≥1-α holds up to the usual finite-sample quantile correction. Proof sketch: deterministic preprocessing of X does not break exchangeability of the scored calibration/test pairs; applying the standard rank argument to s(g(X),Y) yields the result. This proposition does not imply class-conditional, hour-conditional, or arbitrary time-series/OOD coverage; those are evaluated empirically.')
add_heading(doc,'E. CQR for flexibility and RBR',2)
add_body(doc,'Upward flexibility is forecast with a point model and LightGBM quantile models. CQR conformalizes the nominal [q_0.1,q_0.9] interval using calibration residuals, producing [L_t,U_t]. The conservative commitment is L_t^+=max(0,L_t). Because a pure lower-bound policy can be excessively conservative, RBR recovers a fraction of the point forecast only when the state set is singleton, predicted future connectivity exceeds 0.70, and the CQR interval is sufficiently narrow:')
add_eq(doc,'P_RBR(t) = L_plus(t) + beta g(t) max[0, P_up_hat(t) - L_plus(t)]',5)
add_body(doc,'where g_t∈[0,1] decreases with interval width and β is selected on validation data subject to a preset committed-flexibility shortfall budget. β is never tuned on the test period. This is a validation-calibrated decision rule, not a claim of globally optimal risk control.')

add_heading(doc,'VI. Experimental Protocol')
add_heading(doc,'A. Chronological partitions and metrics',2)
add_body(doc,'Days 1–200 are used for model fitting, days 201–240 for conformal calibration, days 241–280 for validation/decision tuning, and days 281–365 for the untouched final test. The main state metrics are accuracy, balanced accuracy, macro-F1, Matthews correlation coefficient (MCC), and per-class F1. Calibration is summarized by ECE, multiclass Brier score, marginal set coverage, set size, and class/hour conditional coverage. Regression uses MAE/RMSE and CQR coverage/width. Statistical uncertainty is obtained from 1,000 paired block-bootstrap resamples over forecast issue times, preserving cross-EV dependence within an issue time.')
add_heading(doc,'B. Generalization tests',2)
add_body(doc,'Three tests reduce the chance that performance is explained by repeated identity patterns. First, models are retrained on EVs 0–79 and tested on never-seen EVs 80–99 in the chronological test period. Second, static identity-like parameters and declared-schedule feature groups are ablated. Third, declared connectivity is corrupted with a 12% flip rate plus time-to-departure jitter. Rolling-origin 14-day blocks quantify temporal stability across the final 85 days.')
add_heading(doc,'C. Feeder QSTS',2)
add_body(doc,'Grid consequence is assessed with a balanced AC backward/forward-sweep model of the standard IEEE 33-bus radial feeder. EVs are allocated to five electrically separated buses and the full 2,039 hourly test instants are solved. V2G is requested only in high-native-load stress periods. Five strategies are compared: no forecast V2G, raw mean flexibility, CQR lower bound, RBR, and oracle realized flexibility. The study reports minimum voltage, bus-time voltage violations below 0.95 p.u., mean losses, peak substation import, delivered V2G energy, and commitment shortfall. The network is intentionally stressed and is a relative benchmark rather than a representation of a specific utility feeder.')

add_heading(doc,'VII. Results')
add_heading(doc,'A. Leak-free state forecasting',2)
add_table(doc,['Method','Acc.','Bal. Acc.','Macro-F1','MCC','V2G F1'],[
('LightGBM raw',f4(raw.accuracy),f4(raw.balanced_accuracy),f4(raw.macro_f1),f4(raw.mcc),f4(raw.v2g_f1)),
('Leak-free physics',f4(phy.accuracy),f4(phy.balanced_accuracy),f4(phy.macro_f1),f4(phy.mcc),f4(phy.v2g_f1)),
('PG-CARE v2',f4(pg.accuracy),f4(pg.balanced_accuracy),f4(pg.macro_f1),f4(pg.mcc),f4(pg.v2g_f1))
],widths=[1.10,.42,.50,.55,.46,.51],caption='TABLE II  FULL 85-DAY CHRONOLOGICAL TEST RESULTS',fs=6.35)
add_body(doc,'Removing target-time connectivity reduces the apparent benefit of the physics layer to a credible magnitude. Macro-F1 increases from 0.7986 to 0.8140 after leak-free projection and to 0.8183 with conformal abstention; V2G F1 rises from 0.6700 to 0.7155. The paired block bootstrap estimates Δmacro-F1=+0.0196 with 95% CI [+0.0171,+0.0221] and ΔMCC=+0.0155 with CI [+0.0130,+0.0179]. Exact McNemar testing counts 2,554 cases corrected by PG-CARE versus 543 degraded cases (p≈6.26×10^-310), but the block-bootstrap interval is emphasized because individual EV forecasts at the same issue time are not independent.')
add_figure(doc,'fig3_leakfree_metrics','Fig. 3. Leak-free classification performance. The revised physics layer produces a smaller but statistically stable improvement after removing future-connectivity leakage.',3.15)
add_heading(doc,'B. Rolling and unseen-EV performance',2)
add_body(doc,'PG-CARE improves macro-F1 in every rolling test block. On never-seen EVs 80–99, macro-F1 is 0.7857 and V2G F1 is 0.6484. With 12% declaration corruption, these become 0.7766 and 0.6221, respectively. The degradation is material but not catastrophic, indicating that the model depends on schedule information without treating it as infallible ground truth.')
add_figure(doc,'fig4_rolling_origin','Fig. 4. Rolling-origin macro-F1 across the final chronological test period. The last one-day block is small and correspondingly more volatile.',3.15)
add_table(doc,['Test','Macro-F1','V2G F1','MCC'],[(unseen.iloc[0]['test'],f4(unseen.iloc[0].macro_f1),f4(unseen.iloc[0].v2g_f1),f4(unseen.iloc[0].mcc)),(stress.iloc[1]['test'],f4(stress.iloc[1].macro_f1),f4(stress.iloc[1].v2g_f1),f4(stress.iloc[1].mcc))],widths=[1.45,.55,.55,.50],caption='TABLE III  GENERALIZATION AND DECLARATION-STRESS RESULTS',fs=6.2)
add_table(doc,['Feature set','Channels','Macro-F1','V2G F1'],[(r.feature_set,int(r.n_channels),f4(r.macro_f1),f4(r.v2g_f1)) for _,r in abl.iterrows()],widths=[1.35,.48,.62,.62],caption='TABLE IV  UNSEEN-EV FEATURE-GROUP ABLATION',fs=6.4)
add_body(doc,'Removing static identity parameters lowers macro-F1 by about 0.027, while removing declared schedule information lowers it by about 0.063. Dynamic-only forecasting falls further to 0.6488 macro-F1. This result is useful for interpretation: declared schedule is a legitimate high-value predictor, but it must remain probabilistic because real connection can deviate from declaration.')
add_figure(doc,'fig5_feature_ablation','Fig. 5. Feature-group ablation under the unseen-EV protocol.',3.1)

add_heading(doc,'C. Calibration and CQR',2)
add_body(doc,'The projected state probabilities reduce multiclass Brier score from 0.1311 to 0.1215 but increase ECE from 0.0201 to 0.0289. The conformal state sets achieve 0.9117 marginal coverage at a nominal 0.90 level with mean set size 0.9906. That favorable marginal result is not uniform: V2G class coverage is only 0.8016, and the 00:00–04:00 block is about 0.8348. These conditional gaps are explicitly reported because they prohibit a stronger class-conditional reliability claim.')
add_figure(doc,'fig6_class_coverage','Fig. 6. Conditional state-set coverage. Marginal coverage near 90% coexists with meaningful V2G and early-morning undercoverage.',3.1)
# Conditional coverage audit table
cc=[]
class_names={0:'Idle',1:'G2V',2:'V2G'}
for _,rr in cond.iterrows():
    if rr['group']=='class': label=class_names.get(int(rr['value']),str(rr['value']))
    else: label=str(rr['value'])
    cc.append((label,f"{float(rr['coverage']):.4f}"))
add_table(doc,['Condition','Empirical coverage'],cc,widths=[1.45,1.25],caption='TABLE V  CONDITIONAL CONFORMAL COVERAGE AUDIT',fs=6.5)
add_body(doc,'For upward flexibility, the point predictor obtains 0.6828-kW MAE and 1.9207-kW RMSE. CQR produces 0.8996 empirical coverage with 6.5018-kW mean interval width; 67.76% of examples have a zero conservative lower bound. This explains why a pure lower-bound commitment is reliable but can leave substantial usable flexibility untapped.')
add_figure(doc,'fig8_cqr','Fig. 7. CQR reliability characteristics for upward EV flexibility.',3.1)

add_heading(doc,'D. Feeder-level reliability-value tradeoff',2)
add_table(doc,['Strategy','Min V','Viol. bus-steps','Loss kW','Peak kW','Delivered MWh','Shortfall MWh'],[
(r.strategy,f'{r.min_voltage_pu:.3f}',int(r.voltage_violation_bus_steps),f'{r.mean_loss_kw:.1f}',f'{r.peak_substation_kw:.0f}',f'{r.v2g_delivered_mwh:.2f}',f'{r.commit_shortfall_mwh:.2f}') for _,r in qsts.iterrows()
],widths=[.84,.38,.55,.47,.47,.55,.55],caption='TABLE VI  IEEE 33-BUS QSTS STRESS TEST',fs=5.7,repeat_header=False)
add_body(doc,'Raw mean flexibility is aggressive: it delivers 125.54 MWh and produces stronger voltage/loss/peak effects, but overcommits by 8.678 MWh. The CQR lower-bound policy delivers only 43.13 MWh but has zero observed shortfall. RBR increases delivered support to 53.76 MWh, lowers mean loss to 265.56 kW and peak substation import to 11.060 MW, while preserving zero observed commitment shortfall in this test. Oracle realized flexibility provides the upper benchmark. These results demonstrate a genuine reliability-value frontier rather than a universal dominance claim.')
add_figure(doc,'fig7_qsts_tradeoff','Fig. 8. Feeder-support versus commitment-reliability tradeoff. RBR recovers part of the feeder benefit that is lost when using the CQR lower bound alone.',3.1)

add_heading(doc,'VIII. Computational and Reliability Analysis')
add_heading(doc,'A. Computational burden',2)
add_body(doc,'The final classifier and connectivity model are gradient-boosted trees because they provided a strong accuracy/complexity tradeoff in this environment. Training the connectivity and state models required approximately 1.87 s and 7.82 s, respectively, on the recorded CPU environment. Runtime deployment requires one connectivity probability, one three-class probability vector, deterministic masking, a conformal set lookup, and three flexibility regressors per forecast. The reliability layer is therefore lightweight relative to the one-hour decision horizon. The paper does not claim that tree ensembles are universally superior to modern deep models; rather, the method is intentionally backbone-agnostic so that future spatio-temporal models [19], [30], [40] can be substituted without reintroducing information leakage.')
add_heading(doc,'B. Failure modes that remain visible',2)
add_body(doc,'Three failure modes remain. First, V2G conformal coverage (0.8016) is well below the nominal 0.90 marginal target, so a user seeking state-conditional guarantees would require class-conditional or adaptive calibration. Second, schedule corruption disproportionately harms V2G because export opportunities occur near availability and SOC boundaries. Third, the CQR lower bound is frequently zero, making strict lower-bound dispatch reliable but conservative. RBR addresses the third issue empirically but does not solve the first two. These are explicit research targets, not hidden residual errors.')
add_heading(doc,'C. Oracle gap and conservatism',2)
add_body(doc,'The feeder experiment also quantifies the remaining oracle gap. RBR delivers 53.76 MWh compared with 152.18 MWh under perfect realized flexibility, so a large fraction of potential V2G support is intentionally left uncommitted. The raw mean model closes much of that gap but incurs 8.678 MWh shortfall. This gap motivates future decision-aware calibration that can allocate risk non-uniformly across operating states, buses, and time periods.')

add_heading(doc,'IX. Discussion')
add_heading(doc,'A. What is novel—and what is not',2)
add_body(doc,'The novelty is not LightGBM, a deterministic EV rule, conformal prediction, or IEEE 33-bus simulation in isolation. The contribution is the information-safe composition: future availability is predicted rather than leaked; physical projection is restricted to issuance-time information; conformal classification and CQR are calibrated after that projection; abstention prevents unsupported state commitments; and RBR converts interval width and forecast connectivity into a tunable reliability budget before a network action. The same reliability envelope can surround another backbone, including future graph or state-space forecasters, without changing the integrity requirements.')
add_heading(doc,'B. Why the honest gain is smaller',2)
add_body(doc,'The revised state-classification gain is intentionally smaller than the earlier draft because the strongest apparent benefit in that draft came from target-time connectivity inside the physical mask. Retaining the inflated result would be indefensible. The remaining +0.0196 macro-F1 improvement is statistically stable, accompanied by higher V2G F1 and MCC, and—more importantly—feeds a flexibility interval and feeder commitment layer that exposes the cost of forecast overconfidence.')
add_heading(doc,'C. Limitations and submission gate',2)
add_body(doc,'The present study remains a source-informed stochastic digital twin plus standard test-feeder validation. It is not a field trial, does not reproduce switching-level converter waveforms, and does not establish arbitrary OOD conformal validity. The stressed IEEE 33-bus voltages are useful for relative comparison but should not be interpreted as values from an actual utility feeder. The measured-data adapters supplied with the reproducibility package target ACN-Data session behavior and Open Power System Data household/PV traces, but those external data are not bundled or claimed as executed validation because access/download conditions require a separate user-side acquisition step.')
add_body(doc,'Before a final IEEE Transactions on Smart Grid submission, the highest-value additional experiment is external validation with measured sessions/load and, ideally, a utility or high-fidelity feeder. The current manuscript is designed so that this experiment changes the data source rather than the evaluation logic. A second priority is class-conditional calibration or adaptive conformal control targeted specifically at the observed V2G undercoverage.')

add_heading(doc,'X. Reproducibility and Data Availability')
add_body(doc,'The accompanying archive contains the original published-controller Simulink artifact, the source-informed Python twin, the leak-free forecasting pipeline, frozen LightGBM models, all chronological split results, full test predictions, block-bootstrap replicates, IEEE 33-bus QSTS code/results, vector PDF figures, source-code invariant test, exact environment information, a claim-to-file traceability document, and SHA-256 hashes. The measured-data acquisition scripts are intentionally separate and cache external datasets locally; raw third-party data are not redistributed.')

add_heading(doc,'XI. Conclusion')
add_body(doc,'PG-CARE v2 reframes one-hour-ahead EV forecasting as an information-integrity and decision-reliability problem. After eliminating future-connectivity leakage, physically feasible conformal state decisions improve macro-F1 and V2G F1 modestly but consistently across the complete chronological test period, rolling blocks, and unseen EVs. CQR provides near-nominal marginal coverage for upward flexibility, while feeder QSTS demonstrates why the mean prediction and conservative lower bound serve different objectives. Reliability-Budgeted Recovery provides an intermediate operating point that recovers grid support without observed shortfall in the test. The main unresolved issue is equally important: nominal marginal conformal coverage does not guarantee V2G conditional coverage, and external measured-data validation remains necessary before claiming field generalization. These boundaries define the next research step more clearly than another increase in model complexity.')

# References
add_heading(doc,'References')
for _,r in refs.iterrows():
    vol=str(r['volume']).replace('.0','') if str(r['volume']) else ''
    issue=str(r['issue']).replace('.0','') if str(r['issue']) else ''
    pages=str(r['pages']) if str(r['pages']) else ''
    s=f"[{int(r['no'])}] {r['authors']}, “{r['title']},” {r['journal']}"
    if vol: s+=f", vol. {vol}"
    if issue: s+=f", no. {issue}"
    if pages: s+=f", pp. {pages}" if pages!='Early Access' else ', Early Access'
    s+=f", {int(r['year'])}"
    if str(r['doi']): s+=f", doi: {r['doi']}"
    s+='.'
    p=doc.add_paragraph(); p.paragraph_format.first_line_indent=Inches(-.16); p.paragraph_format.left_indent=Inches(.16); p.paragraph_format.space_after=Pt(.45); p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY; set_font(p.add_run(s),6.85)

# Final layout defaults on all sections
for s in doc.sections:
    s.page_width=Inches(8.5); s.page_height=Inches(11); s.top_margin=Inches(.45); s.bottom_margin=Inches(.48); s.left_margin=Inches(.54); s.right_margin=Inches(.54)

doc.save(OUT)
print(OUT)
