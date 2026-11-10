# A Leakage-Aware CNN–LSTM Framework for Dynamic Power-System Model Validation Under MOD-026 and MOD-033

> Working editorial draft. Source findings are unverified without reproducibility files.

**Status:** Methodological manuscript: proposed protocol only; no new dynamic-model tests

## A Leakage-Aware CNN–LSTM Framework for Dynamic Power-System Model Validation Under MOD-026 and MOD-033

RESEARCH WORKING DRAFT | 10 November 2026

Methodological manuscript: proposed protocol only; no new dynamic-model tests

## Abstract

Dynamic-model validation is a prerequisite for using simulation results in bulk-power-system studies. This manuscript describes a transparent, auditable role for a convolutional neural network–long short-term memory (CNN–LSTM) model in screening disturbances for discrepancies between recorded measurements and simulated system responses. The proposed workflow connects data provenance, clock alignment, event segmentation, engineering features, chronological evaluation, residual attribution, and expert review. It distinguishes requirements associated with NERC MOD-026 from those in MOD-033 and does not imply that machine-learning predictions can replace the applicable standard, generator verification tests, or engineering judgment. An IEEE 39-bus case is specified as the initial reproducible benchmark, with further scalability testing on larger networks. No quantitative improvements, regulatory compliance determinations, or field validation results are claimed. The resulting contribution is a testable validation protocol and an evidence architecture for future empirical study.

## 1. Introduction

Validation of simulation models is necessary because planning conclusions depend on the fidelity of network, generator, excitation, governor, converter, and protection representations. Dynamic traces may diverge from field measurements for reasons that include parameter errors, operating-point mismatch, incomplete plant-controller implementation, missing auxiliary equipment, synchronization errors, or simulation model limitations. A data-driven anomaly detector can help triage these discrepancies, but it cannot independently establish which parameter is wrong or whether a reliability standard has been satisfied. The goal of this paper is to make that narrower and more useful role explicit.

The proposed CNN–LSTM model learns temporal features of the difference between synchronized measurement and simulation traces; a separate engineering review determines whether the flagged event warrants model correction, further testing, or exclusion because its inputs are unreliable. The validation protocol emphasizes falsifiability: the classifier must detect known injected model errors on previously unseen events, maintain acceptable false-alarm rates, and preserve performance across changing operating conditions.

## 2. Regulatory and Engineering Scope

MOD-026 addresses verification of applicable generating-unit excitation control system and plant volt/var control function models and related data; MOD-033 addresses validation of steady-state and dynamic system models under its applicability requirements. The exact version, compliance obligation, implementation date, registration status, and jurisdictional enforceability must be identified before the paper makes a standards claim. Current NERC standards documents are the controlling primary source, not a secondary summary or this paper.

A standards traceability matrix should link each paper assertion to the applicable version, Requirement number, evidence type, and responsible entity. Model discrepancies do not automatically imply noncompliance. Conversely, showing a high correlation between a simulated and measured voltage trace does not necessarily demonstrate that all required model components and conditions have been verified. The scope of this study is the technical screening process that helps engineers select, compare, document, and review meaningful validation events.

## 3. Measurement and Simulation Data

For each disturbance, store immutable metadata: event ID, UTC start and end, measurement type and unit, recording device, sample rate, time-sync status, quality flags, system topology, pre-disturbance voltage and power, generator dispatch, and a cryptographic digest of source traces. Pair the recorded traces with a simulation generated from documented network and dynamic-model versions. Preserve a complete settings manifest, including machine/exciter/governor parameters, plant control limits, and any parameters intentionally perturbed for sensitivity studies.

The event windows should contain a fixed pre-disturbance period, fault or step initiation, and a recovery interval long enough to capture the dominant modes under study. Resample only after anti-alias filtering and check time alignment before computing residuals. Use physical units consistently and document the base MVA for per-unit signals. Store both raw and aligned traces so that future reviewers can reproduce every preprocessing choice.

## 4. Model and Baselines

