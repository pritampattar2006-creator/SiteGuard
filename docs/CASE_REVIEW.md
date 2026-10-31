# Case review: 11 real site photos, checked by eye

Photos supplied by the team (`eval/cases/`, mapping in `eval/cases/MAPPING.txt`). Annotated results: `outputs/cases/`.

**Method (three passes).**
1. Run the system on every photo and look at each annotated result.
2. Look at each original photo and write down what is actually true for every worker I could judge clearly, then compare.
3. Re-inspect every disagreement, fix what was a logic fault, re-run all 11 photos and look again.

"Judgeable" workers are those a person can clearly assess by eye (large enough, not hidden). Tiny, cut-off or crowded workers were left out of the score.
Truth was written by one reviewer (the assistant); the team should verify it. Treat the numbers as indicative, not a formal benchmark.

## Result after the fixes

| Outcome | Workers | Share |
|---|---|---|
| Correct verdict | 34 | 76% |
| NEEDS_REVIEW where the truth was clear (safe, but not decisive) | 9 | 20% |
| Wrong verdict | 2 | 4% |
| **Total judgeable** | **45** | |

Among decisive verdicts (excluding NEEDS_REVIEW): 34 of 36 correct, 94%.
Before the fixes, 3 workers were wrong, including a false pass.

## Per case

| Case | Scene | Judgeable | Correct | Review | Wrong | Notes |
|---|---|---|---|---|---|---|
| 01 | Busy site, many small workers | 3 | 2 | 1 | 0 | Two workers without vests found. Foreground carrier with no vest left as REVIEW (cut off at the bottom) |
| 02 | Seated workers, helmet on a table | 4 | 3 | 1 | 0 | **Helmet on the table not credited.** Both seated bare-headed workers flagged NO HELMET |
| 03 | Seated workers, helmet on a table | 5 | 3 | 2 | 0 | Helmet on the table left unassigned. The two seated workers are REVIEW (seated pose), not credited |
| 04 | Two workers holding helmets in hand | 5 | 5 | 0 | 0 | **Helmets in hand not credited.** Both flagged NO HELMET. One far-left worker missed |
| 05 | Fully equipped worker plus a distant one | 2 | 2 | 0 | 0 | Both OK |
| 06 | Workers in beanie and cap | 4 | 2 | 1 | 1 | Beanie not taken as a helmet. **Wrong:** bending worker in a vest flagged NO VEST. Two workers missed at the edge |
| 07 | Crowded road works | 3 | 2 | 0 | 1 | **Fixed:** beanie worker was a false OK, now NO HELMET. **Wrong:** a baseball cap is taken as a helmet |
| 08 | Brick site, nobody wearing PPE | 5 | 4 | 1 | 0 | Cap not taken as a helmet. Seated worker gets a duplicate partial box (REVIEW) |
| 09 | Brick site, two helmets, no vests | 4 | 3 | 1 | 0 | Worker with yellow helmet and no vest left as REVIEW |
| 10 | Workers without PPE, saris and head cloths | 6 | 5 | 1 | 0 | Head cloths not taken as helmets |
| 11 | Hi-vis site | 4 | 3 | 1 | 0 | Grey-shirt worker without a vest left as REVIEW. Orange hi-vis shirts counted as vests (rule not decided) |

## Case 12 (added later): indoor lab, three people in black polo shirts

| Case | Scene | Result |
|---|---|---|
| 12 | Indoor lab, not a construction site | Two of three people detected (the third is half hidden by a monitor). Both flagged NO HELMET + NO VEST, which is what the rule says. **The system does not know that PPE is not required in a lab**: it applies the rule to every person it sees |

## Accuracy modes tested on all 314 held-out photos (AP@0.5, higher is better)

| Mode | Person | Helmet | Vest | Speed |
|---|---|---|---|---|
| Before: one model, tiles | 0.868 | 0.924 | 0.864 | 0.16 s per photo |
| Ensemble (2 models + flip/rescale), tiles off | 0.891 | 0.910 | 0.882 | 0.18 s |
| Ensemble, tiles on | 0.847 | 0.920 | 0.892 | 0.68 s |

The benchmark gain is small. **On the real photos the ensemble was worse in one way that matters:** in case 7 both models read the foreground worker's knitted beanie as a helmet, so averaging them
made a false pass come back (helmet 0.41). Balanced (one model plus tiles) stays the default. Ensemble is available as an experimental option.
The fix for cap, beanie and hi-vis look-alikes is training photos of those, not more models.

## Model v3: a `head` class (bare or covered head with no helmet)

Trained 25 epochs from v2 on the merged data with a fourth class, `head` (Construction-PPE `no_helmet` plus CHVG `head`; 982 training boxes), so a cap, beanie or head cloth has an
explanation other than "helmet". Where a head is more convincing than a helmet on the same head, the helmet is cancelled and the worker is a clear NO HELMET.

Held-out photos, 314 (AP@0.5, one pass, no tiles):

| Model | Person | Helmet | Vest | Head |
|---|---|---|---|---|
| v2 | 0.879 | 0.906 | 0.864 | none |
| **v3** | **0.895** | **0.909** | **0.867** | 0.680 (precision 0.80, recall 0.62) |

On the 12 real photos (counts: workers / OK / violation / review): v3 gave more definite verdicts and found more workers in the crowded photos. Case 3's seated workers are now violations
instead of review; the fully equipped workers in cases 5 and 11 are unchanged (no new false violations); the beanie worker in case 7 is still caught.
**Still wrong:** the baseball cap in case 7 passes as a helmet (helmet score 0.32, just above the 0.30 threshold, and no head was detected on it). Hi-vis shirts and life jackets still pass as vests.
The real-photo review for v3 was by eye on counts and on the images above, not a new per-worker answer key.

## Further fix from this round

7. **Vest "cannot be verified" when only the legs were cut off: FIXED.** A worker touching the bottom of the photo is now only "torso cut off" when their box is short for its width
   (`torso_min_aspect`); a worker cut off at the knees keeps a judgeable vest. Three new unit tests.

## Faults found and what was done

1. **False pass (case 7): FIXED.** An oversized person box swallowed a neighbour's helmet at its edge, so a bare-headed worker was credited.
   A helmet must now sit in the middle of the worker's box sideways (`head_x_margin`). Two new unit tests cover it.
2. **Seated workers' vests not matched (case 3): FIXED.** The torso zone now reaches 75% down the box (was 65%).
3. **Baseball cap taken as a helmet (case 7): NOT FIXED.** A model fault. Needs hard-negative training photos of caps and beanies.
4. **Bending worker's vest missed (case 6): NOT FIXED.** The vest was not detected.
5. **Small, background and edge workers missed (cases 4, 6, 8, 9): NOT FIXED.** About 8 to 10 clearly visible workers across the set. Zoomed tiling helps but does not catch them all.
6. **Bystanders are treated as workers (case 2):** a pedestrian was flagged. The system cannot tell a worker from a passer-by.
7. **Seated pose often becomes REVIEW** (cases 3, 8): safe, but it should be a violation.

## Hard cases from the problem statement

| Hard case | Seen in | Result |
|---|---|---|
| Helmet placed on a table | cases 2, 3 | Not credited to anyone |
| Helmet held in hand | case 4 | Not credited; both workers flagged |
| Hi-vis clothing that is not a vest | cases 6, 11 | Not solved: the model counts hi-vis shirts as vests |
| Cap or beanie instead of a helmet | cases 6, 7, 8, 10 | Mostly right; one cap wrongly accepted |
