# Reviewing names

Every species name from every source is matched to Catalogue of Life (CoL).
Most names match exactly or through a synonym. The rest are put in a review
list for a person to decide, because a wrong automatic choice would quietly
put the wrong species on the target list, or leave the right one off.

Your decisions are kept in `config/curation.tsv` and applied in every later
run, so each name only needs deciding once.

## The review lists

There is one per source, in `data/review/`:

| File | Names from | Sorted by |
| --- | --- | --- |
| `legacy_names.xlsx` | the earlier European checklist | order, family, name |
| `gbif_names.xlsx` | GBIF records whose key did not match | number of records, most first |
| `bold_names.xlsx` | BOLD identifications | number of specimens, most first |

The BOLD list matters most for the gap list itself: a name there may hold
barcodes that do not yet count for any species. Start at the top; the
first rows have the most specimens.

Each file has a *Read me* sheet and a *Names to review* sheet. The columns:

| Column | Meaning |
| --- | --- |
| `source`, `original_name` | Where the name comes from, and the name exactly as written there. Do not change these. |
| `decision`, `target_name`, `curator`, `date` | Empty: for you to fill in. |
| `outcome` | `review`: there is a likely match or several possible ones. `unmatched`: nothing similar was found. |
| `records` / `specimens` | GBIF and BOLD lists only: how much depends on this name. |
| `suggestion` | The most likely CoL species, if any. |
| `other_candidates` | Other possible CoL species. |
| `family_in_source`, `order_in_source` | The classification the source gives, to help you judge. |
| `note` | Why the name ended up here. |

## The three decisions

| `decision` | Meaning | `target_name` |
| --- | --- | --- |
| `accept` | The suggestion is right. | leave empty |
| `map` | The name belongs to a different CoL species than suggested, or there was no suggestion. | the accepted CoL name, e.g. `Altica oleracea` |
| `reject` | Leave this name out: it is not a valid European species. | leave empty |

Always fill in `curator` (your initials) and `date` (as YYYY-MM-DD). You can
also add a `note`; it shows up in later review lists and helps whoever comes
next.

## Worked examples

These come from the real review list of the earlier checklist.

### A spelling variant: accept

| original_name | suggestion | family_in_source | note |
| --- | --- | --- | --- |
| Nesotes azorica | Nesotes azoricus | Tenebrionidae | near match: spelling differs |

The species epithet has to agree in gender with the genus: *Nesotes* is
masculine, so CoL writes *azoricus*. Same species, so the decision is
**accept**.

### A near match that is a different species: reject or map

| original_name | suggestion | family_in_source | note |
| --- | --- | --- | --- |
| Hoplitis labialis | Hoplitis saxialis | Megachilidae | near match: spelling differs |

The names differ by two letters, but these are two different bees. This is
exactly why near matches are never accepted automatically. Look the name up
(for instance in CoL or a recent checklist):

- If *Hoplitis labialis* is a valid name that CoL lists under another name,
  choose **map** with that name as `target_name`.
- If it is not a valid European species, choose **reject**.

### Several CoL species with the same name: accept or map

| original_name | suggestion | other_candidates | note |
| --- | --- | --- | --- |
| Camisia segnis | Camisia (Camisia) segnis | Camisia segnis | 2 CoL species share this name |

CoL's eXtended Release sometimes lists the same species twice, once with
and once without its subgenus. Both are the same mite, so **accept** the
suggestion.

| original_name | suggestion | other_candidates | note |
| --- | --- | --- | --- |
| Caspia gmelinii | Clathrocaspia gmelinii | Clathrocaspia knipowitschii | 2 CoL species share this name |

Here an old name is a synonym of two different snail species in CoL, and
the source's classification does not say which is meant. Decide from the
literature: **accept** if the suggestion is right, **map** to the other
candidate if that is right, or **reject** if it cannot be decided.

### An uncertain identification: usually reject

| original_name | suggestion | note |
| --- | --- | --- |
| Ampelisca cf. brevicornis | Ampelisca brevicornis | 'cf.' (uncertain identification) |

"cf." means the identification was not certain. For a list of species that
occur in Europe, such a name is weak evidence. **Reject** it, unless you
know the species does occur in Europe; then **accept**.

### No match at all: map or reject

| original_name | outcome | family_in_source |
| --- | --- | --- |
| Altica jarmilae | unmatched | Chrysomelidae |

Nothing similar was found in CoL. Either the name is missing from CoL
(then there is nothing to map to; leave it undecided, and consider reporting
it to CoL), or it is known in CoL under a different name (**map** to that
name), or it is not a valid species (**reject**).

## Saving your decisions

1. Fill in `decision`, `curator` and `date` (and `target_name` for **map**)
   in the review spreadsheet, for as many rows as you like.
2. Copy the first six columns (`source` to `date`) of the rows you decided.
3. Open `config/curation.tsv` in a spreadsheet program and paste them below
   the existing rows. Save it as **tab-separated text**, keeping the name
   `curation.tsv`.
4. Run section 0 of the notebook to check the file, then run again from the
   section that produced the review list (2a for `legacy`, 2b for `gbif`,
   3 for `bold`), and then section 4.

Decided names disappear from the next review list. A **map** whose
`target_name` cannot be found in CoL comes back, with a note saying so.
