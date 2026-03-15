"""
One-time interactive login to Bushel (Ingredion) via Playwright.

Navigates to the Bushel portal, lets the user complete phone + SMS OTP login,
then intercepts the Keycloak token exchange to capture the refresh token.

Usage (from project root):
    PYTHONPATH=/opt/grainbidcalc venv/bin/python -m ingestion.scrapers.bushel_login

The refresh token is saved to data/bushel_token.json and used by the
Bushel scraper for ongoing access token refreshes.
"""

import json
import logging
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

TOKEN_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "bushel_token.json"
PORTAL_URL = "https://portal.bushelpowered.com/ingredion/cash-bids"
SESSION_URL = "https://portal.bushelpowered.com/api/auth/session"
KEYCLOAK_TOKEN_URL = "https://id.bushelops.com/auth/realms/bushel/protocol/openid-connect/token"


def _save_tokens(data: dict) -> None:
    """Save token data to disk."""
    data["saved_at"] = time.time()
    TOKEN_FILE.write_text(json.dumps(data, indent=2))
    print(f"Tokens saved to {TOKEN_FILE}")


def _get_all_session_cookies(cookies: list[dict]) -> list[dict]:
    """Extract ALL NextAuth session cookie chunks from a cookie list.

    NextAuth splits large JWE tokens across multiple cookies:
    __Secure-next-auth.session-token.0, .1, .2, etc.
    Or a single __Secure-next-auth.session-token if small enough.
    """
    return sorted(
        [c for c in cookies if "next-auth.session-token" in c["name"]],
        key=lambda c: c["name"],
    )


def _save_session_cookies(captured_tokens: dict, cookies: list[dict]) -> None:
    """Save all session cookie chunks to the token dict."""
    session_cookies = _get_all_session_cookies(cookies)
    if session_cookies:
        captured_tokens["session_cookies"] = [
            {
                "name": c["name"],
                "value": c["value"],
                "domain": c.get("domain", ""),
            }
            for c in session_cookies
        ]
        # Keep legacy single-cookie fields for backward compat
        captured_tokens["session_cookie_name"] = session_cookies[0]["name"]
        captured_tokens["session_cookie_value"] = session_cookies[0]["value"]
        captured_tokens["session_cookie_domain"] = session_cookies[0].get("domain", "")
        logger.info("Saved %d session cookie chunk(s)", len(session_cookies))


def login_interactive() -> dict:
    """
    Open a headed browser for manual Bushel login.

    Intercepts the NextAuth callback to capture the authorization code,
    then exchanges it for tokens. Falls back to session endpoint if
    interception doesn't capture the refresh token.
    """
    captured_tokens = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Intercept responses to capture tokens
        def handle_response(response):
            nonlocal captured_tokens
            url = response.url
            # Catch NextAuth session endpoint (returns accessToken)
            if "/api/auth/session" in url and response.status == 200:
                try:
                    body = response.json()
                    if body.get("accessToken"):
                        captured_tokens["access_token"] = body["accessToken"]
                        captured_tokens["id_token"] = body.get("idToken", "")
                        captured_tokens["expires"] = body.get("expires", "")
                        captured_tokens["user"] = body.get("user", {})
                except Exception:
                    pass

        page.on("response", handle_response)

        print("\n=== Bushel Login ===")
        print("Opening Bushel portal (headless)...")
        print("You'll be prompted for your phone number and SMS code.\n")

        page.goto(PORTAL_URL, wait_until="networkidle", timeout=30000)

        # Check if already logged in
        page.wait_for_timeout(2000)
        if captured_tokens.get("access_token"):
            print("Already logged in! Token captured from session.")
            _save_session_cookies(captured_tokens, context.cookies())
            _save_tokens(captured_tokens)
            browser.close()
            return captured_tokens

        # The portal shows a "Sign in" button — click it to go to Keycloak
        sign_in_btn = page.locator('button:has-text("Sign in"), a:has-text("Sign in"), button:has-text("sign in")')
        if sign_in_btn.count() > 0:
            print("Clicking 'Sign in' button...")
            sign_in_btn.first.click()
            page.wait_for_timeout(5000)
            page.wait_for_load_state("networkidle")
        else:
            print("No 'Sign in' button found, checking for login form...")

        print("Waiting for login page to load...")
        page.wait_for_timeout(3000)
        page.screenshot(path="/tmp/bushel_login_page.png")

        # Find phone input
        phone_input = page.locator('input[type="tel"], input[name="phone"], input[name="phoneNumber"], input[placeholder*="phone" i], input[placeholder*="Phone" i], input[type="text"]')
        if phone_input.count() == 0:
            for frame in page.frames:
                phone_input = frame.locator('input[type="tel"], input[name="phone"], input[name="phoneNumber"]')
                if phone_input.count() > 0:
                    break

        if phone_input.count() > 0:
            phone = input("Enter your phone number (e.g., +15198089505): ").strip()
            if not phone:
                phone = "+15198089505"
            phone_input.first.fill(phone)
            page.wait_for_timeout(500)

            submit = page.locator('button[type="submit"], button:has-text("Next"), button:has-text("Continue"), button:has-text("Send"), button:has-text("Sign")')
            if submit.count() > 0:
                submit.first.click()
                print(f"Submitted phone number: {phone}")
                print("Check your phone for an SMS code...")
            else:
                phone_input.first.press("Enter")
                print(f"Submitted phone number: {phone}")
                print("Check your phone for an SMS code...")

            page.wait_for_timeout(3000)
            page.screenshot(path="/tmp/bushel_otp_page.png")

            otp_code = input("Enter the 6-digit SMS code: ").strip()

            page.keyboard.type(otp_code, delay=100)
            page.wait_for_timeout(500)

            submit_btn = page.locator('button:has-text("Submit")')
            if submit_btn.count() > 0:
                submit_btn.first.click()
            else:
                page.keyboard.press("Enter")

            print("Submitted OTP, waiting for redirect...")

            try:
                page.wait_for_url("**/ingredion/**", timeout=30000)
            except Exception:
                pass

            page.wait_for_timeout(5000)
            page.screenshot(path="/tmp/bushel_post_login.png")

        else:
            print("Could not find phone input on login page.")
            print("Screenshot saved to /tmp/bushel_login_page.png")
            page.screenshot(path="/tmp/bushel_login_debug.png")

        # If we didn't capture tokens via response interception,
        # try fetching the session directly
        if not captured_tokens.get("access_token"):
            print("Fetching session to capture access token...")
            resp = page.evaluate("""
                async () => {
                    const r = await fetch('/api/auth/session');
                    return await r.json();
                }
            """)
            if resp and resp.get("accessToken"):
                captured_tokens["access_token"] = resp["accessToken"]
                captured_tokens["id_token"] = resp.get("idToken", "")
                captured_tokens["expires"] = resp.get("expires", "")
                captured_tokens["user"] = resp.get("user", {})

        # Grab ALL session cookie chunks for future refreshes
        _save_session_cookies(captured_tokens, context.cookies())

        browser.close()

    if captured_tokens.get("access_token"):
        _save_tokens(captured_tokens)
        print(f"\nSuccess! Access token captured (length: {len(captured_tokens['access_token'])})")
        print(f"Session cookie chunks: {len(captured_tokens.get('session_cookies', []))}")
        print(f"Session expires: {captured_tokens.get('expires', 'unknown')}")
        return captured_tokens
    else:
        print("\nFailed to capture tokens. Check screenshots in /tmp/bushel_*.png")
        return {}


