import os
import tweepy


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
        media = self.api_v1.media_upload(file_path)
        tweet = self.client_v2.create_tweet(text=text, media_ids=[media.media_id_string])
        return tweet.data["id"]

    def delete(self, tweet_id):
        try:
            self.client_v2.delete_tweet(tweet_id)
        except Exception as e:
            print("Could not delete old tweet:", e)
