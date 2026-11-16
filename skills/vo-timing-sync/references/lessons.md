# Lessons from building and testing vo-timing-sync

Tested on two real Thai voice-overs for a daily football-news video (a 54 s short and a 179 s long clip).

- **Short clip (4 paragraphs):** the three paragraph breaks were found with no warnings and matched the hand-picked breaks exactly (8.55 s, 22.69 s, 41.43 s).
- **Long clip (8 paragraphs):** automatic choice of paragraph breaks was wrong for 2 of 7 breaks (off by about 2-3 s) because a pause inside the intro was as long as the real break. The tool flagged 5 breaks as ambiguous, including both wrong ones. With the break starts supplied by hand, scene starts matched the earlier hand-tuned run to within 0.01 s for 24 of 26 scenes; two differed by 1.6-2.2 s because this version weights all letters, while the earlier one counted consonants only.
- **A recording that does not match the script:** the first take was 40 s; a later take of the same script was 54 s, so the first evidently lacked part of the text. A paragraph duration ratio far from 1, or a total length far below what the text predicts, is the signal. Raise it with the user instead of fitting. This check was not run on the first take at the time, so how reliably it would have flagged it is untested.
- **Short scenes** (under about 2 s) are the least reliable; merge them into a neighbour when possible.
- The final scene of a video should keep showing for 2+ seconds after the speech ends.
