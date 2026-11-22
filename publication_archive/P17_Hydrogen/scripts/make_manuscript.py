#!/usr/bin/env python3
"""Generate revised, carefully qualified IEEE-style two-column Word research draft."""
from pathlib import Path
from docx import Document
from docx.shared import Inches,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH,WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT,WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.section import WD_SECTION_START
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.enum.text import WD_BREAK
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'manuscript'/'IEEE_TSE_Revised_Draft.docx'
d=Document();sec=d.sections[0]
sec.page_height=Inches(11);sec.page_width=Inches(8.5)
sec.top_margin=Inches(.64);sec.bottom_margin=Inches(.60)
sec.left_margin=Inches(.65);sec.right_margin=Inches(.65)
sec.header_distance=Inches(.22);sec.footer_distance=Inches(.25)
style=d.styles['Normal'];style.font.name='Times New Roman';style.font.size=Pt(9.2)
style.paragraph_format.space_after=Pt(4);style.paragraph_format.line_spacing=1.05
for name,size,after in [('Title',17,7),('Heading 1',10.8,5),('Heading 2',9.5,3)]:
    s=d.styles[name];s.font.name='Times New Roman';s.font.size=Pt(size);s.font.bold=True
    s.paragraph_format.space_before=Pt(8);s.paragraph_format.space_after=Pt(after)
small=d.styles.add_style('Tiny reference',WD_STYLE_TYPE.PARAGRAPH)
small.font.name='Times New Roman';small.font.size=Pt(7.5)
small.paragraph_format.space_after=Pt(2);small.paragraph_format.line_spacing=1.0
cap=d.styles.add_style('Figure caption',WD_STYLE_TYPE.PARAGRAPH)
cap.font.name='Times New Roman';cap.font.size=Pt(8);cap.font.italic=True
cap.paragraph_format.space_after=Pt(5)

def body(txt):
    p=d.add_paragraph(txt.replace('**','').replace('`',''));p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
    return p

def head(txt):d.add_heading(txt,1)
def subhead(txt):d.add_heading(txt,2)
def eq(txt,num):
    p=d.add_paragraph();p.paragraph_format.space_before=Pt(4);p.paragraph_format.space_after=Pt(5)
    p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    r=p.add_run(txt);r.italic=True;r.font.name='Cambria Math';r.font.size=Pt(8.7)
    p.add_run('    ('+str(num)+')').font.size=Pt(8)

def img(file,caption):
    p=d.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(ROOT/'figures'/file),width=Inches(3.22))
    c=d.add_paragraph('Fig. '+caption,style='Figure caption');c.alignment=WD_ALIGN_PARAGRAPH.CENTER

def table(caption,headers,rows,widths=None):
    p=d.add_paragraph('TABLE '+caption,style='Figure caption');p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    tb=d.add_table(rows=1,cols=len(headers));tb.alignment=WD_TABLE_ALIGNMENT.CENTER
    tb.autofit=False
    if widths:
        for i,w in enumerate(widths):tb.columns[i].width=Inches(w)
    for i,name in enumerate(headers):tb.rows[0].cells[i].text=name
    for row in rows:
        cells=tb.add_row().cells
        for i,c in enumerate(row):cells[i].text=str(c)
    for ri,row in enumerate(tb.rows):
        for j,c in enumerate(row.cells):
            if widths:c.width=Inches(widths[j])
            c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for p in c.paragraphs:
                p.paragraph_format.space_after=Pt(1);p.paragraph_format.line_spacing=1.0
                for r in p.runs:
                    r.font.name='Times New Roman';r.font.size=Pt(7.0 if ri>0 else 7.3)
                    if ri==0:r.font.bold=True
    d.add_paragraph('').paragraph_format.space_after=Pt(1)
    return tb

