# Output

This is the **default folder the app writes results to**. Each run creates
its own timestamped subfolder, so nothing is ever overwritten:

```
output/
  20260630-143200/
    IMG_7803.json                 <- one clean, nested annotation per image
    IMG_7805.json
    ...
    annotations.jsonl             <- all annotations, one JSON object per line
    annotations.csv               <- the same data as a tidy, spreadsheet-friendly table
    run_metadata.json             <- which provider/model ran, when, with what prompt/schema
```

`annotations.csv` uses a long/tidy format -- one row per extracted value,
columns `image, concert, work, field, value` (plus `share` if you ran more
than one sample per image) -- so it opens directly in Excel, Google Sheets,
or pandas without any reshaping.

This folder is excluded from version control (see `.gitignore`) other than
this README -- your annotation runs stay local to your machine.
