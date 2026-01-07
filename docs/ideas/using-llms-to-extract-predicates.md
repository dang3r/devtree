# Design Spec: Using LLMs to Extract Predicates

## Overview

When extracting predicates from summary text, we use a regex to extract K-numbers. This is a simple and effective approach but not perfect.

Some devices have many k_numbers in their summary text. Some of these k_numbers are included because they are related
to the device but aren't predicates.

- K232891 for CARPL AI includes all device_ids for all FDA cleared AI devices
- K202050 for brainlab uses a picture for the device summary including the predicate. Because I only OCR pdfs with minimal text, this means we won't OCR and catch this. Fun one.
- K132742 has two predicates but one has a space in between the K and the number
```text
Quantra, by Hologic Inc., K082483
Volpara, Matakina Technology Limited. K 102556
```
- K012459 references `Unipolar 6494 Temporary Myocardial Pacing Wire` as its predicate which has no knumber referenced.
  It does have an id after searching which is `K954809`. However, that does not have a summary pdf and thus no predicate. However, it does look like it might be `K922269`
- K012460. Similar to above.
- K131236. This references a predicate with id `(k0 12215)`
- K120828. This has predicate text `K1 00218` in it
- K120836. This has predicate text `Ki 11034,` in it.
- K140806. Not required because it is substantially equivalent to marketed devices before 1976 / 510k
```text
We have reviewed your Section 510(k) premarket notification of intent to market the device
referenced above and have determined the device is substantially equivalent (for the indications
for use stated in the enclosure) to legally marketed predicate devices marketed in interstate
commerce prior to May 28, 1976, the enactment date of the Medical Device Amendments, or to
devices that have been reclassified in accordance with the provisions of the Federal Food, Drug,
and Cosmetic Act (Act) that do not require approval of a premarket approval application (PMA). 
```

## Solutions

- improve the existing regex to handle the cases above. I'd like to find a fun regex way of doing it without invoking AI
- simplest: funnel everything to a vision model
- feed the entire summary text to an LLM and have it extract the predicates. This can be done very quickly locally
- a multipass approach:
    - pass1
        - extract using regex
        - extract using an llm
        - reconcile differences between those two passes. If they both agree, sweet. If not, human reconciliation (yay)
    - pass2
        - try to identify a device from the predicate device name if present. Predicate must be older.
            - use embeddings or fuzzy search?
    - pass3s
        - pdf -> image -> text -> llm or straight to predicate
        - feed into a vision model.


# how things work end to end?

- I want the data engineering process to be autonomous

- download new FDA 510k json data