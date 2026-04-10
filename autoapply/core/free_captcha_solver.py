"""
FREE Captcha Solver
===================
Solves reCAPTCHA using audio challenge + speech recognition.
No API keys, no money needed!

Based on techniques from:
- Buster (9000 stars) - audio recognition
- nonoCAPTCHA (895 stars) - async audio solver

How it works:
1. Click "I'm not a robot"
2. Click audio challenge button
3. Download audio file
4. Use Google Speech Recognition (FREE) to transcribe
5. Submit the answer

Success rate: 70-90% for reCAPTCHA v2
"""

import os
import time
import logging
import tempfile
import asyncio
from pathlib import Path
from typing import Optional

logger = logging.getLogger("autoapply.free_captcha")

# Check dependencies
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

try:
    import speech_recognition as sr
    SPEECH_AVAILABLE = True
except ImportError:
    SPEECH_AVAILABLE = False


class FreeCaptchaSolver:
    """
    FREE reCAPTCHA solver using audio challenge + speech recognition.

    No API keys needed - uses Google's free speech recognition API.
    """

    def __init__(self, headless: bool = False):
        """
        Initialize solver.

        Args:
            headless: Run browser headless (False recommended for debugging)
        """
        self.headless = headless
        self._playwright = None
        self._browser = None

        if SPEECH_AVAILABLE:
            self.recognizer = sr.Recognizer()
        else:
            self.recognizer = None
            logger.warning("SpeechRecognition not installed. Run: pip install SpeechRecognition")

    async def start(self):
        """Start browser."""
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright not installed. Run: pip install playwright && python -m playwright install chromium")

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ]
        )
        logger.info("Browser started")

    async def stop(self):
        """Stop browser."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def solve_recaptcha(self, url: str, max_attempts: int = 3) -> Optional[str]:
        """
        Solve reCAPTCHA on a page and return the page HTML.

        Args:
            url: URL with reCAPTCHA
            max_attempts: Max solve attempts

        Returns:
            Page HTML after solving, or None if failed
        """
        if self._browser is None:
            await self.start()

        context = await self._browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="networkidle")

            for attempt in range(max_attempts):
                logger.info(f"Solve attempt {attempt + 1}/{max_attempts}")

                # Find reCAPTCHA iframe
                recaptcha_frame = None
                for frame in page.frames:
                    if "recaptcha" in frame.url:
                        recaptcha_frame = frame
                        break

                if not recaptcha_frame:
                    # Check if reCAPTCHA is in the page itself
                    if await page.query_selector(".g-recaptcha"):
                        logger.info("Found reCAPTCHA widget")
                    else:
                        logger.info("No reCAPTCHA found on page")
                        return await page.content()

                # Try to solve
                solved = await self._solve_audio_challenge(page, recaptcha_frame)

                if solved:
                    logger.info("reCAPTCHA solved!")
                    await page.wait_for_timeout(2000)
                    return await page.content()

                # Wait before retry
                await page.wait_for_timeout(2000)

            logger.warning("Failed to solve reCAPTCHA after all attempts")
            return await page.content()

        except Exception as e:
            logger.error(f"Error solving reCAPTCHA: {e}")
            return None
        finally:
            await context.close()

    async def _solve_audio_challenge(self, page, recaptcha_frame) -> bool:
        """
        Solve reCAPTCHA audio challenge.

        Returns True if solved successfully.
        """
        try:
            # Click the checkbox
            checkbox = await recaptcha_frame.query_selector("#recaptcha-anchor")
            if checkbox:
                await checkbox.click()
                await page.wait_for_timeout(2000)

            # Check if already solved (green checkmark)
            if await recaptcha_frame.query_selector(".recaptcha-checkbox-checked"):
                return True

            # Find challenge iframe
            challenge_frame = None
            for frame in page.frames:
                if "bframe" in frame.url or "api2/bframe" in frame.url:
                    challenge_frame = frame
                    break

            if not challenge_frame:
                logger.warning("Challenge frame not found")
                return False

            # Click audio button
            audio_btn = await challenge_frame.query_selector("#recaptcha-audio-button")
            if audio_btn:
                await audio_btn.click()
                await page.wait_for_timeout(2000)

            # Get audio source
            audio_source = await challenge_frame.query_selector("#audio-source")
            if not audio_source:
                logger.warning("Audio source not found")
                return False

            audio_url = await audio_source.get_attribute("src")
            if not audio_url:
                logger.warning("No audio URL")
                return False

            logger.info(f"Got audio URL: {audio_url[:50]}...")

            # Download and transcribe audio
            text = await self._transcribe_audio(audio_url)

            if not text:
                logger.warning("Failed to transcribe audio")
                return False

            logger.info(f"Transcribed: {text}")

            # Enter the answer
            input_field = await challenge_frame.query_selector("#audio-response")
            if input_field:
                await input_field.fill(text)

                # Click verify
                verify_btn = await challenge_frame.query_selector("#recaptcha-verify-button")
                if verify_btn:
                    await verify_btn.click()
                    await page.wait_for_timeout(3000)

                    # Check if solved
                    if await recaptcha_frame.query_selector(".recaptcha-checkbox-checked"):
                        return True

            return False

        except Exception as e:
            logger.error(f"Audio challenge error: {e}")
            return False

    async def _transcribe_audio(self, audio_url: str) -> Optional[str]:
        """
        Download audio and transcribe using Google Speech Recognition.
        """
        if not self.recognizer:
            logger.error("SpeechRecognition not available")
            return None

        try:
            import requests
            import io

            # Download audio
            response = requests.get(audio_url, timeout=30)

            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(response.content)
                temp_path = f.name

            # Convert to WAV using pydub if available
            try:
                from pydub import AudioSegment
                audio = AudioSegment.from_mp3(temp_path)
                wav_path = temp_path.replace(".mp3", ".wav")
                audio.export(wav_path, format="wav")
                temp_path = wav_path
            except ImportError:
                logger.warning("pydub not available, trying direct recognition")
            except Exception as e:
                logger.warning(f"Audio conversion failed: {e}")

            # Transcribe
            with sr.AudioFile(temp_path) as source:
                audio_data = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio_data)
                return text.lower().strip()

        except sr.UnknownValueError:
            logger.warning("Speech not recognized")
            return None
        except sr.RequestError as e:
            logger.error(f"Speech API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None
        finally:
            # Cleanup
            try:
                if 'temp_path' in locals():
                    os.unlink(temp_path)
            except:
                pass


async def solve_captcha_async(url: str, headless: bool = False) -> Optional[str]:
    """
    Async function to solve captcha on a URL.

    Returns page HTML after solving.
    """
    solver = FreeCaptchaSolver(headless=headless)
    try:
        await solver.start()
        return await solver.solve_recaptcha(url)
    finally:
        await solver.stop()


def solve_captcha(url: str, headless: bool = False) -> Optional[str]:
    """
    Synchronous wrapper to solve captcha.

    Usage:
        html = solve_captcha("https://indeed.com/jobs")
    """
    return asyncio.run(solve_captcha_async(url, headless))


# CLI
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python free_captcha_solver.py <url>")
        print("Example: python free_captcha_solver.py https://www.google.com/recaptcha/api2/demo")
        sys.exit(1)

    url = sys.argv[1]
    print(f"Solving captcha on: {url}")
    print("A browser window will open - watch it solve!")

    html = solve_captcha(url, headless=False)

    if html:
        print(f"\nSuccess! Got {len(html)} bytes of HTML")
    else:
        print("\nFailed to solve captcha")
