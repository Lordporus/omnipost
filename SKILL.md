---
name: omnipost
description: Use when automating posts to X/Twitter end to end.
version: 1.0.0
license: MIT
metadata:
  hermes:
    tags: [twitter, x, social, content, automation, research]
    related_skills: [humanizer]
---

# OmniPost

An autonomous X/Twitter posting pipeline: it finds the day's material itself,
writes posts in **your** voice, publishes them through a real logged-in browser,
and proves each one actually went live.

No X API key. No developer account. No paid scraper. One Python dependency.

```
research  ->  plan  ->  schedule  ->  publish  ->  verify
```

**Nothing here posts anything until you finish Step 0 and explicitly turn the
schedule on.** Do not skip the interview - the whole point is to sound like the
user, not like a content bot.

---

## STEP 0 - THE ONBOARDING INTERVIEW (do this first, always)

Run this as a conversation. Ask the questions, wait for real answers, then write
them into `config.json`. Do not invent answers, and do not proceed on defaults
the user never saw.

### 0.1 Load their voice — ASK FOR THEIR BEST POSTS

**This is the most important step.** Ask, in these words or close to them:

> "Give me 5-20 of your best-performing posts — ideally ones with **100k+
> impressions**, or simply the ones you're proudest of. Paste them raw, include
> the line breaks, and separate each post with a line of `---`. If you have them
> with impression counts, include those too.
>
> I'm not copying them. I'm measuring how you actually write: how you open, how
> long you go, whether you use numbers or questions, what you talk about. Without
> this, anything I write will sound like a generic AI account."

Also ask, if they are willing:

> "Name 2-3 accounts in your space whose posts you admire. Paste 3-5 of their
> posts too — I'll treat those as *structure* references, never as voice."

Then:

1. Save the pasted posts to `scratch/my_top_tweets.txt` (one post per block,
   `---` between them).
2. Run `python scripts/voice_profile.py --in scratch/my_top_tweets.txt`.
3. Read the output *with* them and confirm it matches reality. If the tool says
   "median 138 chars, 3 beats, 4/5 posts lead with a number" and they say "yeah,
   that's me", you have a voice profile. If not, ask what's missing.
4. Write `references/voice-profile.local.md` (git-ignored) containing:
   - the measured stats, verbatim
   - the hook patterns, with 3 real examples of their own
   - their recurring topics, in their own words
   - explicit **do-not** list: words, formats and personas they never use
   - a short "sounds like" paragraph you write, then let them correct

**Every draft from now on is written against that file.** If it is missing, stop
and ask for the posts again rather than guessing at a voice.

### 0.2 The rest of the interview

| Ask | Why it matters | Goes to |
|---|---|---|
| "What's your handle?" | the account guard refuses to post as anyone else | `handle` |
| "Is this account on X Premium, or free? (Not sure is fine.)" | The ceiling decides what content is possible and it **differs per account** — free caps at 280, Premium does not. Ask, then **verify by measuring**: `python scripts/post.py measure --save`. Never hardcode a number. | `premium`, `max_chars`, `max_chars_verified` |
| "What do you post about, in your own words?" | drives research queries and topics | `x_queries`, `subreddits`, `feeds` |
| "What timezone are you in, and when do you want to post?" | slots are local time | `timezone`, `slots` |
| "How many posts a day?" | more is not better — a second post in the same feed only counts 62% | `slots` |
| "Do you want a daily news roundup post?" | the one repeating format; gets its own counter | `ai_update_*` |
| "Anything you never want to say or do?" | bait, politics, emoji, DMs — record it in the voice profile | do-not list |
| "Do you use X on your phone as well?" | replies from mobile raise the post count and will confuse a naive verifier | note it |

### 0.3 Then, in order

```bash
cp config.example.json config.json     # then fill it from the interview
pip install -r requirements.txt
python scripts/doctor.py               # fix anything MISSING before continuing
python scripts/doctor.py --live        # network + browser check
python scripts/browser.py launch       # starts the automation browser
#   -> sign in to x.com IN THAT WINDOW. Use "Email or username", not
#      "Continue with Google", which can silently create a SECOND account.
python scripts/post.py check           # must print your handle
python scripts/post.py measure --save  # measures THIS account's ceiling and stores it
python scripts/post.py limits          # confirm: shows the limit + whether it's verified
```

