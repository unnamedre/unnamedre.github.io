# Unnamed Reverse Engineering Podcast

## Site Generator

### Installation (run once)
From root directory:

`pipenv install -three`

### Generate site
1. Add episode and publish on Libsyn
1. `Content->Previously Published`.
1. Click on the **Link/Embed** link for the episode
1. Copy the last number in the "Libsyn Directory URL"
1. Add it to `_sitegen/directory_ids.csv` with the episode number in front.
1. Run `pipenv run _sitegen/generate.py`
1. Review changes with `git diff` or equivalent. Commit. Push.