def refresh_session(tokens: dict) -> dict | None:
    """
    Use saved session cookies to get a fresh access token via Playwright.

    Accepts the full token dict (handles both chunked and legacy single cookie).
    Returns dict with new access_token and session cookies, or None on failure.
    """
    # Build list of cookies to inject
    cookies_to_inject = []

    # Prefer new multi-chunk format
    if tokens.get("session_cookies"):
        for sc in tokens["session_cookies"]:
            cookies_to_inject.append({
                "name": sc["name"],
                "value": sc["value"],
                "domain": sc.get("domain") or "portal.bushelpowered.com",
                "path": "/",
                "secure": True,
                "httpOnly": True,
                "sameSite": "Lax",
            })
    elif tokens.get("session_cookie_name") and tokens.get("session_cookie_value"):
        # Legacy single-cookie format
        cookies_to_inject.append({
            "name": tokens["session_cookie_name"],
            "value": tokens["session_cookie_value"],
            "domain": "portal.bushelpowered.com",
            "path": "/",
            "secure": True,
            "httpOnly": True,
            "sameSite": "Lax",
        })

    if not cookies_to_inject:
        logger.warning("Bushel: no session cookies stored, cannot refresh")
        return None

    logger.info("Bushel: injecting %d session cookie chunk(s) for refresh", len(cookies_to_inject))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        context.add_cookies(cookies_to_inject)
        page = context.new_page()

        resp = page.goto(SESSION_URL, wait_until="networkidle", timeout=15000)
        body = {}
        try:
            body = resp.json()
        except Exception:
            pass

        # Grab ALL rotated session cookie chunks
        all_cookies = context.cookies()
        new_session_cookies = _get_all_session_cookies(all_cookies)

        browser.close()

        if body.get("accessToken") and new_session_cookies:
            result = {
                "access_token": body["accessToken"],
                "id_token": body.get("idToken", ""),
                "expires": body.get("expires", ""),
                "user": body.get("user", {}),
                "session_cookies": [
                    {"name": c["name"], "value": c["value"], "domain": c.get("domain", "")}
                    for c in new_session_cookies
                ],
                # Legacy compat
                "session_cookie_name": new_session_cookies[0]["name"],
                "session_cookie_value": new_session_cookies[0]["value"],
                "session_cookie_domain": new_session_cookies[0].get("domain", ""),
                "saved_at": time.time(),
            }
            logger.info("Bushel: refresh OK, %d cookie chunks rotated", len(new_session_cookies))
            return result

    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = login_interactive()
    if result:
        print("\nLogin complete. You can now run the Bushel scraper.")
    else:
        print("\nLogin failed. Please try again.")
        sys.exit(1)
