# Unnamed Reverse Engineering Podcast

Website and podcast feed for the show, at <https://unnamedre.com>, built by GitHub Pages (Jekyll).

- Episodes (MP3s) are hosted on Cloudflare R2 at `media.unnamedre.com`.
- The podcast feed is `https://unnamedre.com/feed.xml`, generated from `_posts/` by `feed.xml`.
- Download stats go through [OP3](https://op3.dev).

## Adding an episode

See [`_PODCASTING.md`](_PODCASTING.md). In short:

```
python3 _sitegen/new_episode.py <number> "<Title>" <episode.mp3> \
    --subtitle "<summary>" --notes <shownotes.md>
```

Then review the new post, commit and push.

## Local preview

`bundle install && bundle exec jekyll serve`
