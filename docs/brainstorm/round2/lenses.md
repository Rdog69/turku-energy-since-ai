# Round 2 angles (one per advisor)

## kimi-k3.1-pro: Scoring mathematician
Treat this as **four separate optimisation problems scored relative to the best team**, with `score.py` as the exact objective. For each metric (MAE of p50, mean pinball of p10/p90, mean Brier of the two spike probabilities, three-class Brier of direction), work out where the cheapest points are. Cover: decision-theoretic optimal outputs given a predictive distribution (e.g. the optimal p50 under MAE for a bimodal mixture; whether to shrink probabilities under drift); post-processing and blending across models, steps and origins; per-step or per-band selection; how validation noise (one volatile month) should change our choices; and how the relative-to-best formula changes what to prioritise. Use numbers from the files.

## kimi-k3: Nordic balancing-market insider
Think like a Fingrid control-room operator and a Nordic mFRR trader. Explain the **mechanisms** behind imbalance prices that a pure ML team would miss:
- How the Nordic mFRR energy activation market and the 15-minute products work
- Scheduled versus direct activation
- Hour and quarter boundaries, and intraday gate closure
- Why SE1 often shares Finland's mFRR price, and what congestion between FI and SE1 means
- How BRPs' intraday trading reacts to wind forecast updates
- What the patterns in the attached volatile day reveal

Turn each mechanism into a **concrete, availability-safe feature or model structure**, and say which metric it moves.

## deepseek-v4.1-flash: Data detective
You have real rows in `data_samples.md` (a volatile day, a calm day, per-series statistics, freshness at an origin) plus the schema. Hunt for **exploitable regularities in the package data itself** that a standard feature set would miss. Candidates include:
- Relationships between columns (mFRR prices, activated MW, aFRR sparsity, flows, neighbour prices)
- Signatures that precede up/down switches or spikes
- Missingness patterns
- Calendar or DST effects
- Interactions of the net position with time of day

For each regularity, give the exact pandas feature definition that respects `first_usable_origin_utc`, and a check that tests it on training data.

## glm-5.3: Red team and contrarian
**Attack the round-1 consensus.**
- Where will the mixture-plus-LightGBM design fail on the **October test period**, given that the validation month is September? Think about drift, DST on 25 Oct, the first cold snaps or icing, lower solar, different wind regimes, and the up share dropping to 25 % in early October.
- What radically different approach could beat it, or should be **ensembled** with it as a hedge? For example analog or k-NN forecasting on the day-ahead context, quantile regression forests or distributional boosting, a small sequence model, or a rules-based mechanistic model.
- Design the **validation protocol** that would tell us which to trust, given only June–early October data.
