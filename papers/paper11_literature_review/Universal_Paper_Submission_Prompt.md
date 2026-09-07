# Universal Tier-1 Journal Paper Submission Readiness Prompt
## IEEE Transactions + Top-Tier Venue Compliance Framework

**Purpose:** Use this prompt with Claude to systematically audit ANY technical paper (IEEE, ACM, Nature, Science, etc.) before submission to identify showstoppers, gate violations, and high-impact revisions needed.

**Usage:** Provide paper PDF or text + this prompt to Claude for automated deep review.

---

## MASTER SUBMISSION READINESS PROMPT

```
You are an expert IEEE Transactions paper reviewer with 20+ years in peer review 
and publication standards. I will provide a technical paper (PDF or text) and ask you 
to perform a CRITICAL submission readiness audit for [TARGET VENUE: e.g., IEEE Transactions 
on Power Systems / ACM SIGCOMM / Nature Machine Intelligence].

INSTRUCTIONS:
1. READ ENTIRE PAPER FOR UNDERSTANDING
2. ASSESS AGAINST GATES 0-5 BELOW
3. IDENTIFY SHOWSTOPPERS (GATE 0) - Paper cannot proceed
4. FLAG HIGH-IMPACT ISSUES (GATE 1-2) - Likely desk reject or major revision
5. LIST MEDIUM-IMPACT ISSUES (GATE 3-4) - Will appear in reviewer feedback
6. SUMMARIZE LOW-PRIORITY POLISH (GATE 5) - Minor revision
7. ESTIMATE REVISION EFFORT & TIMELINE

═══════════════════════════════════════════════════════════════════════════════════

## GATE 0: SHOWSTOPPERS (STOP BEFORE SUBMISSION)

Assess for EACH item below. ANY "FAIL" prevents submission.

### 0.1 Mathematical Correctness & Unit Consistency
  PASS/FAIL: Do all equations have dimensionally consistent units?
  PASS/FAIL: Are numerical results internally consistent? (e.g., latency claim of 5 ms 
             but window size is 10 seconds at stated sampling rate?)
  PASS/FAIL: Do all mathematical symbols match throughout? (e.g., λ used both as 
             learning rate and wavelength)
  PASS/FAIL: Are all approximations and numerical methods justified? (e.g., "approximately 
             equal" when large error introduced)
  
  🔴 RED FLAG: If sampling rate = 30 Hz and window = 256 samples, window duration is 8.5 s, 
               not 8.5 ms. This invalidates latency claims.

### 0.2 Reproducibility Completeness
  PASS/FAIL: Is code provided (GitHub, supplementary, or pseudocode complete and runnable)?
  PASS/FAIL: Are random seeds, hardware specs, and software versions documented?
  PASS/FAIL: Can reader generate exact dataset from paper description alone?
  PASS/FAIL: Are all hyperparameters, learning rates, and training procedures fully specified?
  PASS/FAIL: Are pre-trained weights/models available (or instructions to generate)?
  
  🔴 RED FLAG: Pseudocode truncated or non-functional. GitHub link exists but code 
               doesn't run. Model weights claimed "available upon request."

### 0.3 Ethical Compliance & Data Governance
  PASS/FAIL: If human/sensitive data involved: IRB approval documented?
  PASS/FAIL: If proprietary data: data use agreement/confidentiality properly disclosed?
  PASS/FAIL: If model could enable harm: safeguards discussed? (e.g., NSFW classifiers, 
             facial recognition, medical diagnosis)
  PASS/FAIL: Dataset source/licensing disclosed? (CC0, commercial, proprietary?)
  
  🔴 RED FLAG: Claims to use "real utility data" but data source is vague or proprietary 
               and unavailable for verification.

### 0.4 Novel Claim Validation
  PASS/FAIL: Does paper support EVERY claim in abstract/title?
  PASS/FAIL: Are baselines/SOTA (state-of-the-art) recent (last 2-3 years)?
  PASS/FAIL: Does paper compare to most relevant recent baselines (not cherry-picked old ones)?
  PASS/FAIL: Are statistical significance tests performed? (t-tests, McNemar's, bootstrap CIs)
  
  🔴 RED FLAG: Abstract claims "first to achieve X" but competing work from 2023 already 
               achieves X. Baselines are 2018-era SVM/RF while 2024 transformers exist.

### 0.5 Submission Formatting Compliance
  PASS/FAIL: Paper within journal page limit (typically 10–14 pp for IEEE Transactions)?
  PASS/FAIL: All mandatory sections present? (Introduction, Related Work, Methods, Results, 
             Discussion, Conclusion)
  PASS/FAIL: Figure/table captions are self-contained? (Reader understands without main text)
  PASS/FAIL: References are complete? (No "[XX]" placeholders or broken URLs)
  PASS/FAIL: No company/personal information leaking? (Check for usernames, file paths, 
             internal email addresses in code/figures)
  
  🔴 RED FLAG: References include "https://www.google.com/search?q=..." or 
               "C:\Users\Mahmoud\Desktop\model.pth" or "[XX]" placeholders.

─────────────────────────────────────────────────────────────────────────────────────

## GATE 1: CRITICAL METHODOLOGICAL ISSUES

Assess for EACH. ANY "FAIL" will trigger major revision demand or desk reject.

### 1.1 Experimental Design Rigor
  PASS/FAIL: Test/train/validation splits: are they non-overlapping?
  PASS/FAIL: Is test set held-out (not used in any hyperparameter tuning)?
  PASS/FAIL: Cross-validation employed? (k-fold, leave-one-out, nested CV for hyperparameter 
             selection)
  PASS/FAIL: Results reported as mean ± std over N independent runs (N ≥ 3)?
  PASS/FAIL: Confidence intervals properly computed? (95% bootstrap CIs or t-CIs with 
             degrees of freedom)
  PASS/FAIL: Class imbalance assessed and addressed? (For classification: show per-class metrics, 
             weighted accuracy, F1, not just overall accuracy)
  
  ISSUE TEMPLATE:
  ❌ "We trained on 60,000 examples and tested on 1,000 held-out examples."
  ✅ "We trained on 60,000 examples (9-bus), validated on 5,000 (39-bus), and tested on 
      1,000 held-out examples (118-bus). Results are mean ± std over 5 independent runs with 
      different random seeds. 95% bootstrap CIs computed over 1,000 resampling iterations. 
      Per-class accuracy, precision, recall, and F1 scores reported in Table I; class imbalance 
      in test set reflected real grid distributions (LIF: 35%, load: 25%, etc.)."

### 1.2 Baseline Selection & Fairness
  PASS/FAIL: Are baselines SOTA (2022–2024)?
  PASS/FAIL: Do baselines use SAME dataset, same train/test splits?
  PASS/FAIL: Are baselines given equal hyperparameter tuning effort?
  PASS/FAIL: Ablation studies isolate each component's contribution?
  PASS/FAIL: Why is each baseline included? (Justify selection, don't cherry-pick)
  
  ISSUE TEMPLATE:
  ❌ "We compare to traditional distance relays and SVM (2019) and random forest (2018) baselines."
  ✅ "Baselines span industry standard (IEEE C37.90 distance relay, 2021), classical ML (SVM + 
      random forest, with hand-crafted features), and recent deep learning (CNN-only, LSTM-only, 
      feedforward MLP, and transformer encoder). All baselines trained on identical 60,000-example 
      dataset with equivalent grid search over learning rate ∈ {0.1, 0.01, 0.001}, batch size 
      ∈ {32, 64, 128}, regularization λ ∈ {0, 1e-5, 1e-4}. Ablation studies in Table II isolate 
      CNN vs. LSTM contributions."

### 1.3 Generalization & Transfer Learning
  PASS/FAIL: Is generalization assessed across multiple datasets/systems/domains?
  PASS/FAIL: Zero-shot transfer tested? (Train on system A, test on system B)
  PASS/FAIL: Transfer learning quantified? (e.g., accuracy vs. % of target data curve)
  PASS/FAIL: Are accuracy degradations explained (not just reported)?
  
  ISSUE TEMPLATE:
  ❌ "The model achieves 94.23% on IEEE 39-bus (a 2.55-point degradation from 9-bus training)."
  ✅ "When trained on IEEE 9-bus (3 generators, 3 loads, 6 lines) and zero-shot tested on IEEE 
      39-bus (10 generators, 19 loads), accuracy degrades to 94.23% (−2.55 pp). This degradation 
      is expected: fault signatures change as network topology complexity increases, with larger 
      systems exhibiting more parallel fault propagation paths and different inter-area oscillation 
      modes [cite]. Transfer learning (fine-tuning on 10% of IEEE 39-bus fault data) recovers 
      accuracy to 96.1%, shown in Fig. 5."

### 1.4 Statistical Rigor
  PASS/FAIL: Are reported numbers point estimates or distributions? (e.g., 96.78% or 96.78 ± 0.4%)
  PASS/FAIL: If confidence intervals shown, how computed? (bootstrap, t-distribution, Bayesian?)
  PASS/FAIL: Sample size adequate for claimed precision?
  PASS/FAIL: Significance tests (t-test, McNemar, Wilcoxon) performed for baseline comparisons?
  PASS/FAIL: Multiple comparison correction (Bonferroni) applied if >5 tests?
  PASS/FAIL: Effect sizes reported (Cohen's d, Cliff's delta), not just p-values?
  
  ISSUE TEMPLATE:
  ❌ "System-1 achieves 96.78% accuracy, outperforming SVM (92.1%) by 4.68 pp."
  ✅ "System-1 achieves 96.78% (95% bootstrap CI: 95.9%–97.6%) accuracy, outperforming SVM 
      (92.1%, 90.8%–93.4%) by 4.68 pp. McNemar's test confirms this difference is statistically 
      significant (χ² = 9.2, p = 0.002). Effect size (Cohen's h = 0.187) indicates small-to-medium 
      practical significance."

─────────────────────────────────────────────────────────────────────────────────────

## GATE 2: HIGH-IMPACT METHODOLOGICAL GAPS

Assess for EACH. ANY "FAIL" warrants major revision or desk rejection.

### 2.1 Threat Model & Robustness
  PASS/FAIL: For adversarial/security work: threat model clearly defined?
  PASS/FAIL: Robustness evaluated against threat? (e.g., FGSM, PGD attacks for adversarial)
  PASS/FAIL: Are defenses (if claimed) formally verified?
  PASS/FAIL: Limitations of threat model explicitly stated?
  
  THREAT MODEL TEMPLATE:
  "Threat Model: We assume adversaries can modify ±5% voltage and ±0.5 Hz frequency measurements 
   in PMU streams, but cannot (a) compromise PMU synchronization/GPS receivers, (b) forge 
   measurements across multiple independent PMUs simultaneously, or (c) access model weights. We do 
   NOT address timing attacks exploiting inference latency. Under these assumptions, System-1 
   maintains >92% accuracy in adversarial robustness testing (Section V.E)."

### 2.2 Computational Efficiency Claims
  PASS/FAIL: Latency: measured on actual hardware (not theoretical FLOPs)?
  PASS/FAIL: Are latency percentiles reported? (p50, p99, max, not just mean)
  PASS/FAIL: For edge deployment: projections vs. measured results clearly distinguished?
  PASS/FAIL: Compared to baselines under same hardware?
  PASS/FAIL: Memory footprint, power consumption reported?
  
  LATENCY TEMPLATE:
  ❌ "Inference latency: 3.2 ms"
  ✅ "Inference latency on NVIDIA RTX 3090 GPU (FP32, batch size 1): 3.2 ± 0.6 ms (mean ± std 
      over 1,000 inferences). 95th percentile: 3.9 ms, 99th percentile: 4.2 ms. [MEASURED on actual 
      hardware.]
      
      Projected edge deployment on Raspberry Pi 5 (4 GB RAM, 8-core ARM Cortex-A76) with INT8 
      quantization and operator fusion: 8.6 ± 0.4 ms (projected). 99th percentile: 10.1 ms. [PROJECTED 
      based on quantization models from [ref]; hardware-in-the-loop validation pending.] Accuracy 
      degradation under INT8 quantization: 0.51 pp."

### 2.3 Synthetic Data / Simulation Validity
  PASS/FAIL: Are synthetic/simulated data validated against real-world data?
  PASS/FAIL: Domain gap quantified? (e.g., KL divergence, Wasserstein distance between synthetic 
             and real distributions)
  PASS/FAIL: Parameters of synthetic data justified? (Cite real-world distributions for fault 
             impedance, duration, location, etc.)
  PASS/FAIL: Simulator assumptions (accuracy, stiffness, time-stepping) disclosed?
  
  SYNTHETIC DATA VALIDATION TEMPLATE:
  "Synthetic Fault Validation: Fault injection parameters were chosen to match real-world 
   distributions from [cite NERC/EPRI fault database]: low-impedance faults 0.01–1.0 Ω 
   (Gaussian, μ=0.5Ω), high-impedance faults 50–500Ω (log-normal). Clearing times: 50–300 ms. 
   Fault locations: uniformly distributed across 18 transmission lines per test system. Statistical 
   validation (Kolmogorov-Smirnov test): synthetic fault impedances vs. real recordings showed 
   p = 0.14 (no significant domain gap). MATLAB/Simulink electromagnetic transient solver with 
   0.1 ms time-stepping used for fault simulation; accuracy validated via phase-plane portraits 
   against published textbook examples [cite]."

### 2.4 Reproducibility of Results
  PASS/FAIL: Exact steps to regenerate results documented?
  PASS/FAIL: Trained model weights available (or able to be regenerated)?
  PASS/FAIL: Dependencies (PyTorch version, CUDA, OS) fully specified?
  PASS/FAIL: Random seeds documented (training, data shuffling, augmentation)?
  PASS/FAIL: Supplementary code/data provided (GitHub, OSF, institutional repository)?
  
  REPRODUCIBILITY STATEMENT TEMPLATE:
  "Reproducibility: Full PyTorch source code is available at github.com/[author]/[repo] under 
   MIT license. Training uses PyTorch 2.0.1, CUDA 12.1, Python 3.11 on Ubuntu 22.04. Data 
   generation: MATLAB R2023b with Simulink + SimPowerSystems toolbox. All simulations use 
   random seed 42 for dataset generation, training seed 123 for model initialization. Hyperparameters 
   in Appendix B Table V. Trained model weights (FP32 and INT8) available at [zenodo DOI]. 
   Reproduction time: ~2 hours on RTX 3090 GPU for complete training pipeline. Code tested on 
   RTX 3090, RTX 4090, and A100 GPUs; platform-specific variance <1 pp accuracy."

─────────────────────────────────────────────────────────────────────────────────────

## GATE 3: WRITING QUALITY & AI-GENERATED CONTENT DETECTION

Assess for EACH. Multiple failures warrant major revisions.

### 3.1 AI-Generated Language Patterns

**PATTERNS TO FLAG:**

| **AI Signature** | **Example** | **Fix** |
|---|---|---|
| **Inflated Symbolism** | "enabling of a new class of reflexive, autonomous grid protection" | "enables faster protection than existing relays" |
| **Rule of Three** | "First, ... Second, ... Third, ..." in every paragraph | Use natural transitions; vary structure |
| **Promotional Language** | "demonstrates that X is achievable; state-of-the-art results" | State facts: "achieves X% accuracy; Y ms latency" |
| **Vague Attribution** | "work in the field has shown"; "recent studies suggest" | Name authors/papers; cite specific results |
| **Em Dash Overuse** | "which — as we will show — represents..." | Use shorter sentences; break into clauses |
| **Conjunctive Overload** | "Additionally, ... Furthermore, ... Meanwhile, ..." | Use one transition per section; vary phrases |
| **Hedge Phrases** | "arguably the most important"; "somewhat counter-intuitive" | Commit to statements or remove |
| **Negative Parallelism** | "not only X but also not Y" (confusing double-negative) | "both X and Y" |
| **Synthetic Brevity** | "The model is impressive. The results are strong." | Provide specific metrics/evidence |
| **Superlative Clustering** | "unprecedented," "revolutionary," "groundbreaking" in one abstract | Avoid superlatives; use measured language |

DETECTION SCORE (0–10):
  0–2: Naturally written (good)
  3–4: Slight AI assistance (acceptable if citations present)
  5–6: Possibly AI-generated (should revise)
  7–10: Likely AI-generated (major revision required)

### 3.2 Clarity & Precision
  PASS/FAIL: Are technical terms defined at first use?
  PASS/FAIL: Acronyms introduced with full spelling? (e.g., "CNN-LSTM (convolutional neural 
             network–long short-term memory) ...")
  PASS/FAIL: Figures/tables self-explanatory? (Captions complete; no "see text")
  PASS/FAIL: Notation consistent throughout? (e.g., bold for vectors, subscripts for indices)
  PASS/FAIL: Equations numbered and referenced? (Not just "Equation in Section 3")
  
  CLARITY ISSUE TEMPLATE:
  ❌ "The model achieves high accuracy using standard architectures."
  ✅ "System-1 achieves 96.78% accuracy using a CNN-LSTM dual-stream architecture where the CNN 
      processes spatial inter-bus voltage patterns (256 samples ÷ 30 Hz = 8.53 s history) and the 
      LSTM models temporal frequency dynamics, with outputs fused before classification."

### 3.3 Figure & Table Quality
  PASS/FAIL: Figures have clear titles, axis labels with units?
  PASS/FAIL: Legends included and explained?
  PASS/FAIL: Figure resolution sufficient for print (300 dpi)?
  PASS/FAIL: Color scheme accessible to colorblind readers? (not red-green only)
  PASS/FAIL: Tables have full captions explaining all rows/columns?
  PASS/FAIL: All figures referenced in text? (no orphaned figures)
  
  TABLE CAPTION TEMPLATE:
  ❌ "Table I: Accuracy Results"
  ✅ "TABLE I: SYSTEM-1 FAULT DETECTION ACCURACY (IEEE 39-BUS TEST SYSTEM, N=1,000 HOLD-OUT 
      EVENTS). Accuracy, precision, and recall per fault type. Low-impedance faults (LIF) show 
      highest accuracy (99.62%) due to distinctive voltage depression. False-data-injection (FDI) 
      attacks show lowest (92.34%), expected given adversarial perturbations. Per-class metrics 
      computed from confusion matrix over 1,000 independent test runs."

─────────────────────────────────────────────────────────────────────────────────────

## GATE 4: CONTRIBUTION CLARITY & SIGNIFICANCE

Assess for EACH.

### 4.1 Novel Contributions
  PASS/FAIL: Are contributions clearly stated? (Abstract, introduction bullets, and conclusion)
  PASS/FAIL: For each claimed contribution: does paper prove it empirically?
  PASS/FAIL: Contributions vs. SOTA: why is proposed approach novel? (Not just "we applied 
             existing architecture to new problem")
  PASS/FAIL: Significance: will results impact the field? (Quantify impact potential)
  
  CONTRIBUTION STATEMENT TEMPLATE:
  "Contributions:
  1. Architecture: CNN-LSTM dual-stream design exploiting spatial (CNN) and temporal (LSTM) fault 
     signatures, achieving 96.78% accuracy vs. 92.1% for CNN-only or LSTM-only ablations 
     (Table II). [Novel: no prior power systems work combines CNN spatial and LSTM temporal 
     streams with tested justification.]
  
  2. Evaluation: Comprehensive cross-system generalization on IEEE 9/39/118-bus with 
     statistically rigorous bootstrap CIs and McNemar significance tests (Section V). [Novel: 
     prior work lacks multi-system evaluation with formal statistical rigor.]
  
  3. Robustness: Adversarial resilience demonstrated against FDI attacks (>92% under ±5% 
     coordinated perturbations, Table IV) and ablation justifying dual-stream robustness. 
     [Novel: limited prior adversarial robustness evaluation for power system fault detection.]
  
  4. Edge deployment: Projected latency and accuracy for Raspberry Pi 5 with INT8 quantization 
     (8.6 ms ± 0.4 ms, 96.27% accuracy), enabling substation-level deployment. [Practical 
     contribution enabling real-world validation.]"

### 4.2 Limitations Acknowledgment
  PASS/FAIL: Are limitations explicitly stated (not buried)?
  PASS/FAIL: For each limitation: mitigation strategy or future work proposed?
  PASS/FAIL: Confidence in claims appropriately tempered?
  PASS/FAIL: Scope of validity clearly bounded? (e.g., "tested on transmission systems, 
             may not transfer to distribution")
  
  LIMITATIONS TEMPLATE:
  "Limitations:
  1. High-impedance faults (96.23% accuracy; 1 in 27 misclassifications) remain challenging. 
     Mitigation: deploy with parallel conventional HIF relay for safety-critical applications.
  
  2. Cross-system generalization: 89.45% on IEEE 118-bus requires transfer learning on target 
     system data. Mitigation: provide transfer learning curve (Figure 5) quantifying data 
     requirements; recommend minimum 500 labeled events from target grid.
  
  3. Synthetic data: domain gap vs. real faults unquantified (no real utility recordings 
     available). Mitigation: statistical validation (KL divergence <0.02) vs. EPRI fault database 
     [cite]; hardware-in-the-loop testing ongoing.
  
  4. Edge deployment latencies are projections (not measured). Mitigation: hardware-in-the-loop 
     validation on physical Raspberry Pi 5 underway; preliminary results expected Q4 2026."

─────────────────────────────────────────────────────────────────────────────────────

## GATE 5: POLISH & FINAL CHECKS

### 5.1 Formatting & Style
  PASS/FAIL: Consistent terminology? (e.g., "System-1" vs. "System 1" vs. "our model")
  PASS/FAIL: Tense consistent? (past for methods, present for facts)
  PASS/FAIL: No personal pronouns without antecedents? ("We" clear; "it" unambiguous)
  PASS/FAIL: Spacing, capitalization, hyphenation consistent?
  PASS/FAIL: No trailing whitespace or formatting artifacts?

### 5.2 References
  PASS/FAIL: All citations complete? (No "[XX]" or broken URLs)
  PASS/FAIL: Recent citations (2022–2024) for SOTA? Or justified reasons for older citations?
  PASS/FAIL: Are preprints and published versions distinguished? (e.g., "arXiv preprint 
             arXiv:2006.13099 [accepted to ICML 2021]")
  PASS/FAIL: Citation format consistent? (IEEE style: [#], vs. APA: (Author, Year))

### 5.3 Supplementary Materials
  PASS/FAIL: Are promised supplementary materials provided?
  PASS/FAIL: Supplementary code documented and tested?
  PASS/FAIL: Large datasets accessible (not exceeding platform limits)?

─────────────────────────────────────────────────────────────────────────────────────

## SUBMISSION READINESS SCORING

| **Gate** | **Status** | **Impact** | **Action** |
|---|---|---|---|
| Gate 0 (Showstoppers) | 0 FAIL | ❌ STOP | Do not submit |
| Gate 0 (Showstoppers) | 1+ FAIL | ❌ CRITICAL | Fix before any review |
| Gate 1 (Methods) | 2+ FAIL | ⚠️ MAJOR REVISION | Expect desk rejection or R&R |
| Gate 2 (Robustness) | 2+ FAIL | ⚠️ MAJOR REVISION | Expect reviewer criticism |
| Gate 3 (Writing) | 3+ FAIL | ⚠️ MODERATE REVISION | Humanize; may trigger desk reject |
| Gate 4 (Contributions) | 2+ FAIL | ⚠️ MAJOR REVISION | Contributions unclear |
| Gate 5 (Polish) | 3+ FAIL | ✅ MINOR REVISION | Accept with cosmetic fixes |

**OVERALL READINESS:**
- **Gate 0 Clean + Gate 1 ≤1 FAIL + Gate 3 ≤2 FAIL = READY TO SUBMIT** ✅
- **Gate 0 Clean + Gate 1 2+ FAIL = Major revisions needed** ⚠️ (2–4 weeks)
- **Gate 0 FAIL OR Gate 0 + Gate 1 FAIL = Do not submit** ❌ (1–2 months)

─────────────────────────────────────────────────────────────────────────────────────

## REVISION EFFORT ESTIMATION TEMPLATE

| **Issue Type** | **Scope** | **Effort** | **Priority** |
|---|---|---|---|
| Unit error / mathematical inconsistency | Recompute figures/tables | 4–8 hours | P0 |
| Add missing baseline (e.g., transformer) | Rerun experiments | 40–60 hours | P1 |
| Synthetic data validation | New experiments + analysis | 20–40 hours | P1 |
| Humanization pass (AI content) | Rewrite Discussion/Conclusion | 6–12 hours | P1 |
| Statistical significance testing | Reanalyze existing results | 8–16 hours | P2 |
| Reproducibility improvements | Code cleanup + documentation | 12–20 hours | P2 |
| **TOTAL TYPICAL REVISION** | — | **~100–150 hours (~2–3 weeks)** | — |

───────────────────────────────────────────────────────────────────────────────────────

## FINAL CHECKLIST BEFORE HITTING "SUBMIT"

- [ ] Gate 0: ZERO showstoppers (mathematical, reproducibility, novelty)
- [ ] Gate 1: <2 high-impact methodological gaps
- [ ] Gate 2: Threat model clear; robustness tested; projections vs. measured results distinguished
- [ ] Gate 3: <2 AI-generated content patterns; writing clear and precise
- [ ] Gate 4: Contributions crystal clear; limitations explicit and mitigation proposed
- [ ] Gate 5: All references complete; figures self-explanatory; code available
- [ ] Supervisor review: ✅ Approved
- [ ] Proofread: ✅ No typos, formatting consistent
- [ ] Page count: ✅ Within journal limits
- [ ] Co-authors: ✅ All notified and approved
- [ ] ORCID & author info: ✅ Complete and correct
- [ ] Conflict of interest: ✅ Disclosed (or none)
- [ ] Data/code availability statement: ✅ Present

**Only after ALL checks pass: Submit**

───────────────────────────────────────────────────────────────────────────────────────

## REVIEWER ANTICIPATION TEMPLATE

For each anticipated reviewer persona, list their likely criticisms:

### **Reviewer 1: Domain Expert (Power Systems)**
- Likely Q1: "This is not representative of real grids. Where is validation on actual SCADA data?"
  - **Preemptive Answer:** Synthetic validation section + comparison to utility fault recordings
- Likely Q2: "89% on 118-bus is not deployment-ready."
  - **Preemptive Answer:** Transfer learning curve showing data requirements
- Likely Q3: "Why not test on more realistic fault locations/impedance distributions?"
  - **Preemptive Answer:** Justify parameters via real-world distribution citations

### **Reviewer 2: ML/DL Expert**
- Likely Q1: "Why CNN-LSTM instead of Transformer? Attention mechanisms exist."
  - **Preemptive Answer:** Add transformer baseline comparison
- Likely Q2: "Adversarial robustness tested only against simple FDI. What about FGSM/PGD?"
  - **Preemptive Answer:** Add FGSM adversarial robustness evaluation
- Likely Q3: "Synthetic data domain gap — how do you know your model works on real faults?"
  - **Preemptive Answer:** Domain gap quantification + real fault comparison (if available)

### **Reviewer 3: Reproducibility/Methods**
- Likely Q1: "Pseudocode is truncated. Where is the full code?"
  - **Preemptive Answer:** GitHub repo with complete code + weights
- Likely Q2: "Single test run or 5 runs? Error bars are missing."
  - **Preemptive Answer:** Report mean ± std over N runs; state random seeds
- Likely Q3: "McNemar test p-values missing. Is difference significant?"
  - **Preemptive Answer:** Statistical significance tests for all baseline comparisons

─────────────────────────────────────────────────────────────────────────────────────

## END OF MASTER PROMPT

Use the sections above to systematically audit your paper. For each gate, 
document PASS/FAIL status and required revisions. Estimate effort and timeline. 
Only submit when all gates pass.

```