---

## STEP 1 - ONE SUPERVISED POST (Never skip this)

Before enabling background automation, execute exactly **one** supervised post with human confirmation:

1. **Generate and inspect compose screenshot:**
   ```bash
   python scripts/post.py compose --text "Building sovereign multi-platform pipelines with zero API fees." --dry-run
   ```
2. **Review the composer screenshot:**  
   Open and inspect `shots/compose.png`. Confirm the text landed cleanly in the editor, no formatting broke, and the account handle matches.
3. **Publish live with supervisor confirmation:**
   ```bash
   python scripts/post.py post --text "Building sovereign multi-platform pipelines with zero API fees."
   ```
4. **Read back the profile feed:**
   ```bash
   python scripts/post.py shot --what profile
   ```
   Inspect `shots/profile.png` and verify the topmost article matches what was just posted. Only once this verification succeeds are you ready for automation.

---

## STEP 2 - AUTOMATED SCHEDULE ($0 IDLE MONITORING)

OmniPost uses an idle-cost suppression architecture:

```
[Cron / Task Scheduler (Every 15 min)]
               │
               ▼
   python scripts/gate.py --wake
         /                 \
  [Nothing Due]        [Post Due]
        │                   │
    Outputs "IDLE"     Outputs JSON draft payload
    (Zero LLM Cost)   Trigger autonomous agent / daemon
```

1. **Lightweight Monitoring Gate:**  
   `python scripts/gate.py` runs in <50ms without launching a browser or calling an LLM. If no slot is due, it prints `IDLE\n` (byte-identical) and exits with code 0.
2. **$0 Idle Execution:**  
   Configure your external cron job or agent runner to suppress agent execution when `gate.py` outputs `IDLE`. This drops idle running costs to **$0.00**.
3. **Supervisor Daemon:**  
   Alternatively, run `python scripts/daemon.py` on your machine or VPS, which manages morning research at 11:00 AM and slot dispatch with ±15 minutes randomized human jitter.

---

## HARD RULES

These are not style preferences. Breaking them gets posts ignored, or the account
actioned.

1. **Never hardcode a character ceiling - it belongs to the user's account.**
   Free tiers cap at 280; Premium does not. The ceiling decides what content is
   even possible, so it gets **asked for and then measured**, never assumed:
   1. ask the user whether the account is on Premium (free / Premium / not sure)
   2. run `python scripts/post.py measure --save` — it types into the composer and
      reads the Post button's state; **it never clicks Post, so it cannot publish**
   3. that writes `max_chars` + `premium` + `max_chars_verified` into config.json
   `post.py limits` reports what is configured and whether it is verified;
   `settings.limit()` returns `verified: false` when it is not, and both `due.py`
   and `doctor.py` will warn rather than quietly assume. Until it is measured the
   tool falls back to the free-tier minimum, so a long draft gets trimmed instead
   of a post failing at publish time.
1b. **A high ceiling is permission, not instruction.** Length is not the goal and
   never fill the limit: if one sharp idea fits in two sentences, ship two
   sentences - that is a finished post. Vary length deliberately across posts.
   Longer is justified by more substance, never more words.
2. **No engagement bait.** No "like + comment X and I'll DM you", no "must be
   following", no follow-for-follow. X's own ranking notes single out engagement
   bait as the one category where even big accounts get no pass. If the user asks
   for it, show them that and let them decide — but do not add it silently.
3. **No fabricated numbers, results or quotes.** Every figure in a post must
   trace to a source the agent actually read. If it can't be verified, drop the
   post, not the standard. This is the rule that separates this from the spam
   accounts.
3b. **Read Before You Write (Source Provenance).**
   Every claim or takeaway in a draft must trace directly to a verified source URL
   or item in `swipe/<date>.json` collected by `scripts/research.py`. If a claim
   cannot be linked to an article you opened and inspected, drop the post.
4. **Never post the same text twice**, and never post several times back to back.
   The validator strictly hashes and compares against all past posts in `state.json`.
5. **The account guard is absolute.** If the signed-in handle is not the
   configured one, refuse and say so (`HandleMismatchError`). Check before every single post.
6. **The daily roundup number comes from `post.py day`**, never hand-counted. It
   advances only when that post verifies, so a missed day burns no number.
