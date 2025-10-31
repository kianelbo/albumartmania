# 🎶 Albumartmania

Albumartmania is an automated X (Twitter) bot that posts random album covers (scraped from [Last.fm](https://www.last.fm/)).  
Every day, at 10 am UTC, it first posts a **cropped** version of the album art, teasing the full cover. Four hours later, it replaces the cropped image with the **full version**.

## ⚙️ Tech Stack

- ☁️ **GitHub Actions** for cron scheduling
- 🪣 **Redis** for temporary state storage
- 🕊️ **Tweepy** for posting on X
- 🎧 **Last.fm API** for album data
