# 🎶 Albumartmania

Albumartmania is an automated X (Twitter) bot that posts random album covers (scraped from [last.fm](https://www.last.fm/)).  
Every day, at 10 am UTC, it first posts a cropped version of the album art, teasing the full cover. Four hours later, it replaces the cropped image with the full version.

## ⚙️ Tech Stack

- ☁️ **GitHub Actions** for cron scheduling
- 🪣 **Redis** for temporary state storage
- 🕊️ **Tweepy** for working with X API