7. **Account Warm-Up Guard.**
   New accounts (<14 days old or <15 posts in the ledger) must cap publishing at 1 post/day.
   High automated volume on fresh accounts looks identical to a spam network and triggers
   instant shadowbanning. Warm the account up manually first.


## WHAT THE ALGORITHM ACTUALLY REWARDS

Worth reading before writing anything. Current weights (from X's published
source):

- A tap is worth 0.3. **Staying 10+ seconds after the tap is worth 0.4.** So the
  body must pay off the hook — clickbait got weaker, delivered value got stronger.
- "Not interested" costs about -47. Never write something your audience wants to hide.
- **Original posts are the only thing that reaches non-followers.**
- A copy-link share is the largest single signal (20). A DM share is 5.
- A post that wins a follower is worth 4.
- Your second post in the same feed counts only 62% — 3 good posts beat 8 filler ones.
- Under 1,000 followers there is a lift toward ~16th in a stranger's feed. Use it
  while you have it.
- Don't chain-reply to yourself, don't stuff hashtags, don't tag strangers.

## THE DAILY FLOW

1. `python scripts/research.py collect --hours 36` → `swipe/<date>.json`
2. Pick stories — prefer real engagement and **read the actual source** before
   making any claim about it (`web_extract`, or curl the page).
3. Write each post against `references/voice-profile.local.md`, then check the
   length. Rule of thumb: one idea, short lines, blank line between thoughts,
   hook in the first 6-8 words, end on the payoff.
4. `python scripts/due.py fill --slot 13:00 --file scratch/x1.txt` for each slot
   (it rejects anything over the limit, so you learn now rather than at post time)
5. The schedule publishes each slot. Then **verify by looking**:
   `python scripts/post.py shot --what profile`, then read `shots/profile.png`
   with a vision tool and confirm the topmost post is the text you wrote.

## PITFALLS ALREADY PAID FOR (10 Hard-Won Lessons)

Do not relearn these the hard way:

1. **CDP WebSocket Drops:** Creating a CDP target on `about:blank` and navigating to heavy web apps drops the WebSocket (`no close frame received or sent`). Always create targets pointing directly to the destination URL.
2. **ProseMirror & React Synthetic Events:** Setting `innerText` directly leaves React/ProseMirror state stale and the Post button disabled forever. Always use CDP `Input.insertText`.
3. **Stealth Evasion Detection:** Launching Chrome with `--remote-debugging-port` leaks automation flags (`navigator.webdriver`). OmniPost injects stealth overrides before document evaluation.
4. **Stale Timeline Rendering:** Feeds cache aggressively; immediate readback after posting reports older posts as newest. Always poll readback over 30–90 seconds.
5. **PDF Carousel Viewport Scaling:** `Page.printToPDF` blurs slides unless CSS locks `@page { size: 1080px 1080px; margin: 0; }` with precise DPI paper dimensions.
6. **LinkedIn Rate Limit Cooldown Windows:** Violating LinkedIn velocity algorithms triggers account locks. Enforce a minimum 4-hour gap between posts.
7. **Atomic Ledger State Locks:** Naive JSON writes corrupt state during sudden crashes or concurrent cron ticks. Always use PID-tagged temp file replacement.
8. **Zero-Cost Idle Suppressions:** Polling agents every 10 minutes wastes hundreds in token costs. `scripts/gate.py` outputs byte-identical `IDLE\n` to suppress idle agent runs.
9. **The "Read Before You Write" Invariant:** Models hallucinate facts unless strictly anchored to scraped research text with verifiable provenance.
10. **The Voice Drift Trap:** AI models drift towards corporate cheerleading unless constrained by an active "DO-NOT" list in `references/voice-profile.local.md`.

## FILES

```
scripts/   settings.py browser.py research.py post.py due.py voice_profile.py doctor.py
config.json         your install (git-ignored); config.example.json is the template
state.json          the ledger: every post, its URL, whether it verified
swipe/  drafts/  shots/  scratch/
references/voice-profile.local.md   your measured voice (git-ignored)
README.md           full setup, scheduling and troubleshooting
```

Full documentation — including how to wire the schedule with a monitor so idle
ticks cost nothing, and the cost model — is in **README.md**.