p=d.add_paragraph(style='Title');p.alignment=WD_ALIGN_PARAGRAPH.CENTER
p.add_run('Forecast-Informed Hierarchical Reinforcement Learning for Degradation-Constrained Offshore Wind–Hydrogen Dispatch')
p=d.add_paragraph('IEEE TRANSACTIONS ON SUSTAINABLE ENERGY — RESEARCH REVISION DRAFT (EMPIRICAL VALIDATION PENDING)')
p.alignment=WD_ALIGN_PARAGRAPH.CENTER
for r in p.runs:r.font.size=Pt(7.7);r.font.color.rgb=RGBColor(150,43,42);r.bold=True
p=d.add_paragraph('Author details reserved for final submission');p.alignment=WD_ALIGN_PARAGRAPH.CENTER
for r in p.runs:r.font.size=Pt(8.5)
p=d.add_paragraph();p.paragraph_format.space_after=Pt(7)
r=p.add_run('Abstract—');r.bold=True
p.add_run(' Flexible hydrogen production can provide a controllable sink for offshore-wind surplus, but operational value depends on forecasting uncertainty, inventory and power-system constraints, and degradation of polymer-electrolyte-membrane (PEM) electrolyzers. This research develops an explicitly hierarchical control formulation comprising a supervised long short-term memory quantile forecaster, a quantile-regression deep Q-network (QR-DQN) for risk-sensitive discrete dispatch priorities, and a soft actor–critic (SAC) policy for continuous electrolyzer setpoints. The approach is formulated as staged hybrid learning rather than a three-agent multi-agent reinforcement learning system. A constrained simulator enforces electrical power balance, ramp limits, battery state-of-charge and hydrogen inventory. A reproducible evaluation protocol uses training, calibration and held-out weather years, calibrated prediction intervals, seeded controller comparisons and temporally aware confidence intervals. An audit of the original problem assumptions additionally reveals inconsistencies in claimed annual electrolyzer absorption, lifetime extension and hydrogen offtake. The paper reports the model formulation and reproducibility protocol; empirical comparative performance remains unverified pending acquisition of authentic meteorological records, calibrated ageing coefficients and source-matched market data. No unverified economic or lifetime gain is claimed.')
p=d.add_paragraph();p.add_run('Index Terms—').bold=True;p.add_run(' Electrolyzer scheduling, offshore wind, hydrogen, hierarchical reinforcement learning, degradation, probabilistic forecasting, conditional value-at-risk, reproducibility.')

sec2=d.add_section(WD_SECTION_START.CONTINUOUS)
sec2.top_margin=Inches(.64);sec2.bottom_margin=Inches(.60);sec2.left_margin=Inches(.65);sec2.right_margin=Inches(.65)
cols=sec2._sectPr.xpath('./w:cols')
if cols: co=cols[0]
else:co=OxmlElement('w:cols');sec2._sectPr.append(co)
co.set(qn('w:num'),'2');co.set(qn('w:space'),'280')

head('I. INTRODUCTION')
body('Proton-exchange-membrane (PEM) water electrolysis offers an operationally flexible conversion path between electrical energy and hydrogen, but flexibility is constrained by electrochemical, mechanical and economic considerations. Carmo et al. [1] review the core cell technology and operating mechanisms. Experimental investigations by Rakousky et al. [2], [3] document degradation phenomena and fluctuating-power challenges, while Schofield et al. [4] explicitly model the techno-economic consequences of usage-dependent degradation. These findings motivate dispatch methods that account for wear without treating every fast power change as a measured physical ageing event.')
body('The operational problem becomes more uncertain when wind production varies faster than a deterministic energy schedule and when contractual offtake and electricity prices are imperfectly known. NREL’s WIND Toolkit is a widely cited modeled resource [5], but the data years and spatial coverage depend on its specific generation. The more recent NOW-23 North Atlantic collection covers 2000–2020 and offers finer regional modeling for eligible sites [11]. The relevant offshore Canadian grid-integration context is discussed by Net Zero Atlantic [12]. Neither resource alone establishes historic dispatch-level curtailment at a specific Nova Scotia connection point.')
body('Deep reinforcement learning may produce low-latency operating decisions, but it does not remove uncertainty in the physical environment or establish causal evidence of savings. SAC supports continuous stochastic control [6]; quantile-regression deep Q-networks represent a distribution of discounted returns instead of only the expected value [7]; conditional value-at-risk (CVaR) offers a defined preference for the lower tail of outcomes [8]. These components are useful together only when their information flow, action sets and training assumptions are explicit and when comparison baselines are sufficiently strong.')
body('This paper therefore makes three methodological contributions. First, it defines an auditable forecast-informed hierarchy in which the LSTM is **not** an RL agent and the two RL policies are trained in disclosed stages. Second, it separates physically enforced plant constraints from an explicitly uncalibrated degradation surrogate and from the economic cash-flow layer. Third, it specifies temporal data partitioning, forecast interval calibration, ablations, paired uncertainty analysis and evidence lineage so that each quantitative conclusion can be regenerated from model outputs. The current revision is a scientifically bounded research draft; comparative numerical superiority is not inferred from smoke tests.')

