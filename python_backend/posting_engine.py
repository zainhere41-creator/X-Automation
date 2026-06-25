"""
Posting Engine - Handles X (Twitter) posting automation using Playwright
"""
import asyncio
import logging
import random
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class PostingEngine:
    def __init__(self, selectors_path: str = None):
        """Initialize posting engine and load selectors"""
        if selectors_path is None:
            selectors_path = str(Path(__file__).resolve().parent.parent / "config" / "selectors.json")
        self.selectors = self._load_selectors(selectors_path)
        self._project_root = Path(__file__).resolve().parent.parent
        logger.info("PostingEngine initialized")
    
    def _load_selectors(self, path: str) -> dict:
        """Load selectors from JSON config file"""
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load selectors from {path}: {e}")
            raise
    
    async def post_tweet(self, page, title: str, url: str, community_url: str, settings: dict) -> dict:
        """
        Post a single tweet with title and URL.
        If community_url is provided:
          1. Post to home feed
          2. Navigate to community tab, post there
          3. Navigate back to home ("For you" tab)
        
        Args:
            page: Playwright page object
            title: Tweet text content
            url: Content URL to include in tweet
            community_url: Community name from XLSX (if set, posts to both home and community)
            settings: Settings dict with typing delays, etc.
        
        Returns dict with:
            success (bool): Whether post was successful
            posted_at (str): ISO timestamp if successful
            error (str): Error message if failed
        """
        try:
            # Step 1: Verify login
            logger.info("Step 1: Verifying login status")
            login_verified = False
            for selector in self.selectors["login_check"]:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    login_verified = True
                    logger.info(f"Login verified with selector: {selector}")
                    break
                except Exception:
                    continue
            
            if not login_verified:
                logger.warning("Login check failed - no login selectors found")
                return {"success": False, "error": "not_logged_in"}
            
            # Step 2: Navigate to home if not already there
            current_url = page.url
            logger.info(f"Current URL: {current_url}")
            
            if "x.com" not in current_url and "twitter.com" not in current_url:
                logger.info(f"Step 2: Navigating to {self.selectors['home_url']}")
                try:
                    await page.goto(self.selectors["home_url"], wait_until="domcontentloaded", timeout=15000)
                    logger.info("Navigation successful")
                except Exception as nav_error:
                    logger.error(f"Navigation failed: {nav_error}")
                    return {"success": False, "error": "navigation_failed"}
                
                await asyncio.sleep(2)
            else:
                logger.info("Step 2: Already on X.com, skipping navigation")
                await asyncio.sleep(1)
            
            # Ensure we're on "For you" home feed
            await self._click_for_you_tab(page)
            await asyncio.sleep(1)
            
            # Step 3: Post to HOME feed
            logger.info("Step 3: Posting to HOME feed")
            home_result = await self._do_post(page, title, url, settings, "HOME")
            if not home_result["success"]:
                logger.error(f"Home post failed: {home_result['error']}")
                return home_result
            
            logger.info("Home post successful")
            
            # Step 4: If community specified, post to community too
            if community_url:
                logger.info(f"Step 4: Navigating to Community tab: '{community_url}'")
                try:
                    community_navigated = await self._navigate_to_community_tab(page, community_url)
                    if not community_navigated:
                        logger.warning("Community tab not found, skipping community post")
                    else:
                        await asyncio.sleep(1)
                        
                        # Post to community
                        logger.info("Step 4: Posting to COMMUNITY")
                        community_result = await self._do_post(page, title, url, settings, "COMMUNITY")
                        if not community_result["success"]:
                            logger.error(f"Community post failed: {community_result['error']}")
                            # Don't fail entirely - home post succeeded
                        else:
                            logger.info("Community post successful")
                except Exception as e:
                    logger.error(f"Community posting error: {e}")
                
                # Step 5: Navigate back to home
                logger.info("Step 5: Navigating back to home")
                await self._click_for_you_tab(page)
                await asyncio.sleep(1)
            else:
                logger.info("Step 4: No community specified, skipping")
            
            # Step 6: Return success
            posted_at = datetime.now().isoformat()
            logger.info(f"Tweet posted successfully at {posted_at}")
            return {"success": True, "posted_at": posted_at}
            
        except Exception as e:
            error_msg = str(e)[:200]
            logger.error(f"Error posting tweet: {error_msg}")
            return {"success": False, "error": error_msg}
    
    async def _click_for_you_tab(self, page) -> bool:
        """Click the 'For you' tab to go back to home feed"""
        try:
            tab_selectors = [
                "[role='tab']",
                "a[role='tab']",
            ]
            for selector in tab_selectors:
                try:
                    tabs = await page.query_selector_all(selector)
                    for tab in tabs:
                        text = await tab.text_content()
                        if text and "for you" in text.lower().strip():
                            await tab.click()
                            logger.info("Clicked 'For you' tab")
                            await asyncio.sleep(1)
                            return True
                except Exception:
                    continue
            
            # Fallback: navigate to home URL
            await page.goto(self.selectors["home_url"], wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(2)
            return True
        except Exception as e:
            logger.debug(f"Failed to click For you tab: {e}")
            return False
    
    async def _clear_tweet_box(self, page, label: str) -> bool:
        """Select all text in tweet box and delete it. Returns True if cleared."""
        try:
            for selector in self.selectors["tweet_box"]:
                try:
                    tweet_box = await page.wait_for_selector(selector, timeout=3000)
                    if not tweet_box:
                        continue
                    text = await tweet_box.inner_text()
                    if text and text.strip():
                        logger.info(f"[{label}] Clearing tweet box: {text[:50]}...")
                        await tweet_box.click()
                        await asyncio.sleep(0.1)
                        await page.keyboard.press("Control+a")
                        await asyncio.sleep(0.15)
                        await page.keyboard.press("Backspace")
                        await asyncio.sleep(0.3)
                        logger.info(f"[{label}] Tweet box cleared")
                    return True
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"[{label}] Could not clear tweet box: {e}")
        return False

    async def _check_for_post_error(self, page, label: str) -> Optional[str]:
        """
        After clicking submit, check for error toasts/messages from X.
        Returns error text if found, None if no error.
        Common errors: duplicate tweet, already sent, rate limit, content policy.
        """
        error_keywords = [
            "already sent", "already posted", "duplicate", "previously",
            "can't send", "cannot send", "try again", "something went wrong",
            "rate limit", "too many", "content policy", "violates",
            "couldn't send", "failed to send", "send this post",
        ]
        try:
            # Check toast / alert elements
            for selector in self.selectors.get("error_toast", []):
                try:
                    toasts = await page.query_selector_all(selector)
                    for toast in toasts:
                        text = await toast.inner_text()
                        if not text:
                            continue
                        text_lower = text.lower().strip()
                        for kw in error_keywords:
                            if kw in text_lower:
                                logger.warning(f"[{label}] X error detected: {text[:100]}")
                                return text.strip()
                except Exception:
                    continue

            # Broader scan: any visible element with error-like text near the tweet area
            try:
                all_elements = await page.query_selector_all("[role='alert'], [data-testid='toast'], [data-testid='sheetDialog'], [aria-live='assertive']")
                for el in all_elements:
                    text = await el.inner_text()
                    if not text:
                        continue
                    text_lower = text.lower().strip()
                    for kw in error_keywords:
                        if kw in text_lower:
                            logger.warning(f"[{label}] X error detected (broad): {text[:100]}")
                            return text.strip()
            except Exception:
                pass

        except Exception as e:
            logger.debug(f"[{label}] Error checking for post errors: {e}")
        return None

    async def _do_post(self, page, title: str, url: str, settings: dict, label: str) -> dict:
        """Perform a single post (find tweet box, type, submit, handle errors)"""
        max_retries = 3
        current_title = title
        
        for attempt in range(max_retries):
            try:
                # Find and click tweet box
                logger.info(f"[{label}] Finding tweet box")
                tweet_box_found = False
                tweet_box = None
                for selector in self.selectors["tweet_box"]:
                    try:
                        tweet_box = await page.wait_for_selector(selector, timeout=10000)
                        await tweet_box.click()
                        tweet_box_found = True
                        logger.info(f"[{label}] Tweet box found: {selector}")
                        break
                    except Exception as e:
                        logger.debug(f"[{label}] Selector {selector} failed: {e}")
                        continue
                
                if not tweet_box_found:
                    logger.warning(f"[{label}] Tweet box not found")
                    try:
                        screenshot_path = self._project_root / "logs" / f"screenshot_{label.lower()}_tweet_box_not_found_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                        await page.screenshot(path=str(screenshot_path))
                    except Exception:
                        pass
                    return {"success": False, "error": "tweet_box_not_found"}
                
                await asyncio.sleep(0.5)
                
                # Clear any existing text BEFORE typing
                logger.info(f"[{label}] Clearing any existing text before typing")
                await self._clear_tweet_box(page, label)
                
                # Type content
                logger.info(f"[{label}] Typing content (attempt {attempt + 1}/{max_retries})")
                
                # Add random filler words to title (up to 3, but respect 280 char limit)
                filler_words = [
                    "it's amazing", "it good", "love this thing", "check this out",
                    "wow", "incredible", "must see", "unbelievable", "awesome",
                    "great stuff", "highly recommend", "you need this", "game changer",
                    "life changing", "so good", "amazing", "best thing ever",
                    "must have", "mind blown", "epic", "legendary", "fire",
                    "lit", "dope", "sick", "insane", "crazy good", "next level",
                    "premium quality", "top notch", "first class", "elite",
                    "outstanding", "exceptional", "remarkable", "extraordinary",
                    "phenomenal", "stellar", "brilliant", "magnificent", "superb",
                    "excellent", "perfect", "flawless", "immaculate", "pristine",
                    "fresh", "clean", "smooth", "sleek", "stylish", "classy",
                    "elegant", "sophisticated", "refined", "polished", "gleaming",
                    "vibrant", "vivid", "bold", "striking", "stunning",
                    "breathtaking", "jaw-dropping", "mind-blowing", "awe-inspiring",
                    "glorious", "splendid", "majestic", "grand", "magical",
                    "enchanting", "captivating", "mesmerizing", "spellbinding",
                    "fascinating", "intriguing", "compelling", "engaging", "absorbing",
                    "riveting", "gripping", "thrilling", "exciting", "exhilarating",
                    "electrifying", "dynamic", "energetic", "powerful", "intense",
                    "fierce", "passionate", "fiery", "burning", "blazing",
                    "hot", "spicy", "cool", "amazing", "incredible", "unbelievable",
                    "astonishing", "astounding", "surprising", "shocking", "startling"
                ]
                
                dots_count = settings.get("title_dots_count", 2)
                dots = "." * dots_count
                url_line = f"\n/{url}"
                
                # Calculate max chars for title + fillers (280 - url - dots - newlines)
                max_title_chars = 280 - len(url) - dots_count - 3  # 3 for \n/ and buffer
                
                # Add fillers one by one, stop if would exceed limit
                selected_fillers = []
                title_with_fillers = current_title
                random.shuffle(filler_words)
                
                for filler in filler_words:
                    test_title = f"{title_with_fillers} {filler}"
                    if len(test_title) <= max_title_chars:
                        selected_fillers.append(filler)
                        title_with_fillers = test_title
                        if len(selected_fillers) >= 3:
                            break
                    else:
                        break
                
                logger.info(f"[{label}] Added {len(selected_fillers)} fillers, title length: {len(title_with_fillers)}")
                text = f"{title_with_fillers}{dots}{url_line}"
                
                typing_delay_min = settings.get("typing_delay_min", 80)
                typing_delay_max = settings.get("typing_delay_max", 180)
                
                delay = random.randint(typing_delay_min, typing_delay_max)
                await page.keyboard.type(text, delay=delay)
                logger.info(f"[{label}] Content typed: {text[:50]}...")
                
                # Configurable delay before clicking submit
                pre_submit_min = settings.get("pre_submit_delay_min", 1.0)
                pre_submit_max = settings.get("pre_submit_delay_max", 2.0)
                await asyncio.sleep(random.uniform(pre_submit_min, pre_submit_max))
                
                # Submit tweet
                logger.info(f"[{label}] Submitting tweet")
                submit_clicked = False
                for selector in self.selectors["submit_button"]:
                    try:
                        submit_btn = await page.wait_for_selector(selector, timeout=10000)
                        
                        is_disabled = await submit_btn.get_attribute("disabled")
                        if is_disabled is not None:
                            logger.warning(f"[{label}] Submit button is disabled: {selector}")
                            continue
                        
                        await submit_btn.click()
                        submit_clicked = True
                        logger.info(f"[{label}] Submit button clicked: {selector}")
                        break
                    except Exception as e:
                        logger.debug(f"[{label}] Submit selector {selector} failed: {e}")
                        continue
                
                if not submit_clicked:
                    logger.warning(f"[{label}] Submit button not found")
                    try:
                        screenshot_path = self._project_root / "logs" / f"screenshot_{label.lower()}_submit_failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                        await page.screenshot(path=str(screenshot_path))
                    except Exception:
                        pass
                    return {"success": False, "error": "submit_button_not_found"}
                
                # Wait for X to process the post
                await asyncio.sleep(3)
                
                # Check for error toasts/messages from X
                error_text = await self._check_for_post_error(page, label)
                if error_text:
                    error_lower = error_text.lower()
                    
                    # Check for "Upgrade to Premium" error - post too long
                    if "upgrade to premium" in error_lower or "longer posts" in error_lower:
                        logger.warning(f"[{label}] Post too long - removing one line from title (attempt {attempt + 1})")
                        await self._clear_tweet_box(page, label)
                        
                        # Remove one line from title (split by newline and remove last line)
                        lines = current_title.split('\n')
                        if len(lines) > 1:
                            current_title = '\n'.join(lines[:-1])
                            logger.info(f"[{label}] Shortened title: {current_title[:50]}...")
                            continue  # Retry with shorter title
                        else:
                            # Title is already one line, can't shorten more
                            logger.error(f"[{label}] Cannot shorten title further")
                            return {"success": True, "duplicate": True, "error": error_text[:200]}
                    
                    # Other errors (duplicate, etc.) - clear and return success
                    logger.warning(f"[{label}] Post rejected by X: {error_text[:100]}")
                    await self._clear_tweet_box(page, label)
                    return {"success": True, "duplicate": True, "error": error_text[:200]}
                
                # Verify: check if tweet box cleared (indicates successful post)
                try:
                    for selector in self.selectors["tweet_box"]:
                        try:
                            tweet_box_after = await page.wait_for_selector(selector, timeout=3000)
                            text_after = await tweet_box_after.inner_text()
                            if text_after and text_after.strip():
                                logger.warning(f"[{label}] Tweet box still has text after submit: {text_after[:50]}...")
                                # Might be an error X didn't show a toast for — clear it
                                await self._clear_tweet_box(page, label)
                            else:
                                logger.info(f"[{label}] Tweet box cleared — post succeeded")
                            break
                        except Exception:
                            continue
                except Exception as e:
                    logger.debug(f"[{label}] Could not verify tweet box state: {e}")
                
                logger.info(f"[{label}] Post submitted successfully")
                return {"success": True}
                
            except Exception as e:
                error_msg = str(e)[:200]
                logger.error(f"[{label}] Error in _do_post: {error_msg}")
                # Always try to clear tweet box on error so next post starts clean
                try:
                    await self._clear_tweet_box(page, label)
                except Exception:
                    pass
                return {"success": False, "error": error_msg}
        
        # All retries exhausted
        logger.error(f"[{label}] All {max_retries} attempts failed")
        return {"success": False, "error": "max_retries_exceeded"}
    
    async def _navigate_to_community_tab(self, page, community_name: str) -> bool:
        """
        Navigate to the Community tab on X homepage.
        The community is a tab at the top of the home page (next to "For you" and "Following").
        The tab name matches the community name from the XLSX file.
        
        Args:
            page: Playwright page object
            community_name: Name of the community to post to (from XLSX community column)
        
        Returns:
            bool: True if Community tab was successfully clicked, False otherwise
        """
        try:
            logger.info(f"Looking for community tab: '{community_name}'")
            
            # Find all tab-like elements at the top of the page
            # X.com uses role="tab" for the feed tabs
            tab_selectors = [
                "[role='tab']",
                "a[role='tab']",
                "div[role='tab']",
                "a[href*='/communities']",
            ]
            
            for selector in tab_selectors:
                try:
                    tabs = await page.query_selector_all(selector)
                    for tab in tabs:
                        text = await tab.text_content()
                        if text and community_name.lower().strip() in text.lower().strip():
                            await tab.click()
                            logger.info(f"Community tab clicked by text match: '{text.strip()}'")
                            await asyncio.sleep(2)
                            return True
                except Exception as e:
                    logger.debug(f"Tab selector {selector} failed: {e}")
                    continue
            
            # Fallback: find any clickable element with matching text
            try:
                all_elements = await page.query_selector_all("a, div, span, button")
                for el in all_elements:
                    text = await el.text_content()
                    if text and text.strip() == community_name.strip():
                        tag = await el.evaluate("el => el.tagName.toLowerCase()")
                        if tag in ["a", "div", "span", "button"]:
                            await el.click()
                            logger.info(f"Community tab clicked by exact text match: '{text.strip()}' ({tag})")
                            await asyncio.sleep(2)
                            return True
            except Exception as e:
                logger.debug(f"Fallback text search failed: {e}")
            
            logger.warning(f"Community tab '{community_name}' not found")
            # Take screenshot for debugging
            try:
                screenshot_path = self._project_root / "logs" / f"screenshot_community_tab_not_found_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                await page.screenshot(path=str(screenshot_path))
                logger.info(f"Screenshot saved to {screenshot_path}")
            except Exception:
                pass
            return False
            
        except Exception as e:
            logger.error(f"Error navigating to Community tab: {e}")
            return False
    
    async def run_cycle(self, profile_manager, queue_manager, playwright_instance, settings: dict):
        """
        Execute one posting cycle - process sheets_this_run sheets SEQUENTIALLY.
        Each sheet is fully completed (all tasks to all profiles) before moving to the next.
        """
        sheets_per_run = settings.get("sheets_per_run", 1)
        
        logger.info("=" * 60)
        logger.info(f"Starting posting cycle (sheets_per_run={sheets_per_run})")
        logger.info("=" * 60)
        
        try:
            next_sheet = queue_manager.get_next_sheet_index()
            if next_sheet is None:
                logger.info("All sheets completed")
                return
            
            sheets_this_run = []
            for i in range(sheets_per_run):
                idx = next_sheet + i
                if queue_manager.sheet_exists(idx):
                    sheets_this_run.append(idx)
            
            if not sheets_this_run:
                logger.info("No sheets to process")
                return
            
            concurrency = settings.get("concurrency", 2)
            semaphore = asyncio.Semaphore(concurrency)
            
            # Process sheets SEQUENTIALLY - complete one sheet fully before the next
            for sheet_idx in sheets_this_run:
                tasks = queue_manager.get_tasks_for_sheets([sheet_idx])
                if not tasks:
                    logger.info(f"Sheet {sheet_idx}: no pending tasks, skipping")
                    continue
                
                sheet_name = tasks[0].get("sheet_name", f"Sheet {sheet_idx}")
                logger.info(f"--- Starting Sheet {sheet_idx} ({sheet_name}): {len(tasks)} tasks ---")
                
                tasks_by_profile = {}
                for task in tasks:
                    pid = task["profile_id"]
                    tasks_by_profile.setdefault(pid, []).append(task)
                
                # Mark tasks as failed for profiles that aren't running
                # Collect pids to remove first, then remove after iteration
                pids_to_remove = []
                for pid, ptasks in tasks_by_profile.items():
                    if not profile_manager.is_profile_running(pid):
                        for task in ptasks:
                            queue_manager.mark_failed(task["id"], "profile_not_running")
                            logger.warning(f"Profile {pid} not running, task {task['id']} marked as failed")
                        pids_to_remove.append(pid)
                for pid in pids_to_remove:
                    del tasks_by_profile[pid]
                
                async def process_profile(profile_id, profile_tasks):
                    async with semaphore:
                        browser, page = None, None
                        try:
                            browser, page = await profile_manager.connect(profile_id, playwright_instance)
                            
                            for task in profile_tasks:
                                try:
                                    result = await self.post_tweet(
                                        page,
                                        task["title"],
                                        task["url"],
                                        task.get("community", ""),
                                        settings
                                    )
                                    
                                    if result["success"]:
                                        queue_manager.mark_done(task["id"])
                                        logger.info(f"SUCCESS profile {profile_id} sheet {sheet_name} task {task['id']}")
                                    else:
                                        queue_manager.mark_failed(task["id"], result["error"])
                                        logger.error(f"FAILED profile {profile_id}: {result['error']}")
                                    
                                    # Delay between posts (not after the last one)
                                    if task != profile_tasks[-1]:
                                        delay = random.uniform(
                                            settings.get("post_delay_min", 3),
                                            settings.get("post_delay_max", 8)
                                        )
                                        await asyncio.sleep(delay)
                                
                                except Exception as e:
                                    logger.exception(f"ERROR profile {profile_id}: {e}")
                                    queue_manager.mark_failed(task["id"], str(e))
                        except Exception as e:
                            logger.exception(f"ERROR connecting profile {profile_id}: {e}")
                            for task in profile_tasks:
                                queue_manager.mark_failed(task["id"], str(e))
                        finally:
                            if browser:
                                await profile_manager.disconnect(browser)
                
                # Wait for ALL profiles to finish this sheet before moving on
                if tasks_by_profile:
                    await asyncio.gather(*[
                        process_profile(pid, ptasks)
                        for pid, ptasks in tasks_by_profile.items()
                    ])
                
                logger.info(f"--- Sheet {sheet_idx} ({sheet_name}) COMPLETE ---")
            
            stats = queue_manager.get_stats()
            logger.info(f"Cycle complete. Sheets processed: {sheets_this_run}")
            logger.info(f"Stats - Pending: {stats['pending']}, Done: {stats['done']}, Failed: {stats['failed']}")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.exception(f"Critical error in run_cycle: {e}")
