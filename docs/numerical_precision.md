# Numerical precision policy

Release 1.1 fixes calculation-interface precision at 12 decimal places for normalized detection scores, missingness values, active fractions, and edge probabilities. This is part of the published method, not an accidental display conversion.

The pipeline follows these boundaries:

- reviewed amounts and integer counts retain their source precision;
- normalized probabilities and fractions are serialized to 12 decimal places before crossing from one audited calculation stage to the next;
- downstream stages consume those sealed 12-decimal values so a clean-room rebuild is stable across supported Python versions;
- general monetary outputs retain six decimal places where fractions of one HS are analytically meaningful;
- paper-facing monetary values are rounded to whole HS unless the paper explicitly prints more precision.

The maximum difference between this fixed-interface convention and carrying binary floating-point values without an interface boundary is far below one HS in the release benchmarks. Tests lock both the convention and the published values.
