import os

import tweepy

from image import resize_if_needed


class TwitterClient:
    def __init__(self):
        api_key = os.getenv("TWITTER_API_KEY")
        api_secret = os.getenv("TWITTER_API_SECRET")
        access_token = os.getenv("TWITTER_ACCESS_TOKEN")
        access_secret = os.getenv("TWITTER_ACCESS_SECRET")
        auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_secret)
        self.api_v1 = tweepy.API(auth)
        self.client_v2 = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_secret
        )

    def post(self, file_path, text=""):
        upload_path = resize_if_needed(file_path)
        try:
            media = self.api_v1.media_upload(upload_path)
        finally:
            if upload_path != file_path:
                os.unlink(upload_path)
        tweet = self.client_v2.create_tweet(text=text, media_ids=[media.media_id_string])
        return tweet.data["id"]

    def delete(self, tweet_id):
        try:
            self.client_v2.delete_tweet(tweet_id)
        except Exception as e:
            print("Could not delete old tweet:", e)