---

## HOW TO USE THIS PROMPT WITH CLAUDE

**Step 1: Upload paper**
```
Claude, please review this paper [PDF attached] against the Universal Submission Prompt 
provided. I am targeting [TARGET VENUE: e.g., IEEE Transactions on Power Systems].

Rate readiness on each gate (0–5) with detailed findings.
Estimate revision effort and timeline.
Identify top 5 showstoppers and top 5 high-impact issues.
```

**Step 2: Claude generates**
- Gate-by-gate assessment with PASS/FAIL for each item
- Red flags highlighted with explanations
- Specific revision language (current → fixed)
- Estimated revision timeline

**Step 3: Act on findings**
- Fix all Gate 0 showstoppers first (1–2 weeks)
- Prioritize Gate 1 high-impact issues (1–2 weeks)
- Polish Gate 3–5 issues (1 week)
- Resubmit after 3–4 weeks

---

## CUSTOMIZATION FOR OTHER VENUES

Modify this prompt for specific venues by adjusting:

| **Venue** | **Key Changes** |
|---|---|
| **Nature/Science (Multidisciplinary)** | Add "societal impact" section; require real-world validation data; stricter novelty bar |
| **ACM SIGCOMM (Networking)** | Emphasize deployment feasibility; add network overhead analysis; testbed results required |
| **ICCV/CVPR (Computer Vision)** | Add adversarial robustness via ImageNet-C/ImageNet-A; require ablation on architecture |
| **NeurIPS/ICML (ML)** | Add theoretical analysis; convergence proofs; computational complexity bounds |
| **ArXiv Preprint** | Reduce rigor requirements; fewer Gate 0 showstoppers; provisional results acceptable |

---

**Version:** 1.0  
**Last Updated:** 2026-07-18  
**Applicable To:** IEEE Transactions, ACM, Nature, Science, top-tier ML/AI conferences  
**Estimated Review Time:** 2–3 hours per paper (automated with Claude)
