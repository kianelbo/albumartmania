# Inner Sleeves

**Guess the album before the cover is fully revealed.**

[Inner Sleeves on YouTube](https://www.youtube.com/@InnerSleeves)

Inner Sleeves is a YouTube bot (and channel) that turns random albums into guessing games. Each video gradually reveals an album cover while playing a slowed-down, PaulStretch-processed preview of one of its tracks. The answer is revealed at the end.

## How it works

1. Pick a random album from [Last.fm](https://www.last.fm/).
2. Download its cover art and a track preview from [Deezer](https://www.deezer.com/).
3. Generate a 60-second vertical video with a gradual artwork reveal, processed audio and album credits.
4. Upload the Short to YouTube and set a randomly selected video frame as its thumbnail.

## Setup

Requires Python 3.12+.

```bash
git clone https://github.com/kianelbo/inner-sleeves.git
cd inner-sleeves
apt-get install -y ffmpeg
pip install -r requirements.txt
```

Configure the following environment variables:

| Variable | Description |
|---|---|
| `LAST_FM_API_KEY` | Last.fm API key |
| `YOUTUBE_CLIENT_ID` | Google OAuth client ID |
| `YOUTUBE_CLIENT_SECRET` | Google OAuth client secret |
| `YOUTUBE_REFRESH_TOKEN` | YouTube OAuth refresh token |

You can use `.env.sample` as a reference for the required variables. The application reads environment variables directly; it does not automatically load a `.env` file.

Then run to run locally:

```bash
python main.py
```

The project is run in production via Github actions.
