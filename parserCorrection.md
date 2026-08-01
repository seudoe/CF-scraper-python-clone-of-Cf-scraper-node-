Yes. I looked through your parser, and I think the main issue isn't BeautifulSoup—it's the parsing strategy itself. 

You're parsing each section independently (`legend`, `input-specification`, `output-specification`, etc.) and then calling `parse_blocks()` on their HTML. That works for many problems, but it breaks on problems where Codeforces changes the nesting slightly (extra `<div>`, images mixed with paragraphs, formulas, nested lists, etc.).

## The biggest problems I noticed

### 1. You're reparsing HTML strings

For example:

```python
parse_blocks(str(legend_div))
```

This serializes the HTML and then reparses it.

Instead, `parse_blocks()` should accept a `Tag`, not a string.

That alone removes a lot of weird edge cases.

---

### 2. `parse_blocks()` only looks at direct children

```python
for element in soup.children:
```

This is the biggest weakness.

Many CF problems look like

```html
<div class="legend">
    <div>
        <p>...</p>
        <img ...>
    </div>
</div>
```

Your parser sees only the outer `<div>`.

It never walks the real tree.

---

### 3. Images

This logic

```python
if img and len(list(element.children)) == 1:
```

fails on things like

```html
<p>
    Some text
    <img ...>
</p>
```

or

```html
<div>
    <img>
    <br>
</div>
```

which Codeforces actually has.

---

### 4. Description detection

You have

```python
legend_div = ...

if not legend_div:
    ...
```

This is fragile.

CF has changed the description container several times over the years.

Instead of trying to locate the description,

I'd parse the entire `.problem-statement` sequentially.

---

## What I'd do instead

Instead of

```text
Find Description

↓

Parse Description

↓

Find Input

↓

Parse Input

↓

Find Output

↓

Parse Output
```

I'd do

```text
.problem-statement

↓

walk every child

↓

switch section when a heading appears

↓

append blocks
```

Like this:

```text
Problem Statement

Header

↓

Paragraph

↓

Paragraph

↓

Image

↓

Input Specification

↓

Paragraph

↓

Code

↓

Output Specification

↓

Paragraph

↓

Sample Tests

↓

Note
```

This approach doesn't care whether Codeforces wraps things in another `<div>` next year.

---

## I'd completely replace `parse_blocks()`

Instead of

```python
parse_blocks(html)
```

I'd write

```python
walk(node)
```

that recursively visits

* p
* div
* ul
* ol
* pre
* img
* table
* li
* br

and emits blocks.

Something like

```text
walk(node)

├── img
│      -> image block
│
├── pre
│      -> code block
│
├── table
│      -> table block
│
├── ul/ol
│      -> list block
│
├── p
│      -> paragraph block
│
└── div
       recurse
```

Notice that **div doesn't become a paragraph**.

It's only a container.

That's a huge difference.

---

## I'd also parse examples differently

Instead of

```python
find_all(sample-test)
```

I'd parse

```text
sample-tests

↓

sample

↓

input

↓

output

↓

optional note
```

because some examples have

```
Input

Output

Explanation
```

while others don't.

---

## Overall recommendation

I wouldn't try to patch your current parser.

I'd rewrite just the parser around **one recursive DOM walker**.

The rest of your architecture is actually good:

* ✅ Selenium fetcher
* ✅ Image rewriting
* ✅ Mongo image storage
* ✅ JSON cache format
* ✅ Separation of scraper and parser  

The parser is the only part I'd redesign.

**I think you can cut the parser down from ~230 lines to around 120–150 lines while making it work for essentially every Codeforces problem**, because you'll be following the DOM structure instead of relying on a collection of special cases.


# -----------------------------------------





A good architecture is:

```text
Selenium
     │
     ▼
Gets rendered DOM
     │
     ▼
BeautifulSoup / lxml
     │
     ▼
Your parser
```


## lxml (what I'd actually recommend)

If you're rewriting the parser,

I'd actually switch to **lxml**.

```python
from lxml import html

tree = html.fromstring(page)
```

Advantages over BeautifulSoup:

* Faster
* Better XPath support
* Cleaner DOM traversal
* More accurate HTML parser

Example:

```python
tree.xpath('//div[@class="problem-statement"]')
```

or

```python
problem.xpath('.//div[contains(@class,"input-specification")]')
```

XPath becomes incredibly useful for structured documents like Codeforces pages.

---

## What I would use

```text
Selenium
      │
      ▼
driver.page_source
      │
      ▼
lxml.html.fromstring(...)
      │
      ▼
Recursive parser
      │
      ▼
JSON
```

---

## Even better: Selenium's JavaScript

One neat trick is to let the browser do some work before you parse.

For example:

```python
problem_html = driver.execute_script("""
return document.querySelector('.problem-statement').outerHTML;
""")
```

Now you're only parsing the part you care about, not the entire page.

Then feed that to BeautifulSoup or lxml.

---

## My recommendation for your extension

Since you're already using Selenium:

* ✅ Keep Selenium for fetching.
* ✅ Extract only `.problem-statement` using JavaScript or a Selenium locator.
* ✅ Parse that fragment with **lxml** (or BeautifulSoup if you prefer).

That's the architecture you'll see in most robust web scrapers because it combines the strengths of both tools.