head('II. RELATED WORK AND RESEARCH GAP')
body('Energy-system optimization has conventionally used model predictive control, deterministic planning or robust optimization when physics and future signals can be approximated. Schofield et al. [4] offer a PEM-specific degradation-aware optimization benchmark that should be treated as a substantive comparator rather than dismissed as unaware of degradation. The material question for a data-driven alternative is whether uncertain wind and value distributions change operation and equipment stress enough to justify policy-learning complexity, not whether optimization techniques are intrinsically unsuitable.')
body('SAC [6] addresses continuous setpoint control through a maximum-entropy objective. QR-DQN [7] predicts action-conditioned return quantiles, enabling risk-sensitive action selection. These are separate RL learners; a supervised LSTM used to produce a forecast is not a participant in an underlying Markov game. Forecast calibration can be based on quantile regression and separate nonconformity scores [9], although serial dependence means nominal exchangeability guarantees cannot simply be assumed for wind time series. We accordingly quantify empirical temporal coverage rather than promise finite-sample distribution-free validity.')

head('III. OPERATIONAL SYSTEM AND CONSTRAINTS')
subhead('A. Physical energy routing')
body('Consider a grid-connected wind-to-hydrogen facility indexed by dispatch step t and step duration Δt. Available wind Pᵂₜ is allocated to the electrolyzer Pᴱₜ, battery charging Pᶜₜ and grid export Pˣₜ. The BESS can discharge Pᵈₜ to support electrolyzer operation, while residual Pᵏₜ is curtailed. Each action is projected to the nonnegative physically feasible region.')
eq('Pᵂₜ + Pᵈₜ = Pᴱₜ + Pᶜₜ + Pˣₜ + Pᵏₜ',1)
body('Power limits constrain 0 ≤ Pᴱₜ ≤ 50 MW and |Pᴱₜ − Pᴱₜ₋₁| ≤ rₘₐₓ Δt. The BESS is represented by energy state Eᴮₜ with a bounded charge/discharge rate and efficiency η. Simultaneous charge/discharge and unrestricted grid imports are not assumed. Hydrogen mass stored Mᴴ₂ₜ increases by production proportional to electrolyzer input and decreases by delivered mass Dₜ.')
eq('Eᴮₜ₊₁ = Eᴮₜ + η½ Pᶜₜ Δt − Pᵈₜ Δt / η½',2)
eq('Mᴴ₂ₜ₊₁ = Mᴴ₂ₜ + (Pᴱₜ Δt / eᴴ₂) − Dₜ',3)
body('The production energy coefficient eᴴ₂ has units MWh/kg. This linear conversion is an explicit approximation; efficiency variation with current density, thermal condition, pressure and BoP load requires manufacturer calibration. Constraints on hydrogen tank capacity and delivery rates are enforced rather than allowing unlimited inventory. A 300 MW grid export cap in this model is a scenario parameter, not a verified transmission limit.')

