I found the issue. It's actually a combination of **Cloudflare** and **how your scraper waits**.


10 seconds isn't enough

Cloudflare doesn't care that you're waiting 10 seconds.

It looks at many signals:

Browser fingerprint
TLS fingerprint
Cookies
Request pattern
Mouse movement
Scrolls
Headers
IP reputation
Previous requests
navigator.webdriver
Canvas fingerprint
WebGL fingerprint
etc.

A bot waiting 10 seconds is still a bot.

---

# Problem 1 (The biggest one)

In `fetch_html()` you do:

```python
driver.get(url)

time.sleep(4)

html = driver.page_source
```



This assumes that after 4 seconds the page is always the problem page.

But that's not how Cloudflare works.

Sometimes the flow is

```text
driver.get()

↓

Cloudflare page

↓

Turnstile JS runs

↓

Browser gets cookies

↓

Redirect

↓

Problem page
```

Sometimes this takes

* 1 sec
* 3 sec
* 7 sec
* 15 sec

Sometimes it never succeeds.

So you're often saving the HTML **too early**.

---

# Problem 2

Your parser expects

```html
<div class="problem-statement">
```

If it isn't there:

```python
ps_div = soup.find(...)

if not ps_div:
    return None
```



Which is exactly what happens when Cloudflare gives

```html
<title>Just a moment...</title>
```

instead.

---

# Problem 3

The 10-second delay isn't helping

You're delaying between problems:

```python
SCRAPE_DELAY_SEC = 10

time.sleep(SCRAPE_DELAY_SEC)
```

 

Cloudflare doesn't care.

It looks at

* webdriver
* TLS fingerprint
* browser fingerprint
* cookies
* request history
* JS execution
* etc.

Not simply

> "Did he wait 10 seconds?"

---

# What I'd change first

Instead of

```python
driver.get(url)

time.sleep(4)

return driver.page_source
```

wait for the actual page.

Example:

```python
from selenium.webdriver.support import expected_conditions as EC

driver.get(url)

WebDriverWait(driver, 30).until(
    lambda d:
        d.find_elements(By.CLASS_NAME, "problem-statement")
        or
        "Just a moment" in d.title
)
```

Then

```python
html = driver.page_source
```

Now inspect:

```python
if "Just a moment" in driver.title:
    raise Exception("Cloudflare challenge")
```

instead of blindly parsing.

---

# Problem 4

You're running **headless**

```python
chrome_options.add_argument("--headless=new")
```



Many Cloudflare installations are significantly more suspicious of headless browsers.

For testing, try

```python
# comment this out
# chrome_options.add_argument("--headless=new")
```

You'll probably notice the browser solves the challenge correctly much more often.

---

# Problem 5 (Very important)

You only do

```python
Object.defineProperty(
    navigator,
    "webdriver",
    ...
)
```



Unfortunately that's only **one** of dozens of signals Cloudflare checks.

Modern Cloudflare also looks at

* WebGL
* Canvas
* Audio
* Permissions API
* Plugins
* Languages
* Chrome runtime
* TLS handshake
* Client hints

Changing `navigator.webdriver` alone is no longer enough.

---

# What I'd do instead

For scraping Codeforces I'd use:

* **undetected-chromedriver**
* or **Playwright**

rather than plain Selenium.

They are much better at looking like a real browser.

---

# Even better

Instead of

```python
driver.get(problem)
```

for 12,000 problems,

keep the same browser alive (you already do 👍).

Then periodically

```python
driver.get("https://codeforces.com")
```

or visit the problem list every few hundred requests so your navigation pattern resembles a human browsing session.

---

# Another thing I'd add

Right after fetching:

```python
html = driver.page_source
```

check

```python
if "Performing security verification" in html:
    print("Cloudflare!")

elif "Just a moment" in html:
    print("Cloudflare!")

elif '<div class="problem-statement">' not in html:
    print("Unknown page")
```

That tells you immediately **why** parsing failed instead of getting

```
Could not find .problem-statement
```

30 functions later.

---

## One more observation

Looking through your code, I think you're trying to scrape **the entire Codeforces problemset** (around **12,000+ problems**) by visiting each problem page individually. 

If that's your end goal, I'd actually redesign the fetching layer. You can make it **much** more reliable and significantly faster while avoiding most Cloudflare issues.

I have a couple of ideas (browser session persistence, retry logic, and a queue-based fetcher) that would make this scraper robust enough to run for days without constantly hitting verification pages.
