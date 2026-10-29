# Synthetic RapidAPI test responses

These files are invented fixtures shaped according to the provider's documented API v2 as inspected on 2026-10-29. They are not downloaded match results and do not represent real athletes or tournaments. Demo storage is isolated in runs/api_demo and must never be merged with live API data or the historical dataset.

Two pages cover one completed main-draw match, one retirement, one main-draw match missing best_of, one Challenger and one qualifying match. Statistics are coherent invented counts; empty objects represent unavailable stats. Expected discovery: 3 stored, 2 excluded; expected analysis: 2 retained, 1 quarantined for missing best_of.

Provider references: https://docs.tennis-api.com/results and https://docs.tennis-api.com/getting-started. These fixtures test the adapter contract; they do not prove the authenticated live service conforms to its public documentation.