subhead('B. Degradation model and economic separation')
body('Ageing is tracked in equivalent full-load operating hours with contributions from operation, starts and transient setpoint changes. This is a sensitivity surrogate, not an electrochemical membrane-damage predictor. A measured nominal stack design life Ldesign must be distinguished from a simulated time to an ageing threshold Lsim and from the discounted economic replacement schedule. The current implementation sets the unverified cold-start penalty to zero by default instead of asserting fifty equivalent hours per start.')
eq('Aₜ₊₁ = Aₜ + Δt (Pᴱₜ/Pᴱʳ) + kₛ Istartₜ + kᵣ (ΔPᴱₜ)²',4)
body('The controller reward subtracts a replacement-cost proxy proportional to incremental equivalent ageing, but neither that reward nor a one-year operating margin is a 15-year net present value. A defensible NPV requires verified plant CAPEX, stack replacement price, O&M, delivery/transport costs, true sale prices, grid contract terms, discounting and escalation sensitivity. The separate `economics.py` module provides explicit accounting, not independently validated economic assumptions.')

img('fig01_architecture.png','1. Forecast-informed architecture: supervised quantile-LSTM provides calibrated information to two staged RL policies. The image does not portray the LSTM as a third RL agent.')

table('I — LEARNING MODULE DEFINITIONS', ['Module','Learning','Decision/output'],[
    ['Quantile LSTM','Supervised','Wind P10/P50/P90'],
    ['QR-DQN','RL / discrete','H₂, BESS, export priority'],
    ['SAC','RL / continuous','Electrolyzer setpoint fraction']], [1.05,1.05,1.15])

head('IV. PROBABILISTIC WIND FORECASTING')
body('A one-layer LSTM [10] maps a trailing sequence of observed wind-power features into three conditional target quantiles q0.1, q0.5 and q0.9 at a declared forecast lead. For each sample with target y, training minimizes the mean pinball loss over τ ∈ {0.1,0.5,0.9}. Noncrossing predictions are obtained by sorting and clipping to the admissible plant range; the choice must be reported because postprocessing can affect quantile calibration.')
eq('Lpin = Eτ [ max{ τ(y−qτ), (τ−1)(y−qτ) } ]',5)
body('The absolute exceedance score is sᵢ = max{q0.1,i−yᵢ, yᵢ−q0.9,i, 0}. A nonnegative calibration radius is the finite-sample empirical quantile of s on the 2019 set. The test interval is [q0.1−δ, q0.9+δ] within the feasible output range. We report median MAE and RMSE, 80% interval coverage, mean width and interval score. With meteorological serial dependence and domain shift, these are measured holdout quantities rather than guaranteed conditional coverage.')
body('Chronological training is restricted to 2017–2018, calibration to 2019 and test to 2020. No model architecture, calibration setting or risk parameter may be selected on the 2020 test output. Persistence, simple linear-quantile and gradient-boosted-quantile forecasts are required comparators for an eventual submitted results section; only the neural model and interval diagnostics have been implemented and unit tested in the current package.')

