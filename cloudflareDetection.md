Cloudflare doesn't rely on a single thing like cookies. It builds a **trust profile** from many signals over time.

Here's what a real browser session accumulates:

| Signal                                       | Stored?             | Helps? | Notes                                                        |
| -------------------------------------------- | ------------------- | ------ | ------------------------------------------------------------ |
| 🍪 Cookies (`cf_clearance`, session cookies) | ✅                   | ⭐⭐⭐⭐⭐  | Most important.                                              |
| 💾 Local Storage                             | ✅                   | ⭐⭐     | Site-specific state.                                         |
| 🗄️ IndexedDB                                | ✅                   | ⭐⭐     | Some sites use it for persistent state.                      |
| 📦 Cache                                     | ✅                   | ⭐⭐⭐    | Cached JS/CSS/images make you look like a returning visitor. |
| 🔐 TLS Session Tickets                       | ✅ (browser/network) | ⭐⭐⭐    | Reusing secure connections looks natural.                    |
| 🌐 DNS Cache                                 | ✅ (OS/browser)      | ⭐      | Minor signal.                                                |
| 📜 Browser History                           | ✅                   | ⭐      | Low importance.                                              |
| 🔑 Login Session                             | ✅                   | ⭐⭐⭐⭐   | Logged-in users generally appear more legitimate.            |
| 🧩 Installed Extensions                      | ✅                   | ⭐      | Can contribute to a realistic profile.                       |
| ⚙️ Browser Preferences                       | ✅                   | ⭐⭐     | Language, timezone, fonts, etc.                              |

---

## Fingerprints (not really "stored", but consistent)

Cloudflare also checks characteristics that should remain stable:

* `navigator.userAgent`
* `navigator.languages`
* `navigator.platform`
* Screen resolution
* Timezone
* WebGL renderer
* Canvas fingerprint
* Audio fingerprint
* Installed fonts
* Plugins
* Device memory
* CPU cores (`hardwareConcurrency`)
* Touch support
* `navigator.webdriver`

These should stay **consistent** across visits.

---

## Network-level signals

These aren't stored in Chrome's profile, but Cloudflare sees them:

* IP address and reputation
* TLS fingerprint (JA3/JA4)
* HTTP/2 fingerprint
* Request timing
* Connection reuse
* Proxy/VPN detection

---

## Behavior signals

Cloudflare also watches how the browser behaves:

* Mouse movement
* Scrolling
* Click timing
* Focus/blur events
* Typing cadence
* Navigation patterns
* Time spent on pages

---

## The biggest win

Instead of creating a fresh browser every run:

```text
Run 1
↓
New Chrome
No cookies
No cache
No history
```

use a **persistent user profile**:

```python
options.add_argument("--user-data-dir=./chrome-profile")
```

Now Chrome keeps:

* ✅ Cookies
* ✅ Cache
* ✅ Local Storage
* ✅ IndexedDB
* ✅ Login sessions
* ✅ Site permissions
* ✅ Browser preferences

So the next run looks like:

```text
Yesterday's browser
↓

Same cookies

↓

Same cache

↓

Same profile

↓

Much more trusted
```

This is one of the most effective improvements you can make when automating a browser for legitimate tasks.
