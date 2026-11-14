# Contributing

Contributions to Inner Sleeves are welcome! Whether you're fixing a bug, improving the video-generation pipeline, or suggesting an enhancement, thank you for taking the time to help.

## Before contributing

- Check existing issues and pull requests to avoid duplicating work.
- For significant changes, open an issue first to discuss the proposed approach.
- Keep changes focused and avoid introducing unnecessary dependencies.

## Local testing

**Thoroughly test your changes locally before submitting a pull request.**

The project currently has no automated test suite, so contributors are responsible for verifying that their changes work and do not break existing functionality.

- Run the relevant parts of the application locally.
- For changes to video generation or image processing, generate sample output and inspect it visually and technically.
- For changes to audio processing, listen to the resulting audio and check that it behaves as expected.

The scraper and YouTube uploader require private API credentials and are not expected to be runnable by contributors. Do not attempt to obtain or request the project's secrets. If you modify these components, carefully review your changes and test any parts that can be isolated from the external services.

Since there is no automated test suite, please describe what you tested and any limitations in your pull request.

## Pull requests

- Explain what your changes do and why they are needed.
- Keep the pull request focused on a single concern where possible.
- Include relevant screenshots or sample output for visual or media-related changes.
- Never commit API keys, OAuth credentials, refresh tokens, or other secrets.
- Make sure your changes do not introduce unnecessary files or generated media.

By submitting a contribution, you agree that it may be incorporated into the proprietary Inner Sleeves project. Please refer to [LICENSE.md](LICENSE.md) for the project's licensing terms.

Thank you for contributing!