head('V. HIERARCHICAL DISPATCH CONTROL')
subhead('A. Discrete allocation and continuous physical actuation')
body('The market-level policy chooses one of three discrete priorities: hydrogen-first, battery-charge-first or export-first. Its state contains current meteorological availability, calibrated lower/median/upper forecasts, scenario price, battery state of charge, hydrogen inventory and previous electrolyzer output. A QR-DQN approximates a set of 51 return quantiles for every action. For a conservative policy, actions are ranked by the mean of the lowest 25% of their estimated quantiles, an operational lower-tail estimate related to CVaR [7], [8].')
eq('aᴰₜ = arg maxₐ  (1/K) ∑ᵢ₌₁ᴷ Z₍ᵢ₎(sₜ, a)',6)
body('For a selected priority aᴰₜ, SAC supplies a continuous power fraction aᶜₜ ∈ [0,1] and optimizes discounted physical/economic reward under an entropy regularizer [6]. Requested actions are projected onto the plant’s ramp, capacity, SOC, inventory and wind availability constraints; executed actions, rather than unprojected requests, are recorded for all operational metrics.')
eq('Jπ = E[∑ₜ γᵗ {r(sₜ,aₜ) + α H(π(·|sₜ))}]',7)
body('Training is staged: QR-DQN is trained against a frozen reference setpoint mechanism, then SAC is trained with QR-DQN frozen. This procedure is a hierarchical hybrid control pipeline and should not be described as jointly trained multi-agent reinforcement learning. The method requires independent comparisons to a separately trained SAC without discrete arbitrage and to non-RL scheduling algorithms before any synergistic contribution can be established.')
subhead('B. Baselines and protocol')
body('A competitive evaluation shall include no-electrolysis, straightforward curtailment following, fixed-output scheduling, single-policy SAC, degradation-aware receding-horizon MPC and a perfect-information benchmark clearly marked as an unattainable oracle. Required ablations remove degradation feedback, CVaR tail preference, battery storage or forecast calibration one at a time. All comparators must share the same turbine conversion, plant hardware, demand, prices, feasible action region and future-information rules. The accompanying baseline environment currently implements the first four families and a staged hierarchy; a strong matched MPC and independent single-agent SAC training remain acceptance blockers.')

head('VI. DATA, PARAMETERS AND REPRODUCIBILITY')
body('The default experimental input is the NOW-23 North Atlantic NLR/NREL archive [11], subject to a strict distance-based coverage check for the original nominated Nova Scotia location. The original WIND Toolkit source described by Draxl et al. [5] does not provide the paper’s claimed 2020–2022 conventional WIND Toolkit years. Because NOW-23 ends in 2020, a 2017–2018/2019/2020 chronological split is used rather than fabricating later observations. Net Zero Atlantic offers more region-specific offshore wind data [12]; separate hourly ERA5 reanalysis can be used as an independent sensitivity input. All sources are modeled meteorological data rather than measured physical curtailment.')
body('Table II reports the *scenario* parameters used in code and is cited here as a reproducibility definition, not a claim of physical truth. A public NSPI archive can supply historical aggregate system load [13], although system load alone cannot infer congestion or curtailment. Equally, constant hypothetical electricity prices cannot establish merchant arbitrage under a true Nova Scotia settlement regime. Proper market data or auditable industrial tariffs are therefore essential to a final economic evaluation.')
table('II — BASE CASE ENGINEERING SCENARIO (NOT CALIBRATED)', ['Quantity','Scenario','Evidence status'],[
    ['Wind nameplate','700 MW','Hypothesis'],
    ['PEM nameplate','50 MW','Paper setting'],
    ['Grid export ceiling','300 MW','Proxy, unverified'],
    ['Battery','20 MWh / 10 MW','Paper + assumption'],
    ['Hydrogen tank','500 kg','Paper setting'],
    ['H₂ specific input','0.052 MWh/kg','Assumption'],
    ['Hydrogen offtake','800 kg/day','Paper example'],
    ['Dispatch interval','15 min','Scenario choice'],
    ['Sale price','5 USD/kg','Scenario only']], [1.28,.98,1.0])
body('The implementation records versioned JSON configuration, source SHA256 hashes, site coordinates, UTC timestamps, zero-gap QC and forecast calibration, as well as per-step energy-routing data. Unit tests cover power conservation, bounded storage, sign of battery energy flow, ramp constraints, quantile shapes, finite neural-network gradients and bootstrap calculations. A simulator smoke test uses seeded artificial wind solely to detect software failures; its outputs are never promoted to empirical engineering evidence.')