Let y_meas(t,c) denote the measured signal for channel c, y_sim(t,c) the simulated signal, and e(t,c)=y_meas(t,c)−y_sim(t,c) their aligned residual. The input tensor may concatenate measured, simulated, residual, derivative, and event-mask channels. A one-dimensional CNN extracts local deviation patterns; an LSTM models their progression. Candidate outputs are event-level anomaly probability, physical subsystem likelihood, and a calibrated uncertainty measure.

Baselines should include rule-based RMS and peak-error thresholds, normalized cross correlation, dynamic time warping with bounded alignment, an isolation forest on engineering features, and a smaller temporal neural network. Model capacity must be controlled: an ANN or CNN–LSTM trained on synthetic fault fingerprints may overfit the simulator used to create its labels. The primary question is whether the hybrid model provides useful triage beyond transparent engineering thresholds.

## 5. Chronological and Group-Aware Experimental Design

Split at the event level before feature normalization or window generation. All windows from one event—and closely related repeated perturbations—must remain in one split. To test generalization, hold out operating regimes, disturbance families, generator locations, and at least one network configuration. Use a development set for fitting and hyperparameter selection; reserve a sealed test set for the final comparison. If real fault records are available, distinguish fully measured tests from simulated injection tests and never merge the two in a single headline metric.

A sensitivity matrix should vary exciter time constants, stabilizer gains, plant reactive current response, governor damping, transformer impedance, and event timing. Each intervention must be small enough to remain physically plausible and documented with the original and perturbed parameter values. Accuracy on synthetic labels is not proof of successful field identification; this distinction must appear in every results table.

## 6. Performance Measures and Decision Utility

Report precision, recall, macro-F1, area under the precision-recall curve, false alarms per 100 legitimate events, and calibration for anomaly classification. For trace agreement, use voltage/active-power/reactive-power RMSE, normalized integral absolute error, settling-time mismatch, frequency and damping deviation, and confidence intervals across independent events. Report the fraction of events for which a reviewer reaches the same conclusion with and without the model. Time-to-review and retrieval of the most consequential parameter families are relevant operational metrics.

Use bootstrap confidence intervals resampled over independent events, not overlapping windows, and compare against a preregistered baseline. In a separate robustness suite, vary noise, missing samples, time offsets, controller model mismatch, and dataset shift. The proposed tool should abstain from making a confident recommendation when trace quality or operating-point documentation is inadequate.

## 7. Reproducible IEEE 39-Bus Benchmark

Phase A begins with the IEEE 39-bus New England test system and a pinned case/dynamic model, solved and verified with an independent power-flow program. Record bus data, generator models, dynamic settings, Python environment, random seeds, and the version of each study tool. Phase B applies parameter perturbations and predefined events. Phase C creates paired residual traces and evaluates threshold baselines. Phase D trains and calibrates the CNN–LSTM. Phase E tests transfer to unseen configurations and only then considers larger IEEE networks.

PSS/E-compatible exports or simulations should not be represented as actual PSS/E runs unless there is an engine execution log and output channel file. Training a PyTorch predictor on synthetic traces alone does not constitute validation of the physical PSS/E model. A second simulator or independently implemented power-flow benchmark is needed for cross-tool consistency; field measurements are needed for field verification.

## 8. Limitations and Conclusion

This manuscript defines the experimental protocol and no completed validation outcomes. A useful model must improve error localization without obscuring the original measurement and engineering residuals. Future results should be released with executable scripts, event manifests, measured-data permissions, declared operating conditions, and machine-readable standards mapping. A successful empirical study will show what was detected, on which independent events, at what false-alarm cost, and with which verification method—not merely report a high classifier accuracy.

## References and authoritative documents

NERC, MOD-026-2: Verification of Models and Data for Generator Excitation Control System or Plant Volt/Var Control Functions, version and jurisdiction to be checked against official standards page.

NERC, MOD-033-3: Steady-State and Dynamic System Model Validation, version and jurisdiction to be checked against official standards page.

NERC reliability standards index: https://www.nerc.com/pa/Stand/Pages/ReliabilityStandards.aspx

Specific technical publication references require a fresh bibliography audit before submission.
