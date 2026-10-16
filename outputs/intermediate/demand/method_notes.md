# Demand analysis method notes

The core result uses estimated movement records whose origin and destination both match the August 2026 Seoul administrative-dong codebook. Departure codes are matched only to `3|03|4|04|5|05`; HH and HHMM codes are not conflated. Calendar Monday-Friday and Saturday-Sunday contain 22 and 8 observed days respectively, without holiday adjustment.

`cnt` is summed as estimated movements. It is neither a unique-person count nor observed unmet demand. Missing cells are not replaced by zero. Purpose and mode files are alternative classifications and are reported independently. OA-12913 boarding/alighting monthly totals use a different measurement unit and are described independently; no subtraction from mobility estimates is performed. Its lack of a daily axis makes weekday/weekend comparison unsupported.

Demand candidates are the 100 highest distinct-dong internal-Seoul OD-hour cells by OA-22300 weekday-plus-weekend monthly estimated movements. Same-dong movements are retained in `intrazonal_summary.csv`, but are not used as corridor candidates. Bus candidates are the 100 stops with the largest combined 03:00-05:59 monthly boarding and alighting activity. OA-1095 supplies map coordinates where a standard stop ID has one unique coordinate pair. These are demand-side screening candidates only and contain no first-service, transfer, walking, service-calendar, service-gap, or causal conclusion.

No predictive or clustering model is used because the requested descriptive rankings and compositions are directly identifiable from the available aggregates, while a model would add assumptions without a validated outcome target.