head('VII. ANALYTICAL FEASIBILITY AND CLAIM AUDIT')
body('Several previously reported figures are inconsistent with basic engineering limits. A 50 MW electrolyzer cannot absorb more than 438 GWh in a 365-day year, even at continuous full power and before outages. If the available wind surplus were 1,126 GWh, a claim of 78.2% absorption would imply 880.5 GWh and would therefore violate this bound. The number 340 GWh corresponds to only 30.2% of 1,126 GWh, but this ratio is an arithmetic observation, not validated historical curtailment recovery.')
img('fig02_feasibility_audit.png','2. Hard upper-bound check. The rejected 78.2% value is infeasible when its denominator is the reported 1,126 GWh wind surplus.')
body('The 20 MWh BESS likewise cannot support 40% of a 50 MW electrolyzer for 36 h: such operation needs 720 MWh before conversion losses. At 20 MW, a fully charged 20 MWh BESS lasts at most one hour. The originally reported hydrogen production-throughput claim is also incompatible with the cited plant offtake example. At 52 kWh/kg, consuming 340 GWh yields approximately 6.54 million kg/year; serving only 800 kg/day corresponds to 0.292 million kg/year. Unsold output cannot be counted as cash revenue without additional storage or buyer contracts.')
body('Finally, increasing modeled life from 17,500 to 19,100 h yields a 9.14% relative improvement when calculated against the former baseline, not the quoted 8.1%. Comparing 60,000 to 72,800 h yields 21.33% but represents a different pair of definitions or scenarios. These competing values must be withdrawn, not averaged, until one calibrated stack ageing model is applied to one frozen holdout and one consistently defined lifetime metric.')

head('VIII. EXPERIMENTAL RESULTS — EVIDENCE REQUIREMENTS')
body('The supplied original research code, its training checkpoints, the exact peer-reviewed manuscript version and the raw wind data are not available in this execution environment. The reconstructed simulator and neural training functions pass software-level tests; a representative synthetic fixture also executes end to end. These observations establish only internal numerical/software functionality, not gains on real Nova Scotia wind or statistically reliable superiority over MPC. Accordingly, there are **no validated empirical NPV, stack-lifetime, inference-latency or forecast-coverage result estimates in this revision**.')
body('After the 2017–2020 dataset is downloaded and a defensible study location confirmed, all baselines must run with at least five independent learning seeds. Test episodes and economic assumptions should be identical across policies; report per-seed performance, paired differences with block-bootstrap 95% intervals, seasonal and tail-event strata, energy-balance residuals, start counts and calibrated prediction interval coverage. A single result row must be reproducibly exported to both a figure and a table with traceable configuration and seed hashes. A data-dependent claim without this evidence is not included in a submission abstract.')

head('IX. DISCUSSION, LIMITATIONS AND FUTURE WORK')
body('The distinction between model assumptions and observed operating behavior is fundamental. A generic cubic turbine characteristic, static connection export cap and simplified inventory constraints do not replace turbine manufacturer data, network-constrained dispatch, flow limits or validated plant balance-of-system operations. An electricity-demand series is not itself a measurement of renewable energy curtailment, and a price scenario cannot be treated as a transactable merchant market. Real grid contracts and a consistent H₂ delivery network may materially alter the action ranking.')
body('The present ageing surrogate does not claim to represent membrane thinning or catalyst loss with experimentally established coefficients. Future validation should fit ramp/start/thermal parameters to manufacturer or laboratory observations, assess out-of-domain weather, and study uncertainty in replacement and nominal-lifetime assumptions. Methodological superiority also depends on comparing joint or staged learning with suitable deterministic and stochastic optimizers; without this, claims of unique multi-agent contribution are premature.')

head('X. CONCLUSION')
body('A reproducible, forecast-informed hierarchy has been specified for offshore wind–hydrogen dispatch: the LSTM forecasts probabilistic wind availability, QR-DQN selects a risk-sensitive discrete priority and SAC actuates continuous constrained setpoints. These are two RL policies plus a supervised forecast module, rather than a three-agent MARL algorithm. The physical and economic audit demonstrates why unqualified curtailment, battery-autonomy, hydrogen-offtake and stack-lifetime claims cannot be retained from the rejected paper. The control implementation and test suite provide a defensible starting point for an empirical study, but reliable claims of lifetime, NPV and risk improvement require authentic held-out data, external ageing calibration, realistic market assumptions and competitive baseline evaluation.')

