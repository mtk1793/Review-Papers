# Source provenance

## Published physical-controller source

- Publication: M. M. Kiasari and H. H. Aly, “A proposed controller for real-time management of electrical vehicle battery fleet with MATLAB/SIMULINK,” *Journal of Energy Storage*, vol. 99, Art. no. 113235, 2024, doi: 10.1016/j.est.2024.113235.
- Canonical Google Drive project: `Real-Time Management of Electrical Vehicle Battery Fleet`
- Drive folder ID: `1UMhuKAKuoY3a81MR54xX0MZn2Yyxtz1y`
- Original source model in Drive: `V2GStronge2.slx`, file ID `1V1aWh8bRkMOjcurfNWiJVzjA0oTGMztM`
- Preserved package snapshot: `source_artifacts/V2GStronge2_published_controller.slx`
- SHA-256 of preserved SLX: `de77e22a82e73e3d09bb7fa6f9a565807678be171c3a931986e919ed3403250f`
- Historical manuscript snapshot: `source_artifacts/Published_Controller_Working_Manuscript.docx`

## What was carried into Python

The Python study reconstructs the *supervisory* concepts documented in the publication and source artifact: owner participation policy, minimum SOC protection, EV connection/availability, previous-day Q1/Q3 load thresholds, G2V/V2G/Idle state selection, charger power limits, and SOC energy balance.

## What was not claimed

The Python digital twin is not a switching-level conversion of the 10-kHz Simulink power-electronic model. The reported results do not claim electromagnetic-transient equivalence, harmonic equivalence, power-flow validation, transformer thermal validation, or HIL validation.