head('REFERENCES')
refs=[
'[1] M. Carmo, D. L. Fritz, J. Mergel, and D. Stolten, “A comprehensive review on PEM water electrolysis,” Int. J. Hydrogen Energy, vol. 38, no. 12, pp. 4901–4934, 2013, doi: 10.1016/j.ijhydene.2013.01.151.',
'[2] C. Rakousky et al., “An analysis of degradation phenomena in polymer electrolyte membrane water electrolysis,” J. Power Sources, vol. 326, pp. 120–128, 2016, doi: 10.1016/j.jpowsour.2016.06.082.',
'[3] C. Rakousky et al., “Polymer electrolyte membrane water electrolysis: Restraining degradation in the presence of fluctuating power,” J. Power Sources, 2017, doi: 10.1016/j.jpowsour.2016.11.118.',
'[4] L. Schofield, B. Paren, R. Macdonald, Y. Shao-Horn, and D. Mallapragada, “Dynamic optimization of proton exchange membrane water electrolyzers considering usage-based degradation,” AIChE J., vol. 71, no. 1, e18635, 2025, doi: 10.1002/aic.18635.',
'[5] C. Draxl, A. Clifton, B.-M. Hodge, and J. McCaa, “The Wind Integration National Dataset (WIND) Toolkit,” Appl. Energy, vol. 151, pp. 355–366, 2015, doi: 10.1016/j.apenergy.2015.03.121.',
'[6] T. Haarnoja, A. Zhou, P. Abbeel, and S. Levine, “Soft Actor-Critic: Off-Policy Maximum Entropy Deep Reinforcement Learning with a Stochastic Actor,” in Proc. ICML, vol. 80, pp. 1861–1870, 2018.',
'[7] W. Dabney, M. Rowland, M. G. Bellemare, and R. Munos, “Distributional Reinforcement Learning with Quantile Regression,” in Proc. AAAI Conf. Artif. Intell., 2018.',
'[8] R. T. Rockafellar and S. Uryasev, “Optimization of conditional value-at-risk,” J. Risk, vol. 2, no. 3, pp. 21–41, 2000, doi: 10.21314/JOR.2000.038.',
'[9] Y. Romano, E. Patterson, and E. J. Candès, “Conformalized Quantile Regression,” in Adv. Neural Inf. Process. Syst., vol. 32, 2019.',
'[10] S. Hochreiter and J. Schmidhuber, “Long short-term memory,” Neural Comput., vol. 9, no. 8, pp. 1735–1780, 1997, doi: 10.1162/neco.1997.9.8.1735.',
'[11] National Laboratory of the Rockies, “NOW-23 North Atlantic Data API,” 2026. [Online]. Available: https://developer.nlr.gov/docs/wind/wind-toolkit/offshore-north-atlantic-download/.',
'[12] Net Zero Atlantic, “Atlantic Canada Offshore Wind Grid Integration and Transmission Study,” Jul. 2026. [Online]. Available: https://netzeroatlantic.ca/atlantic-canada-offshore-wind-grid-integration-and-transmission-study.',
'[13] Nova Scotia Power, “Hourly Total Net Nova Scotia Load,” OASIS archive. [Online]. Available: https://www.nspower.ca/oasis/monthly-reports/hourly-total-net-nova-scotia-load.'
]
for x in refs:p=d.add_paragraph(x,style='Tiny reference')

# footer page number
footer=d.sections[0].footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.RIGHT
r=footer.add_run('Research revision — empirical results pending   |   ');r.font.size=Pt(7)
fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');footer._p.append(fld)

# reasonable metadata
d.core_properties.title='Forecast-Informed Hierarchical Reinforcement Learning for Degradation-Constrained Offshore Wind-Hydrogen Dispatch'
d.core_properties.subject='Reviewer-driven technical rewrite; not a validated empirical submission'
d.core_properties.keywords='hydrogen; electrolyzer; renewable wind; reinforcement learning; IEEE'
OUT.parent.mkdir(exist_ok=True);d.save(OUT)
print('Created',OUT,'bytes',OUT.stat().st_size)
