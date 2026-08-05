* [](https://crawlee.dev/python/python)
* Quick start

Version: 1.9

On this page

# Quick start

This short tutorial will help you start scraping with Crawlee in just a minute or two. For an in-depth understanding of how Crawlee works, check out the [Introduction](https://crawlee.dev/python/python/docs/introduction.md) section, which provides a comprehensive step-by-step guide to creating your first scraper.

## Choose your crawler[​](#choose-your-crawler "Direct link to Choose your crawler")

Crawlee offers the following main crawler classes: [`BeautifulSoupCrawler`](https://crawlee.dev/python/python/api/class/BeautifulSoupCrawler.md), [`ParselCrawler`](https://crawlee.dev/python/python/api/class/ParselCrawler.md), and [`PlaywrightCrawler`](https://crawlee.dev/python/python/api/class/PlaywrightCrawler.md). All crawlers share the same interface, providing maximum flexibility when switching between them.

Minimum Python version

Crawlee requires Python 3.10 or higher.

### BeautifulSoupCrawler[​](#beautifulsoupcrawler "Direct link to BeautifulSoupCrawler")

The [`BeautifulSoupCrawler`](https://crawlee.dev/python/python/api/class/BeautifulSoupCrawler.md) is a plain HTTP crawler that parses HTML using the well-known [BeautifulSoup](https://pypi.org/project/beautifulsoup4/) library. It crawls the web using an HTTP client that mimics a browser. This crawler is very fast and efficient but cannot handle JavaScript rendering.

### ParselCrawler[​](#parselcrawler "Direct link to ParselCrawler")

The [`ParselCrawler`](https://crawlee.dev/python/python/api/class/ParselCrawler.md) is similar to the [`BeautifulSoupCrawler`](https://crawlee.dev/python/python/api/class/BeautifulSoupCrawler.md) but uses the [Parsel](https://pypi.org/project/parsel/) library for HTML parsing. Parsel is a lightweight library that provides a CSS selector-based API for extracting data from HTML documents. If you are familiar with the [Scrapy](https://scrapy.org/) framework, you will feel right at home with Parsel. As with the [`BeautifulSoupCrawler`](https://crawlee.dev/python/python/api/class/BeautifulSoupCrawler.md), the [`ParselCrawler`](https://crawlee.dev/python/python/api/class/ParselCrawler.md) cannot handle JavaScript rendering.

### PlaywrightCrawler[​](#playwrightcrawler "Direct link to PlaywrightCrawler")

The [`PlaywrightCrawler`](https://crawlee.dev/python/python/api/class/PlaywrightCrawler.md) uses a headless browser controlled by the [Playwright](https://playwright.dev/) library. It can manage Chromium, Firefox, Webkit, and other browsers. Playwright is the successor to the [Puppeteer](https://pptr.dev/) library and is becoming the de facto standard in headless browser automation. If you need a headless browser, choose Playwright.

## Installation[​](#installation "Direct link to Installation")

Crawlee is available the [`crawlee`](https://pypi.org/project/crawlee/) package on PyPI. This package includes the core functionality, while additional features are available as optional extras to keep dependencies and package size minimal.

You can install Crawlee with all features or choose only the ones you need. For installing it using the [pip](https://pip.pypa.io/en/stable/) package manager, run the following command:

```
python -m pip install 'crawlee[all]'
```

Verify that Crawlee is successfully installed:

```
python -c 'import crawlee; print(crawlee.__version__)'
```

If you plan to use the [`PlaywrightCrawler`](https://crawlee.dev/python/python/api/class/PlaywrightCrawler.md), you'll need to install Playwright dependencies, including the browser binaries. To do this, run the following command:

```
playwright install
```

For detailed installation instructions, see the [Setting up](https://crawlee.dev/python/python/docs/introduction/setting-up.md) documentation page.

## Crawling[​](#crawling "Direct link to Crawling")

Run the following example to perform a recursive crawl of the Crawlee website using the selected crawler.

* BeautifulSoupCrawler
* ParselCrawler
* PlaywrightCrawler

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuXFxuZnJvbSBjcmF3bGVlLmNyYXdsZXJzIGltcG9ydCBCZWF1dGlmdWxTb3VwQ3Jhd2xlciwgQmVhdXRpZnVsU291cENyYXdsaW5nQ29udGV4dFxcblxcblxcbmFzeW5jIGRlZiBtYWluKCkgLT4gTm9uZTpcXG4gICAgIyBCZWF1dGlmdWxTb3VwQ3Jhd2xlciBjcmF3bHMgdGhlIHdlYiB1c2luZyBIVFRQIHJlcXVlc3RzXFxuICAgICMgYW5kIHBhcnNlcyBIVE1MIHVzaW5nIHRoZSBCZWF1dGlmdWxTb3VwIGxpYnJhcnkuXFxuICAgIGNyYXdsZXIgPSBCZWF1dGlmdWxTb3VwQ3Jhd2xlcihtYXhfcmVxdWVzdHNfcGVyX2NyYXdsPTEwKVxcblxcbiAgICAjIERlZmluZSBhIHJlcXVlc3QgaGFuZGxlciB0byBwcm9jZXNzIGVhY2ggY3Jhd2xlZCBwYWdlXFxuICAgICMgYW5kIGF0dGFjaCBpdCB0byB0aGUgY3Jhd2xlciB1c2luZyBhIGRlY29yYXRvci5cXG4gICAgQGNyYXdsZXIucm91dGVyLmRlZmF1bHRfaGFuZGxlclxcbiAgICBhc3luYyBkZWYgcmVxdWVzdF9oYW5kbGVyKGNvbnRleHQ6IEJlYXV0aWZ1bFNvdXBDcmF3bGluZ0NvbnRleHQpIC0-IE5vbmU6XFxuICAgICAgICBjb250ZXh0LmxvZy5pbmZvKGYnUHJvY2Vzc2luZyB7Y29udGV4dC5yZXF1ZXN0LnVybH0gLi4uJylcXG4gICAgICAgICMgRXh0cmFjdCByZWxldmFudCBkYXRhIGZyb20gdGhlIHBhZ2UgY29udGV4dC5cXG4gICAgICAgIGRhdGEgPSB7XFxuICAgICAgICAgICAgJ3VybCc6IGNvbnRleHQucmVxdWVzdC51cmwsXFxuICAgICAgICAgICAgJ3RpdGxlJzogY29udGV4dC5zb3VwLnRpdGxlLnN0cmluZyBpZiBjb250ZXh0LnNvdXAudGl0bGUgZWxzZSBOb25lLFxcbiAgICAgICAgfVxcbiAgICAgICAgIyBTdG9yZSB0aGUgZXh0cmFjdGVkIGRhdGEuXFxuICAgICAgICBhd2FpdCBjb250ZXh0LnB1c2hfZGF0YShkYXRhKVxcbiAgICAgICAgIyBFeHRyYWN0IGxpbmtzIGZyb20gdGhlIGN1cnJlbnQgcGFnZSBhbmQgYWRkIHRoZW0gdG8gdGhlIGNyYXdsaW5nIHF1ZXVlLlxcbiAgICAgICAgYXdhaXQgY29udGV4dC5lbnF1ZXVlX2xpbmtzKClcXG5cXG4gICAgIyBBZGQgZmlyc3QgVVJMIHRvIHRoZSBxdWV1ZSBhbmQgc3RhcnQgdGhlIGNyYXdsLlxcbiAgICBhd2FpdCBjcmF3bGVyLnJ1bihbJ2h0dHBzOi8vY3Jhd2xlZS5kZXYnXSlcXG5cXG5cXG5pZiBfX25hbWVfXyA9PSAnX19tYWluX18nOlxcbiAgICBhc3luY2lvLnJ1bihtYWluKCkpXFxuXCJ9Iiwib3B0aW9ucyI6eyJidWlsZCI6ImxhdGVzdCIsImNvbnRlbnRUeXBlIjoiYXBwbGljYXRpb24vanNvbjsgY2hhcnNldD11dGYtOCIsIm1lbW9yeSI6MTAyNCwidGltZW91dCI6MTgwfX0.FYzSLWHZpPu5EwJQM8QlYHBOPN8ym0fJsoJsr5RP2AY\&asrc=run_on_apify)

```
import asyncio



from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext





async def main() -> None:

    # BeautifulSoupCrawler crawls the web using HTTP requests

    # and parses HTML using the BeautifulSoup library.

    crawler = BeautifulSoupCrawler(max_requests_per_crawl=10)



    # Define a request handler to process each crawled page

    # and attach it to the crawler using a decorator.

    @crawler.router.default_handler

    async def request_handler(context: BeautifulSoupCrawlingContext) -> None:

        context.log.info(f'Processing {context.request.url} ...')

        # Extract relevant data from the page context.

        data = {

            'url': context.request.url,

            'title': context.soup.title.string if context.soup.title else None,

        }

        # Store the extracted data.

        await context.push_data(data)

        # Extract links from the current page and add them to the crawling queue.

        await context.enqueue_links()



    # Add first URL to the queue and start the crawl.

    await crawler.run(['https://crawlee.dev'])





if __name__ == '__main__':

    asyncio.run(main())
```

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuXFxuZnJvbSBjcmF3bGVlLmNyYXdsZXJzIGltcG9ydCBQYXJzZWxDcmF3bGVyLCBQYXJzZWxDcmF3bGluZ0NvbnRleHRcXG5cXG5cXG5hc3luYyBkZWYgbWFpbigpIC0-IE5vbmU6XFxuICAgICMgUGFyc2VsQ3Jhd2xlciBjcmF3bHMgdGhlIHdlYiB1c2luZyBIVFRQIHJlcXVlc3RzXFxuICAgICMgYW5kIHBhcnNlcyBIVE1MIHVzaW5nIHRoZSBQYXJzZWwgbGlicmFyeS5cXG4gICAgY3Jhd2xlciA9IFBhcnNlbENyYXdsZXIobWF4X3JlcXVlc3RzX3Blcl9jcmF3bD0xMClcXG5cXG4gICAgIyBEZWZpbmUgYSByZXF1ZXN0IGhhbmRsZXIgdG8gcHJvY2VzcyBlYWNoIGNyYXdsZWQgcGFnZVxcbiAgICAjIGFuZCBhdHRhY2ggaXQgdG8gdGhlIGNyYXdsZXIgdXNpbmcgYSBkZWNvcmF0b3IuXFxuICAgIEBjcmF3bGVyLnJvdXRlci5kZWZhdWx0X2hhbmRsZXJcXG4gICAgYXN5bmMgZGVmIHJlcXVlc3RfaGFuZGxlcihjb250ZXh0OiBQYXJzZWxDcmF3bGluZ0NvbnRleHQpIC0-IE5vbmU6XFxuICAgICAgICBjb250ZXh0LmxvZy5pbmZvKGYnUHJvY2Vzc2luZyB7Y29udGV4dC5yZXF1ZXN0LnVybH0gLi4uJylcXG4gICAgICAgICMgRXh0cmFjdCByZWxldmFudCBkYXRhIGZyb20gdGhlIHBhZ2UgY29udGV4dC5cXG4gICAgICAgIGRhdGEgPSB7XFxuICAgICAgICAgICAgJ3VybCc6IGNvbnRleHQucmVxdWVzdC51cmwsXFxuICAgICAgICAgICAgJ3RpdGxlJzogY29udGV4dC5zZWxlY3Rvci54cGF0aCgnLy90aXRsZS90ZXh0KCknKS5nZXQoKSxcXG4gICAgICAgIH1cXG4gICAgICAgICMgU3RvcmUgdGhlIGV4dHJhY3RlZCBkYXRhLlxcbiAgICAgICAgYXdhaXQgY29udGV4dC5wdXNoX2RhdGEoZGF0YSlcXG4gICAgICAgICMgRXh0cmFjdCBsaW5rcyBmcm9tIHRoZSBjdXJyZW50IHBhZ2UgYW5kIGFkZCB0aGVtIHRvIHRoZSBjcmF3bGluZyBxdWV1ZS5cXG4gICAgICAgIGF3YWl0IGNvbnRleHQuZW5xdWV1ZV9saW5rcygpXFxuXFxuICAgICMgQWRkIGZpcnN0IFVSTCB0byB0aGUgcXVldWUgYW5kIHN0YXJ0IHRoZSBjcmF3bC5cXG4gICAgYXdhaXQgY3Jhd2xlci5ydW4oWydodHRwczovL2NyYXdsZWUuZGV2J10pXFxuXFxuXFxuaWYgX19uYW1lX18gPT0gJ19fbWFpbl9fJzpcXG4gICAgYXN5bmNpby5ydW4obWFpbigpKVxcblwifSIsIm9wdGlvbnMiOnsiYnVpbGQiOiJsYXRlc3QiLCJjb250ZW50VHlwZSI6ImFwcGxpY2F0aW9uL2pzb247IGNoYXJzZXQ9dXRmLTgiLCJtZW1vcnkiOjEwMjQsInRpbWVvdXQiOjE4MH19.fShec9IocYPi2vw1j7Z_Sh3CczHHpm1VNpakilmAu44\&asrc=run_on_apify)

```
import asyncio



from crawlee.crawlers import ParselCrawler, ParselCrawlingContext





async def main() -> None:

    # ParselCrawler crawls the web using HTTP requests

    # and parses HTML using the Parsel library.

    crawler = ParselCrawler(max_requests_per_crawl=10)



    # Define a request handler to process each crawled page

    # and attach it to the crawler using a decorator.

    @crawler.router.default_handler

    async def request_handler(context: ParselCrawlingContext) -> None:

        context.log.info(f'Processing {context.request.url} ...')

        # Extract relevant data from the page context.

        data = {

            'url': context.request.url,

            'title': context.selector.xpath('//title/text()').get(),

        }

        # Store the extracted data.

        await context.push_data(data)

        # Extract links from the current page and add them to the crawling queue.

        await context.enqueue_links()



    # Add first URL to the queue and start the crawl.

    await crawler.run(['https://crawlee.dev'])





if __name__ == '__main__':

    asyncio.run(main())
```

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuXFxuZnJvbSBjcmF3bGVlLmNyYXdsZXJzIGltcG9ydCBQbGF5d3JpZ2h0Q3Jhd2xlciwgUGxheXdyaWdodENyYXdsaW5nQ29udGV4dFxcblxcblxcbmFzeW5jIGRlZiBtYWluKCkgLT4gTm9uZTpcXG4gICAgIyBQbGF5d3JpZ2h0Q3Jhd2xlciBjcmF3bHMgdGhlIHdlYiB1c2luZyBhIGhlYWRsZXNzIGJyb3dzZXJcXG4gICAgIyBjb250cm9sbGVkIGJ5IHRoZSBQbGF5d3JpZ2h0IGxpYnJhcnkuXFxuICAgIGNyYXdsZXIgPSBQbGF5d3JpZ2h0Q3Jhd2xlcigpXFxuXFxuICAgICMgRGVmaW5lIGEgcmVxdWVzdCBoYW5kbGVyIHRvIHByb2Nlc3MgZWFjaCBjcmF3bGVkIHBhZ2VcXG4gICAgIyBhbmQgYXR0YWNoIGl0IHRvIHRoZSBjcmF3bGVyIHVzaW5nIGEgZGVjb3JhdG9yLlxcbiAgICBAY3Jhd2xlci5yb3V0ZXIuZGVmYXVsdF9oYW5kbGVyXFxuICAgIGFzeW5jIGRlZiByZXF1ZXN0X2hhbmRsZXIoY29udGV4dDogUGxheXdyaWdodENyYXdsaW5nQ29udGV4dCkgLT4gTm9uZTpcXG4gICAgICAgIGNvbnRleHQubG9nLmluZm8oZidQcm9jZXNzaW5nIHtjb250ZXh0LnJlcXVlc3QudXJsfSAuLi4nKVxcbiAgICAgICAgIyBFeHRyYWN0IHJlbGV2YW50IGRhdGEgZnJvbSB0aGUgcGFnZSBjb250ZXh0LlxcbiAgICAgICAgZGF0YSA9IHtcXG4gICAgICAgICAgICAndXJsJzogY29udGV4dC5yZXF1ZXN0LnVybCxcXG4gICAgICAgICAgICAndGl0bGUnOiBhd2FpdCBjb250ZXh0LnBhZ2UudGl0bGUoKSxcXG4gICAgICAgIH1cXG4gICAgICAgICMgU3RvcmUgdGhlIGV4dHJhY3RlZCBkYXRhLlxcbiAgICAgICAgYXdhaXQgY29udGV4dC5wdXNoX2RhdGEoZGF0YSlcXG4gICAgICAgICMgRXh0cmFjdCBsaW5rcyBmcm9tIHRoZSBjdXJyZW50IHBhZ2UgYW5kIGFkZCB0aGVtIHRvIHRoZSBjcmF3bGluZyBxdWV1ZS5cXG4gICAgICAgIGF3YWl0IGNvbnRleHQuZW5xdWV1ZV9saW5rcygpXFxuXFxuICAgICMgQWRkIGZpcnN0IFVSTCB0byB0aGUgcXVldWUgYW5kIHN0YXJ0IHRoZSBjcmF3bC5cXG4gICAgYXdhaXQgY3Jhd2xlci5ydW4oWydodHRwczovL2NyYXdsZWUuZGV2J10pXFxuXFxuXFxuaWYgX19uYW1lX18gPT0gJ19fbWFpbl9fJzpcXG4gICAgYXN5bmNpby5ydW4obWFpbigpKVxcblwifSIsIm9wdGlvbnMiOnsiYnVpbGQiOiJsYXRlc3QiLCJjb250ZW50VHlwZSI6ImFwcGxpY2F0aW9uL2pzb247IGNoYXJzZXQ9dXRmLTgiLCJtZW1vcnkiOjQwOTYsInRpbWVvdXQiOjE4MH19.G_nYq646ERlU1yLA0hFR_p51rR_rKyMhqfEfogVXfh8\&asrc=run_on_apify)

```
import asyncio



from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext





async def main() -> None:

    # PlaywrightCrawler crawls the web using a headless browser

    # controlled by the Playwright library.

    crawler = PlaywrightCrawler()



    # Define a request handler to process each crawled page

    # and attach it to the crawler using a decorator.

    @crawler.router.default_handler

    async def request_handler(context: PlaywrightCrawlingContext) -> None:

        context.log.info(f'Processing {context.request.url} ...')

        # Extract relevant data from the page context.

        data = {

            'url': context.request.url,

            'title': await context.page.title(),

        }

        # Store the extracted data.

        await context.push_data(data)

        # Extract links from the current page and add them to the crawling queue.

        await context.enqueue_links()



    # Add first URL to the queue and start the crawl.

    await crawler.run(['https://crawlee.dev'])





if __name__ == '__main__':

    asyncio.run(main())
```

When you run the example, you will see Crawlee automating the data extraction process in your terminal.

<!-- -->

## Running headful browser[​](#running-headful-browser "Direct link to Running headful browser")

By default, browsers controlled by Playwright run in headless mode (without a visible window). However, you can configure the crawler to run in a headful mode, which is useful during the development phase to observe the browser's actions. You can also switch from the default Chromium browser to Firefox or WebKit.

```
import asyncio



from crawlee.crawlers import PlaywrightCrawler





async def main() -> None:

    crawler = PlaywrightCrawler(

        # Run with a visible browser window.

        headless=False,

        # Switch to the Firefox browser.

        browser_type='firefox',

    )



    # ...





if __name__ == '__main__':

    asyncio.run(main())
```

When you run the example code, you'll see an automated browser navigating through the Crawlee website.

<!-- -->

## Results[​](#results "Direct link to Results")

By default, Crawlee stores data in the `./storage` directory within your current working directory. The results of your crawl will be saved as JSON files under `./storage/datasets/default/`.

To view the results, you can use the `cat` command:

```
cat ./storage/datasets/default/000000001.json
```

The JSON file will contain data similar to the following:

```
{

    "url": "https://crawlee.dev/",

    "title": "Crawlee · Build reliable crawlers. Fast. | Crawlee"

}
```

tip

If you want to change the storage directory, you can set the `CRAWLEE_STORAGE_DIR` environment variable to your preferred path.

## Examples and further reading[​](#examples-and-further-reading "Direct link to Examples and further reading")

For more examples showcasing various features of Crawlee, visit the [Examples](https://crawlee.dev/python/python/docs/examples.md) section of the documentation. To get a deeper understanding of Crawlee and its components, read the step-by-step [Introduction](https://crawlee.dev/python/python/docs/introduction.md) guide.

[Edit this page](https://github.com/apify/crawlee-python/edit/master/website/versioned_docs/version-1.9/quick-start/index.mdx)

Last updated

<!-- -->

on **Aug 4, 2026** by **Vlada Dusek**

[Next](https://crawlee.dev/python/python/docs/introduction.md)

[Introduction](https://crawlee.dev/python/python/docs/introduction.md)


* [](https://crawlee.dev/python/python)
* Introduction

Version: 1.9

On this page

# Introduction

Crawlee covers your crawling and scraping end-to-end and helps you **build reliable scrapers. Fast.**

Your crawlers will appear human-like and fly under the radar of modern bot protections even with the default configuration. Crawlee gives you the tools to crawl the web for links, scrape data and persistently store it in machine-readable formats, without having to worry about the technical details. And thanks to rich configuration options, you can tweak almost any aspect of Crawlee to suit your project's needs if the default settings don't cut it.

## What you will learn[​](#what-you-will-learn "Direct link to What you will learn")

The goal of the introduction is to provide a step-by-step guide to the most important features of Crawlee. It will walk you through creating the simplest of crawlers that only prints text to console, all the way up to a full-featured scraper that collects links from a website and extracts data.

## 🛠 Features[​](#-features "Direct link to 🛠 Features")

Why Crawlee is the preferred choice for web scraping and crawling?

### Why use Crawlee instead of just a random HTTP library with an HTML parser?[​](#why-use-crawlee-instead-of-just-a-random-http-library-with-an-html-parser "Direct link to Why use Crawlee instead of just a random HTTP library with an HTML parser?")

* Unified interface for **HTTP & headless browser** crawling.
* Automatic **parallel crawling** based on available system resources.
* Written in Python with **type hints** - enhances DX (IDE autocompletion) and reduces bugs (static type checking).
* Automatic **retries** on errors or when you are getting blocked.
* Integrated **proxy rotation** and session management.
* Configurable **request routing** - direct URLs to the appropriate handlers.
* Persistent **queue for URLs** to crawl.
* Pluggable **storage** of both tabular data and files.
* Robust **error handling**.

### Why to use Crawlee rather than Scrapy?[​](#why-to-use-crawlee-rather-than-scrapy "Direct link to Why to use Crawlee rather than Scrapy?")

* Crawlee has out-of-the-box support for **headless browser** crawling (Playwright).
* Crawlee has a **minimalistic & elegant interface** - Set up your scraper with fewer than 10 lines of code.
* Complete **type hint** coverage.
* Based on standard **Asyncio**.

<!-- -->

<!-- -->

## Next steps[​](#next-steps "Direct link to Next steps")

Next, you will install Crawlee and learn how to bootstrap projects with the prepared Crawlee templates.

[Edit this page](https://github.com/apify/crawlee-python/edit/master/website/versioned_docs/version-1.9/introduction/index.mdx)

Last updated

<!-- -->

on **Aug 4, 2026** by **Vlada Dusek**

[Previous](https://crawlee.dev/python/python/docs/quick-start.md)

[Quick start](https://crawlee.dev/python/python/docs/quick-start.md)

[Next](https://crawlee.dev/python/python/docs/introduction/setting-up.md)

[Setting up](https://crawlee.dev/python/python/docs/introduction/setting-up.md)

* [](https://crawlee.dev/python/python)
* [Introduction](https://crawlee.dev/python/python/docs/introduction.md)
* Setting up

Version: 1.9

On this page

# Setting up

This guide will help you get started with Crawlee by setting it up on your computer. Follow the steps below to ensure a smooth installation process.

## Prerequisites[​](#prerequisites "Direct link to Prerequisites")

Before installing Crawlee itself, make sure that your system meets the following requirements:

* **Python 3.10 or higher**: Crawlee requires Python 3.10 or a newer version. You can download Python from the [official website](https://python.org/downloads/).
* **Python package manager**: While this guide uses [pip](https://pip.pypa.io/) (the most common package manager), you can also use any package manager you want. You can download pip from the [official website](https://pip.pypa.io/en/stable/installation/).

### Verifying prerequisites[​](#verifying-prerequisites "Direct link to Verifying prerequisites")

To check if Python and pip are installed, run the following commands:

```
python --version
```

```
python -m pip --version
```

If these commands return the respective versions, you're ready to continue.

## Installing Crawlee[​](#installing-crawlee "Direct link to Installing Crawlee")

Crawlee is available as [`crawlee`](https://pypi.org/project/crawlee/) package on PyPI. This package includes the core functionality, while additional features are available as optional extras to keep dependencies and package size minimal.

### Basic installation[​](#basic-installation "Direct link to Basic installation")

To install the core package, run:

```
python -m pip install crawlee
```

After installation, verify that Crawlee is installed correctly by checking its version:

```
python -c 'import crawlee; print(crawlee.__version__)'
```

### Full installation[​](#full-installation "Direct link to Full installation")

If you do not mind the package size, you can run the following command to install Crawlee with all optional features:

```
python -m pip install 'crawlee[all]'
```

### Installing specific extras[​](#installing-specific-extras "Direct link to Installing specific extras")

Depending on your use case, you may want to install specific extras to enable additional functionality:

For using the [`BeautifulSoupCrawler`](https://crawlee.dev/python/python/api/class/BeautifulSoupCrawler.md), install the `beautifulsoup` extra:

```
python -m pip install 'crawlee[beautifulsoup]'
```

For using the [`ParselCrawler`](https://crawlee.dev/python/python/api/class/ParselCrawler.md), install the `parsel` extra:

```
python -m pip install 'crawlee[parsel]'
```

For using the [`CurlImpersonateHttpClient`](https://crawlee.dev/python/python/api/class/CurlImpersonateHttpClient.md), install the `curl-impersonate` extra:

```
python -m pip install 'crawlee[curl-impersonate]'
```

If you plan to use a (headless) browser with [`PlaywrightCrawler`](https://crawlee.dev/python/python/api/class/PlaywrightCrawler.md), install Crawlee with the `playwright` extra:

```
python -m pip install 'crawlee[playwright]'
```

After installing the playwright extra, install the necessary Playwright dependencies:

```
playwright install
```

### Installing multiple extras[​](#installing-multiple-extras "Direct link to Installing multiple extras")

You can install multiple extras at once by using a comma as a separator:

```
python -m pip install 'crawlee[beautifulsoup,curl-impersonate]'
```

## Start a new project[​](#start-a-new-project "Direct link to Start a new project")

The quickest way to get started with Crawlee is by using the Crawlee CLI and selecting one of the prepared templates. The CLI helps you set up a new project in seconds.

### Using Crawlee CLI with uv[​](#using-crawlee-cli-with-uv "Direct link to Using Crawlee CLI with uv")

First, ensure you have [uv](https://pypi.org/project/uv/) installed. You can check if it is installed by running:

```
uv --version
```

If [uv](https://pypi.org/project/uv/) is not installed, follow the official [installation guide](https://docs.astral.sh/uv/getting-started/installation/).

Then, run the Crawlee CLI using `uvx` and choose from the available templates:

```
uvx 'crawlee[cli]' create my-crawler
```

### Using Crawlee CLI directly[​](#using-crawlee-cli-directly "Direct link to Using Crawlee CLI directly")

If you already have `crawlee` installed, you can spin it up by running:

```
crawlee create my_crawler
```

Follow the interactive prompts in the CLI to choose a crawler type and set up your new project.

### Running your project[​](#running-your-project "Direct link to Running your project")

To run your newly created project, navigate to the project directory, activate the virtual environment, and execute the Python interpreter with the project module:

* Linux
* Windows

```
cd my_crawler/
```

```
source .venv/bin/activate
```

```
python -m my_crawler
```

```
cd my_crawler/
```

```
venv\Scripts\activate
```

```
python -m my_crawler
```

Congratulations! You have successfully set up and executed your first Crawlee project.

## Next steps[​](#next-steps "Direct link to Next steps")

Next, you will learn how to create a very simple crawler and Crawlee components while building it.

[Edit this page](https://github.com/apify/crawlee-python/edit/master/website/versioned_docs/version-1.9/introduction/01_setting_up.mdx)

Last updated

<!-- -->

on **Aug 4, 2026** by **Vlada Dusek**

[Previous](https://crawlee.dev/python/python/docs/introduction.md)

[Introduction](https://crawlee.dev/python/python/docs/introduction.md)

[Next](https://crawlee.dev/python/python/docs/introduction/first-crawler.md)

[First crawler](https://crawlee.dev/python/python/docs/introduction/first-crawler.md)

* [](https://crawlee.dev/python/python)
* [Introduction](https://crawlee.dev/python/python/docs/introduction.md)
* First crawler

Version: 1.9

On this page

# First crawler

Now, you will build your first crawler. But before you do, let's briefly introduce the Crawlee classes involved in the process.

## How Crawlee works[​](#how-crawlee-works "Direct link to How Crawlee works")

There are 3 main crawler classes available for use in Crawlee.

* [`BeautifulSoupCrawler`](https://crawlee.dev/python/python/api/class/BeautifulSoupCrawler.md)
* [`ParselCrawler`](https://crawlee.dev/python/python/api/class/ParselCrawler.md)
* [`PlaywrightCrawler`](https://crawlee.dev/python/python/api/class/PlaywrightCrawler.md)

We'll talk about their differences later. Now, let's talk about what they have in common.

The general idea of each crawler is to go to a web page, open it, do some stuff there, save some results, continue to the next page, and repeat this process until the crawler's done its job. So the crawler always needs to find answers to two questions: *Where should I go?* and *What should I do there?* Answering those two questions is the only required setup. The crawlers have reasonable defaults for everything else.

### The where - `Request` and `RequestQueue`[​](#the-where---request-and-requestqueue "Direct link to the-where---request-and-requestqueue")

All crawlers use instances of the [`Request`](https://crawlee.dev/python/python/api/class/Request.md) class to determine where they need to go. Each request may hold a lot of information, but at the very least, it must hold a URL - a web page to open. But having only one URL would not make sense for crawling. Sometimes you have a pre-existing list of your own URLs that you wish to visit, perhaps a thousand. Other times you need to build this list dynamically as you crawl, adding more and more URLs to the list as you progress. Most of the time, you will use both options.

The requests are stored in a [`RequestQueue`](https://crawlee.dev/python/python/api/class/RequestQueue.md), a dynamic queue of [`Request`](https://crawlee.dev/python/python/api/class/Request.md) instances. You can seed it with start URLs and also add more requests while the crawler is running. This allows the crawler to open one page, extract interesting data, such as links to other pages on the same domain, add them to the queue (called *enqueuing*) and repeat this process to build a queue of virtually unlimited number of URLs.

### The what - request handler[​](#the-what---request-handler "Direct link to The what - request handler")

In the request handler you tell the crawler what to do at each and every page it visits. You can use it to handle extraction of data from the page, processing the data, saving it, calling APIs, doing calculations and so on.

The request handler is a user-defined function, invoked automatically by the crawler for each [`Request`](https://crawlee.dev/python/python/api/class/Request.md) from the [`RequestQueue`](https://crawlee.dev/python/python/api/class/RequestQueue.md). It always receives a single argument - [`BasicCrawlingContext`](https://crawlee.dev/python/python/api/class/BasicCrawlingContext.md) (or its descendants). Its properties change depending on the crawler class used, but it always includes the `request` property, which represents the currently crawled URL and related metadata.

## Building a crawler[​](#building-a-crawler "Direct link to Building a crawler")

Let's put the theory into practice and start with something easy. Visit a page and get its HTML title. In this tutorial, you'll scrape the Crawlee website <https://crawlee.dev>, but the same code will work for any website.

### Adding requests to the crawling queue[​](#adding-requests-to-the-crawling-queue "Direct link to Adding requests to the crawling queue")

Earlier you learned that the crawler uses a queue of requests as its source of URLs to crawl. Let's create it and add the first request.

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuXFxuZnJvbSBjcmF3bGVlLnN0b3JhZ2VzIGltcG9ydCBSZXF1ZXN0UXVldWVcXG5cXG5cXG5hc3luYyBkZWYgbWFpbigpIC0-IE5vbmU6XFxuICAgICMgRmlyc3QgeW91IGNyZWF0ZSB0aGUgcmVxdWVzdCBxdWV1ZSBpbnN0YW5jZS5cXG4gICAgcnEgPSBhd2FpdCBSZXF1ZXN0UXVldWUub3BlbigpXFxuXFxuICAgICMgQW5kIHRoZW4geW91IGFkZCBvbmUgb3IgbW9yZSByZXF1ZXN0cyB0byBpdC5cXG4gICAgYXdhaXQgcnEuYWRkX3JlcXVlc3QoJ2h0dHBzOi8vY3Jhd2xlZS5kZXYnKVxcblxcblxcbmlmIF9fbmFtZV9fID09ICdfX21haW5fXyc6XFxuICAgIGFzeW5jaW8ucnVuKG1haW4oKSlcXG5cIn0iLCJvcHRpb25zIjp7ImJ1aWxkIjoibGF0ZXN0IiwiY29udGVudFR5cGUiOiJhcHBsaWNhdGlvbi9qc29uOyBjaGFyc2V0PXV0Zi04IiwibWVtb3J5IjoxMDI0LCJ0aW1lb3V0IjoxODB9fQ.xtEUDfrYe6CfTiKS1jtjFTW56R66WCsG8IPnIETMtKI\&asrc=run_on_apify)

```
import asyncio



from crawlee.storages import RequestQueue





async def main() -> None:

    # First you create the request queue instance.

    rq = await RequestQueue.open()



    # And then you add one or more requests to it.

    await rq.add_request('https://crawlee.dev')





if __name__ == '__main__':

    asyncio.run(main())
```

The [`RequestQueue.add_request`](https://crawlee.dev/python/python/api/class/RequestQueue.md#add_request) method automatically converts the object with URL string to a [`Request`](https://crawlee.dev/python/python/api/class/Request.md) instance. So now you have a [`RequestQueue`](https://crawlee.dev/python/python/api/class/RequestQueue.md) that holds one request which points to `https://crawlee.dev`.

Bulk add requests

The code above is for illustration of the request queue concept. Soon you'll learn about the [`BasicCrawler.add_requests`](https://crawlee.dev/python/python/api/class/BasicCrawler.md#add_requests) method which allows you to skip this initialization code, and it also supports adding a large number of requests without blocking.

### Building a BeautifulSoupCrawler[​](#building-a-beautifulsoupcrawler "Direct link to Building a BeautifulSoupCrawler")

Crawlee comes with three main crawler classes: [`BeautifulSoupCrawler`](https://crawlee.dev/python/python/api/class/BeautifulSoupCrawler.md), [`ParselCrawler`](https://crawlee.dev/python/python/api/class/ParselCrawler.md), and [`PlaywrightCrawler`](https://crawlee.dev/python/python/api/class/PlaywrightCrawler.md). You can read their short descriptions in the [Quick start](https://crawlee.dev/python/python/docs/quick-start.md) lesson.

Unless you have a good reason to start with a different one, you should try building a [`BeautifulSoupCrawler`](https://crawlee.dev/python/python/api/class/BeautifulSoupCrawler.md) first. It is an HTTP crawler with HTTP2 support, anti-blocking features and integrated HTML parser - [BeautifulSoup](https://pypi.org/project/beautifulsoup4/). It's fast, simple, cheap to run and does not require complicated dependencies. The only downside is that it won't work out of the box for websites which require JavaScript rendering. But you might not need JavaScript rendering at all, because many modern websites use server-side rendering.

Let's continue with the earlier [`RequestQueue`](https://crawlee.dev/python/python/api/class/RequestQueue.md) example.

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuXFxuIyBBZGQgaW1wb3J0IG9mIGNyYXdsZXIgYW5kIGNyYXdsaW5nIGNvbnRleHQuXFxuZnJvbSBjcmF3bGVlLmNyYXdsZXJzIGltcG9ydCBCZWF1dGlmdWxTb3VwQ3Jhd2xlciwgQmVhdXRpZnVsU291cENyYXdsaW5nQ29udGV4dFxcbmZyb20gY3Jhd2xlZS5zdG9yYWdlcyBpbXBvcnQgUmVxdWVzdFF1ZXVlXFxuXFxuXFxuYXN5bmMgZGVmIG1haW4oKSAtPiBOb25lOlxcbiAgICAjIEZpcnN0IHlvdSBjcmVhdGUgdGhlIHJlcXVlc3QgcXVldWUgaW5zdGFuY2UuXFxuICAgIHJxID0gYXdhaXQgUmVxdWVzdFF1ZXVlLm9wZW4oKVxcblxcbiAgICAjIEFuZCB0aGVuIHlvdSBhZGQgb25lIG9yIG1vcmUgcmVxdWVzdHMgdG8gaXQuXFxuICAgIGF3YWl0IHJxLmFkZF9yZXF1ZXN0KCdodHRwczovL2NyYXdsZWUuZGV2JylcXG5cXG4gICAgY3Jhd2xlciA9IEJlYXV0aWZ1bFNvdXBDcmF3bGVyKHJlcXVlc3RfbWFuYWdlcj1ycSlcXG5cXG4gICAgIyBEZWZpbmUgYSByZXF1ZXN0IGhhbmRsZXIgYW5kIGF0dGFjaCBpdCB0byB0aGUgY3Jhd2xlciB1c2luZyB0aGUgZGVjb3JhdG9yLlxcbiAgICBAY3Jhd2xlci5yb3V0ZXIuZGVmYXVsdF9oYW5kbGVyXFxuICAgIGFzeW5jIGRlZiByZXF1ZXN0X2hhbmRsZXIoY29udGV4dDogQmVhdXRpZnVsU291cENyYXdsaW5nQ29udGV4dCkgLT4gTm9uZTpcXG4gICAgICAgICMgRXh0cmFjdCA8dGl0bGU-IHRleHQgd2l0aCBCZWF1dGlmdWxTb3VwLlxcbiAgICAgICAgIyBTZWUgQmVhdXRpZnVsU291cCBkb2N1bWVudGF0aW9uIGZvciBBUEkgZG9jcy5cXG4gICAgICAgIHVybCA9IGNvbnRleHQucmVxdWVzdC51cmxcXG4gICAgICAgIHRpdGxlID0gY29udGV4dC5zb3VwLnRpdGxlLnN0cmluZyBpZiBjb250ZXh0LnNvdXAudGl0bGUgZWxzZSAnJ1xcbiAgICAgICAgY29udGV4dC5sb2cuaW5mbyhmJ1RoZSB0aXRsZSBvZiB7dXJsfSBpczoge3RpdGxlfS4nKVxcblxcbiAgICBhd2FpdCBjcmF3bGVyLnJ1bigpXFxuXFxuXFxuaWYgX19uYW1lX18gPT0gJ19fbWFpbl9fJzpcXG4gICAgYXN5bmNpby5ydW4obWFpbigpKVxcblwifSIsIm9wdGlvbnMiOnsiYnVpbGQiOiJsYXRlc3QiLCJjb250ZW50VHlwZSI6ImFwcGxpY2F0aW9uL2pzb247IGNoYXJzZXQ9dXRmLTgiLCJtZW1vcnkiOjEwMjQsInRpbWVvdXQiOjE4MH19.zu1PyrE-eFAXkHO_Q-woIm6CoTDVJM0zBEz0PDdhNk8\&asrc=run_on_apify)

```
import asyncio



# Add import of crawler and crawling context.

from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext

from crawlee.storages import RequestQueue





async def main() -> None:

    # First you create the request queue instance.

    rq = await RequestQueue.open()



    # And then you add one or more requests to it.

    await rq.add_request('https://crawlee.dev')



    crawler = BeautifulSoupCrawler(request_manager=rq)



    # Define a request handler and attach it to the crawler using the decorator.

    @crawler.router.default_handler

    async def request_handler(context: BeautifulSoupCrawlingContext) -> None:

        # Extract <title> text with BeautifulSoup.

        # See BeautifulSoup documentation for API docs.

        url = context.request.url

        title = context.soup.title.string if context.soup.title else ''

        context.log.info(f'The title of {url} is: {title}.')



    await crawler.run()





if __name__ == '__main__':

    asyncio.run(main())
```

When you run the example, you will see the title of <https://crawlee.dev> printed to the log. What really happens is that [`BeautifulSoupCrawler`](https://crawlee.dev/python/python/api/class/BeautifulSoupCrawler.md) first makes an HTTP request to `https://crawlee.dev`, then parses the received HTML with BeautifulSoup and makes it available as the `context` argument of the request handler.

```
[__main__] INFO  The title of "https://crawlee.dev" is "Crawlee · Build reliable crawlers. Fast. | Crawlee".
```

### Add requests faster[​](#add-requests-faster "Direct link to Add requests faster")

Earlier we mentioned that you'll learn how to use the [`BasicCrawler.add_requests`](https://crawlee.dev/python/python/api/class/BasicCrawler.md#add_requests) method to skip the request queue initialization. It's simple. Every crawler has an implicit [`RequestQueue`](https://crawlee.dev/python/python/api/class/RequestQueue.md) instance, and you can add requests to it with the [`BasicCrawler.add_requests`](https://crawlee.dev/python/python/api/class/BasicCrawler.md#add_requests) method. In fact, you can go even further and just use the first parameter of `crawler.run()`!

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuXFxuIyBZb3UgZG9uJ3QgbmVlZCB0byBpbXBvcnQgUmVxdWVzdFF1ZXVlIGFueW1vcmUuXFxuZnJvbSBjcmF3bGVlLmNyYXdsZXJzIGltcG9ydCBCZWF1dGlmdWxTb3VwQ3Jhd2xlciwgQmVhdXRpZnVsU291cENyYXdsaW5nQ29udGV4dFxcblxcblxcbmFzeW5jIGRlZiBtYWluKCkgLT4gTm9uZTpcXG4gICAgY3Jhd2xlciA9IEJlYXV0aWZ1bFNvdXBDcmF3bGVyKClcXG5cXG4gICAgQGNyYXdsZXIucm91dGVyLmRlZmF1bHRfaGFuZGxlclxcbiAgICBhc3luYyBkZWYgcmVxdWVzdF9oYW5kbGVyKGNvbnRleHQ6IEJlYXV0aWZ1bFNvdXBDcmF3bGluZ0NvbnRleHQpIC0-IE5vbmU6XFxuICAgICAgICB1cmwgPSBjb250ZXh0LnJlcXVlc3QudXJsXFxuICAgICAgICB0aXRsZSA9IGNvbnRleHQuc291cC50aXRsZS5zdHJpbmcgaWYgY29udGV4dC5zb3VwLnRpdGxlIGVsc2UgJydcXG4gICAgICAgIGNvbnRleHQubG9nLmluZm8oZidUaGUgdGl0bGUgb2Yge3VybH0gaXM6IHt0aXRsZX0uJylcXG5cXG4gICAgIyBTdGFydCB0aGUgY3Jhd2xlciB3aXRoIHRoZSBwcm92aWRlZCBVUkxzLlxcbiAgICBhd2FpdCBjcmF3bGVyLnJ1bihbJ2h0dHBzOi8vY3Jhd2xlZS5kZXYvJ10pXFxuXFxuXFxuaWYgX19uYW1lX18gPT0gJ19fbWFpbl9fJzpcXG4gICAgYXN5bmNpby5ydW4obWFpbigpKVxcblwifSIsIm9wdGlvbnMiOnsiYnVpbGQiOiJsYXRlc3QiLCJjb250ZW50VHlwZSI6ImFwcGxpY2F0aW9uL2pzb247IGNoYXJzZXQ9dXRmLTgiLCJtZW1vcnkiOjEwMjQsInRpbWVvdXQiOjE4MH19.YJB9IR7e81OHAGlrbpMZmTrephFxQmDSI2FHKWat7Qc\&asrc=run_on_apify)

```
import asyncio



# You don't need to import RequestQueue anymore.

from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext





async def main() -> None:

    crawler = BeautifulSoupCrawler()



    @crawler.router.default_handler

    async def request_handler(context: BeautifulSoupCrawlingContext) -> None:

        url = context.request.url

        title = context.soup.title.string if context.soup.title else ''

        context.log.info(f'The title of {url} is: {title}.')



    # Start the crawler with the provided URLs.

    await crawler.run(['https://crawlee.dev/'])





if __name__ == '__main__':

    asyncio.run(main())
```

When you run this code, you'll see exactly the same output as with the earlier, longer example. The [`RequestQueue`](https://crawlee.dev/python/python/api/class/RequestQueue.md) is still there, it's just managed by the crawler automatically.

info

This method not only makes the code shorter, it will help with performance too! Internally it calls [`RequestQueue.add_requests`](https://crawlee.dev/python/python/api/class/RequestQueue.md#add_requests) method. It will wait only for the initial batch of 1000 requests to be added to the queue before resolving, which means the processing will start almost instantly. After that, it will continue adding the rest of the requests in the background (again, in batches of 1000 items, once every second).

## Next steps[​](#next-steps "Direct link to Next steps")

Next, you'll learn about crawling links. That means finding new URLs on the pages you crawl and adding them to the [`RequestQueue`](https://crawlee.dev/python/python/api/class/RequestQueue.md) for the crawler to visit.

[Edit this page](https://github.com/apify/crawlee-python/edit/master/website/versioned_docs/version-1.9/introduction/02_first_crawler.mdx)

Last updated

<!-- -->

on **Aug 4, 2026** by **Vlada Dusek**

[Previous](https://crawlee.dev/python/python/docs/introduction/setting-up.md)

[Setting up](https://crawlee.dev/python/python/docs/introduction/setting-up.md)

[Next](https://crawlee.dev/python/python/docs/introduction/adding-more-urls.md)

[Adding more URLs](https://crawlee.dev/python/python/docs/introduction/adding-more-urls.md)

* [](https://crawlee.dev/python/python)
* [Introduction](https://crawlee.dev/python/python/docs/introduction.md)
* Adding more URLs

Version: 1.9

On this page

# Adding more URLs

Previously you've built a very simple crawler that downloads HTML of a single page, reads its title and prints it to the console. This is the original source code:

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuXFxuZnJvbSBjcmF3bGVlLmNyYXdsZXJzIGltcG9ydCBCZWF1dGlmdWxTb3VwQ3Jhd2xlciwgQmVhdXRpZnVsU291cENyYXdsaW5nQ29udGV4dFxcblxcblxcbmFzeW5jIGRlZiBtYWluKCkgLT4gTm9uZTpcXG4gICAgY3Jhd2xlciA9IEJlYXV0aWZ1bFNvdXBDcmF3bGVyKClcXG5cXG4gICAgQGNyYXdsZXIucm91dGVyLmRlZmF1bHRfaGFuZGxlclxcbiAgICBhc3luYyBkZWYgcmVxdWVzdF9oYW5kbGVyKGNvbnRleHQ6IEJlYXV0aWZ1bFNvdXBDcmF3bGluZ0NvbnRleHQpIC0-IE5vbmU6XFxuICAgICAgICB1cmwgPSBjb250ZXh0LnJlcXVlc3QudXJsXFxuICAgICAgICB0aXRsZSA9IGNvbnRleHQuc291cC50aXRsZS5zdHJpbmcgaWYgY29udGV4dC5zb3VwLnRpdGxlIGVsc2UgJydcXG4gICAgICAgIGNvbnRleHQubG9nLmluZm8oZidUaGUgdGl0bGUgb2Yge3VybH0gaXM6IHt0aXRsZX0uJylcXG5cXG4gICAgYXdhaXQgY3Jhd2xlci5ydW4oWydodHRwczovL2NyYXdsZWUuZGV2LyddKVxcblxcblxcbmlmIF9fbmFtZV9fID09ICdfX21haW5fXyc6XFxuICAgIGFzeW5jaW8ucnVuKG1haW4oKSlcXG5cIn0iLCJvcHRpb25zIjp7ImJ1aWxkIjoibGF0ZXN0IiwiY29udGVudFR5cGUiOiJhcHBsaWNhdGlvbi9qc29uOyBjaGFyc2V0PXV0Zi04IiwibWVtb3J5IjoxMDI0LCJ0aW1lb3V0IjoxODB9fQ.ODoXMKeR0XukKw7A0je4-vG9S7-AV4u1icmfr64tdsU\&asrc=run_on_apify)

```
import asyncio



from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext





async def main() -> None:

    crawler = BeautifulSoupCrawler()



    @crawler.router.default_handler

    async def request_handler(context: BeautifulSoupCrawlingContext) -> None:

        url = context.request.url

        title = context.soup.title.string if context.soup.title else ''

        context.log.info(f'The title of {url} is: {title}.')



    await crawler.run(['https://crawlee.dev/'])





if __name__ == '__main__':

    asyncio.run(main())
```

Now you'll use the example from the previous section and improve on it. You'll add more URLs to the queue and thanks to that the crawler will keep going, finding new links, enqueuing them into the [`RequestQueue`](https://crawlee.dev/python/python/api/class/RequestQueue.md) and then scraping them.

## How crawling works[​](#how-crawling-works "Direct link to How crawling works")

The process is simple:

1. Find new links on the page.
2. Filter only those pointing to the same domain, in this case [crawlee.dev](https://crawlee.dev/).
3. Enqueue (add) them to the [`RequestQueue`](https://crawlee.dev/python/python/api/class/RequestQueue.md).
4. Visit the newly enqueued links.
5. Repeat the process.

In the following paragraphs you will learn about the [`enqueue_links`](https://crawlee.dev/python/python/api/class/EnqueueLinksFunction.md) function which simplifies crawling to a single function call.

context awareness

The [`enqueue_links`](https://crawlee.dev/python/python/api/class/EnqueueLinksFunction.md) function is context aware. It means that it will read the information about the currently crawled page from the context, and you don't need to explicitly provide any arguments. However, you can specify filtering criteria or an enqueuing strategy if desired. It will find the links and automatically add the links to the running crawler's [`RequestQueue`](https://crawlee.dev/python/python/api/class/RequestQueue.md).

## Limit your crawls[​](#limit-your-crawls "Direct link to Limit your crawls")

When you're just testing your code or when your crawler could potentially find millions of links, it's very useful to set a maximum limit of crawled pages. The option is called [`max_requests_per_crawl`](https://crawlee.dev/python/python/api/class/BasicCrawlerOptions.md#max_requests_per_crawl), is available in all crawlers, and you can set it like this:

```
crawler = BeautifulSoupCrawler(max_requests_per_crawl=10)
```

This means that no new requests will be started after the 10th request is finished. The actual number of processed requests might be a little higher thanks to parallelization, because the running requests won't be forcefully aborted. It's not even possible in most cases.

## Finding new links[​](#finding-new-links "Direct link to Finding new links")

There are numerous approaches to finding links to follow when crawling the web. For our purposes, we will be looking for `<a>` elements that contain the `href` attribute because that's what you need in most cases. For example:

```
<a href="https://crawlee.dev/docs/introduction">This is a link to Crawlee introduction</a>
```

Since this is the most common case, it is also the [`enqueue_links`](https://crawlee.dev/python/python/api/class/EnqueueLinksFunction.md) default.

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuXFxuZnJvbSBjcmF3bGVlLmNyYXdsZXJzIGltcG9ydCBCZWF1dGlmdWxTb3VwQ3Jhd2xlciwgQmVhdXRpZnVsU291cENyYXdsaW5nQ29udGV4dFxcblxcblxcbmFzeW5jIGRlZiBtYWluKCkgLT4gTm9uZTpcXG4gICAgIyBMZXQncyBsaW1pdCBvdXIgY3Jhd2xzIHRvIG1ha2Ugb3VyIHRlc3RzIHNob3J0ZXIgYW5kIHNhZmVyLlxcbiAgICBjcmF3bGVyID0gQmVhdXRpZnVsU291cENyYXdsZXIobWF4X3JlcXVlc3RzX3Blcl9jcmF3bD0xMClcXG5cXG4gICAgQGNyYXdsZXIucm91dGVyLmRlZmF1bHRfaGFuZGxlclxcbiAgICBhc3luYyBkZWYgcmVxdWVzdF9oYW5kbGVyKGNvbnRleHQ6IEJlYXV0aWZ1bFNvdXBDcmF3bGluZ0NvbnRleHQpIC0-IE5vbmU6XFxuICAgICAgICB1cmwgPSBjb250ZXh0LnJlcXVlc3QudXJsXFxuICAgICAgICB0aXRsZSA9IGNvbnRleHQuc291cC50aXRsZS5zdHJpbmcgaWYgY29udGV4dC5zb3VwLnRpdGxlIGVsc2UgJydcXG4gICAgICAgIGNvbnRleHQubG9nLmluZm8oZidUaGUgdGl0bGUgb2Yge3VybH0gaXM6IHt0aXRsZX0uJylcXG5cXG4gICAgICAgICMgVGhlIGVucXVldWVfbGlua3MgZnVuY3Rpb24gaXMgYXZhaWxhYmxlIGFzIG9uZSBvZiB0aGUgZmllbGRzIG9mIHRoZSBjb250ZXh0LlxcbiAgICAgICAgIyBJdCBpcyBhbHNvIGNvbnRleHQgYXdhcmUsIHNvIGl0IGRvZXMgbm90IHJlcXVpcmUgYW55IHBhcmFtZXRlcnMuXFxuICAgICAgICBhd2FpdCBjb250ZXh0LmVucXVldWVfbGlua3MoKVxcblxcbiAgICBhd2FpdCBjcmF3bGVyLnJ1bihbJ2h0dHBzOi8vY3Jhd2xlZS5kZXYvJ10pXFxuXFxuXFxuaWYgX19uYW1lX18gPT0gJ19fbWFpbl9fJzpcXG4gICAgYXN5bmNpby5ydW4obWFpbigpKVxcblwifSIsIm9wdGlvbnMiOnsiYnVpbGQiOiJsYXRlc3QiLCJjb250ZW50VHlwZSI6ImFwcGxpY2F0aW9uL2pzb247IGNoYXJzZXQ9dXRmLTgiLCJtZW1vcnkiOjEwMjQsInRpbWVvdXQiOjE4MH19.ZRIb8tuYHWXWQAJZmUTEJVXfKUUFmysN3gXXbQw15KE\&asrc=run_on_apify)

```
import asyncio



from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext





async def main() -> None:

    # Let's limit our crawls to make our tests shorter and safer.

    crawler = BeautifulSoupCrawler(max_requests_per_crawl=10)



    @crawler.router.default_handler

    async def request_handler(context: BeautifulSoupCrawlingContext) -> None:

        url = context.request.url

        title = context.soup.title.string if context.soup.title else ''

        context.log.info(f'The title of {url} is: {title}.')



        # The enqueue_links function is available as one of the fields of the context.

        # It is also context aware, so it does not require any parameters.

        await context.enqueue_links()



    await crawler.run(['https://crawlee.dev/'])





if __name__ == '__main__':

    asyncio.run(main())
```

If you need to override the default selection of elements in [`enqueue_links`](https://crawlee.dev/python/python/api/class/EnqueueLinksFunction.md), you can use the `selector` argument.

```
await context.enqueue_links(selector='a.article-link')
```

## Filtering links to same domain[​](#filtering-links-to-same-domain "Direct link to Filtering links to same domain")

Websites typically contain a lot of links that lead away from the original page. This is normal, but when crawling a website, we usually want to crawl that one site and not let our crawler wander away to Google, Facebook and Twitter. Therefore, we need to filter out the off-domain links and only keep the ones that lead to the same domain.

```
# The default behavior of enqueue_links is to stay on the same hostname, so it does not require

# any parameters. This will ensure the subdomain stays the same.

await context.enqueue_links()
```

The default behavior of [`enqueue_links`](https://crawlee.dev/python/python/api/class/EnqueueLinksFunction.md) is to stay on the same hostname. This **does not include subdomains**. To include subdomains in your crawl, use the `strategy` argument. The `strategy` argument is an instance of the `EnqueueStrategy` type alias.

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuXFxuZnJvbSBjcmF3bGVlLmNyYXdsZXJzIGltcG9ydCBCZWF1dGlmdWxTb3VwQ3Jhd2xlciwgQmVhdXRpZnVsU291cENyYXdsaW5nQ29udGV4dFxcblxcblxcbmFzeW5jIGRlZiBtYWluKCkgLT4gTm9uZTpcXG4gICAgY3Jhd2xlciA9IEJlYXV0aWZ1bFNvdXBDcmF3bGVyKG1heF9yZXF1ZXN0c19wZXJfY3Jhd2w9MTApXFxuXFxuICAgIEBjcmF3bGVyLnJvdXRlci5kZWZhdWx0X2hhbmRsZXJcXG4gICAgYXN5bmMgZGVmIHJlcXVlc3RfaGFuZGxlcihjb250ZXh0OiBCZWF1dGlmdWxTb3VwQ3Jhd2xpbmdDb250ZXh0KSAtPiBOb25lOlxcbiAgICAgICAgY29udGV4dC5sb2cuaW5mbyhmJ1Byb2Nlc3Npbmcge2NvbnRleHQucmVxdWVzdC51cmx9LicpXFxuXFxuICAgICAgICAjIFNlZSB0aGUgYEVucXVldWVTdHJhdGVneWAgdHlwZSBhbGlhcyBmb3IgbW9yZSBzdHJhdGVneSBvcHRpb25zLlxcbiAgICAgICAgIyBoaWdobGlnaHQtbmV4dC1saW5lXFxuICAgICAgICBhd2FpdCBjb250ZXh0LmVucXVldWVfbGlua3MoXFxuICAgICAgICAgICAgIyBoaWdobGlnaHQtbmV4dC1saW5lXFxuICAgICAgICAgICAgc3RyYXRlZ3k9J3NhbWUtZG9tYWluJyxcXG4gICAgICAgICAgICAjIGhpZ2hsaWdodC1uZXh0LWxpbmVcXG4gICAgICAgIClcXG5cXG4gICAgYXdhaXQgY3Jhd2xlci5ydW4oWydodHRwczovL2NyYXdsZWUuZGV2LyddKVxcblxcblxcbmlmIF9fbmFtZV9fID09ICdfX21haW5fXyc6XFxuICAgIGFzeW5jaW8ucnVuKG1haW4oKSlcXG5cIn0iLCJvcHRpb25zIjp7ImJ1aWxkIjoibGF0ZXN0IiwiY29udGVudFR5cGUiOiJhcHBsaWNhdGlvbi9qc29uOyBjaGFyc2V0PXV0Zi04IiwibWVtb3J5IjoxMDI0LCJ0aW1lb3V0IjoxODB9fQ.wsSkJOC86y2a9ATz3O9k5fJxr8I-GRgVHKBpNS8Xy40\&asrc=run_on_apify)

```
import asyncio



from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext





async def main() -> None:

    crawler = BeautifulSoupCrawler(max_requests_per_crawl=10)



    @crawler.router.default_handler

    async def request_handler(context: BeautifulSoupCrawlingContext) -> None:

        context.log.info(f'Processing {context.request.url}.')



        # See the `EnqueueStrategy` type alias for more strategy options.

        await context.enqueue_links(

            strategy='same-domain',

        )



    await crawler.run(['https://crawlee.dev/'])





if __name__ == '__main__':

    asyncio.run(main())
```

When you run the code, you will see the crawler log the **title** of the first page, then the **enqueueing** message showing number of URLs, followed by the **title** of the first enqueued page and so on and so on.

## Skipping duplicate URLs[​](#skipping-duplicate-urls "Direct link to Skipping duplicate URLs")

Skipping of duplicate URLs is critical, because visiting the same page multiple times would lead to duplicate results. This is automatically handled by the [`RequestQueue`](https://crawlee.dev/python/python/api/class/RequestQueue.md) which deduplicates requests using their `unique_key`. This `unique_key` is automatically generated from the request's URL by lowercasing the URL, lexically ordering query parameters, removing fragments and a few other tweaks that ensure the queue only includes unique URLs.

## Advanced filtering arguments[​](#advanced-filtering-arguments "Direct link to Advanced filtering arguments")

While the defaults for [`enqueue_links`](https://crawlee.dev/python/python/api/class/EnqueueLinksFunction.md) can be often exactly what you need, it also gives you fine-grained control over which URLs should be enqueued. One way we already mentioned above. It is using the `EnqueueStrategy` type alias. You can use the `all` strategy if you want to follow every single link, regardless of its domain, or you can enqueue links that target the same domain name with the `same-domain` strategy.

```
# Wanders the internet.

await context.enqueue_links(strategy='all')
```

### Filter URLs with patterns[​](#filter-urls-with-patterns "Direct link to Filter URLs with patterns")

For even more control, you can use the `include` or `exclude` parameters, either as glob patterns or regular expressions, to filter the URLs. Refer to the API documentation for [`enqueue_links`](https://crawlee.dev/python/python/api/class/EnqueueLinksFunction.md) for detailed information on these and other available options.

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuXFxuZnJvbSBjcmF3bGVlIGltcG9ydCBHbG9iXFxuZnJvbSBjcmF3bGVlLmNyYXdsZXJzIGltcG9ydCBCZWF1dGlmdWxTb3VwQ3Jhd2xlciwgQmVhdXRpZnVsU291cENyYXdsaW5nQ29udGV4dFxcblxcblxcbmFzeW5jIGRlZiBtYWluKCkgLT4gTm9uZTpcXG4gICAgY3Jhd2xlciA9IEJlYXV0aWZ1bFNvdXBDcmF3bGVyKG1heF9yZXF1ZXN0c19wZXJfY3Jhd2w9MTApXFxuXFxuICAgIEBjcmF3bGVyLnJvdXRlci5kZWZhdWx0X2hhbmRsZXJcXG4gICAgYXN5bmMgZGVmIHJlcXVlc3RfaGFuZGxlcihjb250ZXh0OiBCZWF1dGlmdWxTb3VwQ3Jhd2xpbmdDb250ZXh0KSAtPiBOb25lOlxcbiAgICAgICAgY29udGV4dC5sb2cuaW5mbyhmJ1Byb2Nlc3Npbmcge2NvbnRleHQucmVxdWVzdC51cmx9LicpXFxuXFxuICAgICAgICAjIEVucXVldWUgbGlua3MgdGhhdCBtYXRjaCB0aGUgJ2luY2x1ZGUnIGdsb2IgcGF0dGVybiBhbmRcXG4gICAgICAgICMgZG8gbm90IG1hdGNoIHRoZSAnZXhjbHVkZScgZ2xvYiBwYXR0ZXJuLlxcbiAgICAgICAgIyBoaWdobGlnaHQtbmV4dC1saW5lXFxuICAgICAgICBhd2FpdCBjb250ZXh0LmVucXVldWVfbGlua3MoXFxuICAgICAgICAgICAgIyBoaWdobGlnaHQtbmV4dC1saW5lXFxuICAgICAgICAgICAgaW5jbHVkZT1bR2xvYignaHR0cHM6Ly9zb21lcGxhY2UuY29tLyoqL2NhdHMnKV0sXFxuICAgICAgICAgICAgIyBoaWdobGlnaHQtbmV4dC1saW5lXFxuICAgICAgICAgICAgZXhjbHVkZT1bR2xvYignaHR0cHM6Ly8qKi9hcmNoaXZlLyoqJyldLFxcbiAgICAgICAgICAgICMgaGlnaGxpZ2h0LW5leHQtbGluZVxcbiAgICAgICAgKVxcblxcbiAgICBhd2FpdCBjcmF3bGVyLnJ1bihbJ2h0dHBzOi8vY3Jhd2xlZS5kZXYvJ10pXFxuXFxuXFxuaWYgX19uYW1lX18gPT0gJ19fbWFpbl9fJzpcXG4gICAgYXN5bmNpby5ydW4obWFpbigpKVxcblwifSIsIm9wdGlvbnMiOnsiYnVpbGQiOiJsYXRlc3QiLCJjb250ZW50VHlwZSI6ImFwcGxpY2F0aW9uL2pzb247IGNoYXJzZXQ9dXRmLTgiLCJtZW1vcnkiOjEwMjQsInRpbWVvdXQiOjE4MH19.RverXr-WKElrnHRMAk3t7ynOkuL5BklOPZ7K15X9TZE\&asrc=run_on_apify)

```
import asyncio



from crawlee import Glob

from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext





async def main() -> None:

    crawler = BeautifulSoupCrawler(max_requests_per_crawl=10)



    @crawler.router.default_handler

    async def request_handler(context: BeautifulSoupCrawlingContext) -> None:

        context.log.info(f'Processing {context.request.url}.')



        # Enqueue links that match the 'include' glob pattern and

        # do not match the 'exclude' glob pattern.

        await context.enqueue_links(

            include=[Glob('https://someplace.com/**/cats')],

            exclude=[Glob('https://**/archive/**')],

        )



    await crawler.run(['https://crawlee.dev/'])





if __name__ == '__main__':

    asyncio.run(main())
```

### Transform requests before enqueuing[​](#transform-requests-before-enqueuing "Direct link to Transform requests before enqueuing")

For cases where you need to modify or filter requests before they are enqueued, you can use the `transform_request_function` parameter. This function receives a [`RequestOptions`](https://crawlee.dev/python/python/api/class/RequestOptions.md) object and should return either a modified [`RequestOptions`](https://crawlee.dev/python/python/api/class/RequestOptions.md) object, or a string of type `RequestTransformAction`, which only allows the values `skip` and `unchanged`. Returning `skip` means the request will be skipped, while `unchanged` will add it without any changes

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImZyb20gX19mdXR1cmVfXyBpbXBvcnQgYW5ub3RhdGlvbnNcXG5cXG5pbXBvcnQgYXN5bmNpb1xcblxcbmZyb20gY3Jhd2xlZSBpbXBvcnQgSHR0cEhlYWRlcnMsIFJlcXVlc3RPcHRpb25zLCBSZXF1ZXN0VHJhbnNmb3JtQWN0aW9uXFxuZnJvbSBjcmF3bGVlLmNyYXdsZXJzIGltcG9ydCBCZWF1dGlmdWxTb3VwQ3Jhd2xlciwgQmVhdXRpZnVsU291cENyYXdsaW5nQ29udGV4dFxcblxcblxcbmRlZiB0cmFuc2Zvcm1fcmVxdWVzdChcXG4gICAgcmVxdWVzdF9vcHRpb25zOiBSZXF1ZXN0T3B0aW9ucyxcXG4pIC0-IFJlcXVlc3RPcHRpb25zIHwgUmVxdWVzdFRyYW5zZm9ybUFjdGlvbjpcXG4gICAgIyBTa2lwIHJlcXVlc3RzIHRvIFBERiBmaWxlc1xcbiAgICBpZiByZXF1ZXN0X29wdGlvbnNbJ3VybCddLmVuZHN3aXRoKCcucGRmJyk6XFxuICAgICAgICByZXR1cm4gJ3NraXAnXFxuXFxuICAgIGlmICcvZG9jcycgaW4gcmVxdWVzdF9vcHRpb25zWyd1cmwnXTpcXG4gICAgICAgICMgQWRkIGN1c3RvbSBoZWFkZXJzIHRvIHJlcXVlc3RzIHRvIHNwZWNpZmljIFVSTHNcXG4gICAgICAgIHJlcXVlc3Rfb3B0aW9uc1snaGVhZGVycyddID0gSHR0cEhlYWRlcnMoeydDdXN0b20tSGVhZGVyJzogJ3ZhbHVlJ30pXFxuXFxuICAgIGVsaWYgJy9ibG9nJyBpbiByZXF1ZXN0X29wdGlvbnNbJ3VybCddOlxcbiAgICAgICAgIyBBZGQgbGFiZWwgZm9yIGNlcnRhaW4gVVJMc1xcbiAgICAgICAgcmVxdWVzdF9vcHRpb25zWydsYWJlbCddID0gJ0JMT0cnXFxuXFxuICAgIGVsc2U6XFxuICAgICAgICAjIFNpZ25hbCB0aGF0IHRoZSByZXF1ZXN0IHNob3VsZCBwcm9jZWVkIHdpdGhvdXQgYW55IHRyYW5zZm9ybWF0aW9uXFxuICAgICAgICByZXR1cm4gJ3VuY2hhbmdlZCdcXG5cXG4gICAgcmV0dXJuIHJlcXVlc3Rfb3B0aW9uc1xcblxcblxcbmFzeW5jIGRlZiBtYWluKCkgLT4gTm9uZTpcXG4gICAgY3Jhd2xlciA9IEJlYXV0aWZ1bFNvdXBDcmF3bGVyKG1heF9yZXF1ZXN0c19wZXJfY3Jhd2w9MTApXFxuXFxuICAgIEBjcmF3bGVyLnJvdXRlci5kZWZhdWx0X2hhbmRsZXJcXG4gICAgYXN5bmMgZGVmIHJlcXVlc3RfaGFuZGxlcihjb250ZXh0OiBCZWF1dGlmdWxTb3VwQ3Jhd2xpbmdDb250ZXh0KSAtPiBOb25lOlxcbiAgICAgICAgY29udGV4dC5sb2cuaW5mbyhmJ1Byb2Nlc3Npbmcge2NvbnRleHQucmVxdWVzdC51cmx9LicpXFxuXFxuICAgICAgICAjIFRyYW5zZm9ybSByZXF1ZXN0IGJlZm9yZSBlbnF1ZXVlaW5nXFxuICAgICAgICBhd2FpdCBjb250ZXh0LmVucXVldWVfbGlua3ModHJhbnNmb3JtX3JlcXVlc3RfZnVuY3Rpb249dHJhbnNmb3JtX3JlcXVlc3QpXFxuXFxuICAgIEBjcmF3bGVyLnJvdXRlci5oYW5kbGVyKCdCTE9HJylcXG4gICAgYXN5bmMgZGVmIGJsb2dfaGFuZGxlcihjb250ZXh0OiBCZWF1dGlmdWxTb3VwQ3Jhd2xpbmdDb250ZXh0KSAtPiBOb25lOlxcbiAgICAgICAgY29udGV4dC5sb2cuaW5mbyhmJ0Jsb2cgUHJvY2Vzc2luZyB7Y29udGV4dC5yZXF1ZXN0LnVybH0uJylcXG5cXG4gICAgYXdhaXQgY3Jhd2xlci5ydW4oWydodHRwczovL2NyYXdsZWUuZGV2LyddKVxcblxcblxcbmlmIF9fbmFtZV9fID09ICdfX21haW5fXyc6XFxuICAgIGFzeW5jaW8ucnVuKG1haW4oKSlcXG5cIn0iLCJvcHRpb25zIjp7ImJ1aWxkIjoibGF0ZXN0IiwiY29udGVudFR5cGUiOiJhcHBsaWNhdGlvbi9qc29uOyBjaGFyc2V0PXV0Zi04IiwibWVtb3J5IjoxMDI0LCJ0aW1lb3V0IjoxODB9fQ.Jj6-CkvsDgLqWAS5AZRI0j5i-BPLOq7A3Oq9IT1iJbk\&asrc=run_on_apify)

```
from __future__ import annotations



import asyncio



from crawlee import HttpHeaders, RequestOptions, RequestTransformAction

from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext





def transform_request(

    request_options: RequestOptions,

) -> RequestOptions | RequestTransformAction:

    # Skip requests to PDF files

    if request_options['url'].endswith('.pdf'):

        return 'skip'



    if '/docs' in request_options['url']:

        # Add custom headers to requests to specific URLs

        request_options['headers'] = HttpHeaders({'Custom-Header': 'value'})



    elif '/blog' in request_options['url']:

        # Add label for certain URLs

        request_options['label'] = 'BLOG'



    else:

        # Signal that the request should proceed without any transformation

        return 'unchanged'



    return request_options





async def main() -> None:

    crawler = BeautifulSoupCrawler(max_requests_per_crawl=10)



    @crawler.router.default_handler

    async def request_handler(context: BeautifulSoupCrawlingContext) -> None:

        context.log.info(f'Processing {context.request.url}.')



        # Transform request before enqueueing

        await context.enqueue_links(transform_request_function=transform_request)



    @crawler.router.handler('BLOG')

    async def blog_handler(context: BeautifulSoupCrawlingContext) -> None:

        context.log.info(f'Blog Processing {context.request.url}.')



    await crawler.run(['https://crawlee.dev/'])





if __name__ == '__main__':

    asyncio.run(main())
```

## Next steps[​](#next-steps "Direct link to Next steps")

Next, you will start your project of scraping a production website and learn some more Crawlee tricks in the process.

[Edit this page](https://github.com/apify/crawlee-python/edit/master/website/versioned_docs/version-1.9/introduction/03_adding_more_urls.mdx)

Last updated

<!-- -->

on **Aug 4, 2026** by **Vlada Dusek**

[Previous](https://crawlee.dev/python/python/docs/introduction/first-crawler.md)

[First crawler](https://crawlee.dev/python/python/docs/introduction/first-crawler.md)

[Next](https://crawlee.dev/python/python/docs/introduction/real-world-project.md)

[Real-world project](https://crawlee.dev/python/python/docs/introduction/real-world-project.md)

* [](https://crawlee.dev/python/python)
* [Introduction](https://crawlee.dev/python/python/docs/introduction.md)
* Real-world project

Version: 1.9

On this page

# Real-world project

> *Hey, guys, you know, it's cool that we can scrape the `<title>` elements of web pages, but that's not very useful. Can we finally scrape some real data and save it somewhere in a machine-readable format? Because that's why I started reading this tutorial in the first place!*

We hear you, young padawan! First, learn how to crawl, you must. Only then, walk through data, you can!

## Making a production-grade crawler[​](#making-a-production-grade-crawler "Direct link to Making a production-grade crawler")

Making a production-grade crawler is not difficult, but there are many pitfalls of scraping that can catch you off guard. So for the real world project you'll learn how to scrape an [Warehouse store example](https://warehouse-theme-metal.myshopify.com/collections) instead of the Crawlee website. It contains a list of products of different categories, and each product has its own detail page.

The website requires JavaScript rendering, which allows us to showcase more features of Crawlee. We've also added some helpful tips that prepare you for the real-world issues that you will surely encounter when scraping at scale.

Not interested in theory?

If you're not interested in crawling theory, feel free to [skip to the next chapter](https://crawlee.dev/python/python/docs/introduction/crawling.md) and get right back to coding.

## Drawing a plan[​](#drawing-a-plan "Direct link to Drawing a plan")

Sometimes scraping is really straightforward, but most of the time, it really pays off to do a bit of research first and try to answer some of these questions:

* How is the website structured?
* Can I scrape it only with HTTP requests (read "with some [`HttpCrawler`](https://crawlee.dev/python/python/api/class/HttpCrawler.md), e.g. [`BeautifulSoupCrawler`](https://crawlee.dev/python/python/api/class/BeautifulSoupCrawler.md)")?
* Do I need a headless browser for something?
* Are there any anti-scraping protections in place?
* Do I need to parse the HTML or can I get the data otherwise, such as directly from the website's API?

For the purposes of this tutorial, let's assume that the website cannot be scraped with [`HttpCrawler`](https://crawlee.dev/python/python/api/class/HttpCrawler.md). It actually can, but we would have to dive a bit deeper than this introductory guide allows. So for now we will make things easier for you, scrape it with [`PlaywrightCrawler`](https://crawlee.dev/python/python/api/class/PlaywrightCrawler.md), and you'll learn about headless browsers in the process.

## Choosing the data you need[​](#choosing-the-data-you-need "Direct link to Choosing the data you need")

A good first step is to figure out what data you want to scrape and where to find it. For the time being, let's just agree that we want to scrape all products from all categories available on the [all collections page of the store](https://warehouse-theme-metal.myshopify.com/collections) and for each product we want to get its:

* URL
* Manufacturer
* SKU
* Title
* Current price
* Stock available

You will notice that some information is available directly on the list page, but for details such as "SKU" we'll also need to open the product's detail page.

![data to scrape](/python/assets/images/scraping-practice-c3a7bcc681e36946e25b1f8cfd090a8a.jpg "Overview of data to be scraped.")

### The start URL(s)[​](#the-start-urls "Direct link to The start URL(s)")

This is where you start your crawl. It's convenient to start as close to the data as possible. For example, it wouldn't make much sense to start at <https://warehouse-theme-metal.myshopify.com> and look for a `collections` link there, when we already know that everything we want to extract can be found at the <https://warehouse-theme-metal.myshopify.com/collections> page.

## Exploring the page[​](#exploring-the-page "Direct link to Exploring the page")

Let's take a look at the <https://warehouse-theme-metal.myshopify.com/collections> page more carefully. There are some **categories** on the page, and each category has a list of **items**. On some category pages, at the bottom you will notice there are links to the next pages of results. This is usually called **the pagination**.

### Categories and sorting[​](#categories-and-sorting "Direct link to Categories and sorting")

When you click the categories, you'll see that they load a page of products filtered by that category. By going through a few categories and observing the behavior, we can also observe that we can sort by different conditions (such as `Best selling`, or `Price, low to high`), but for this example, we will not be looking into those.

Limited pagination

Be careful, because on some websites, like [amazon.com](https://amazon.com), this is not true and the sum of products in categories is actually larger than what's available without filters. Learn more in our [tutorial on scraping websites with limited pagination](https://docs.apify.com/tutorials/scrape-paginated-sites).

### Pagination[​](#pagination "Direct link to Pagination")

The pagination of the demo Warehouse Store is simple enough. When switching between pages, you will see that the URL changes to:

```
https://warehouse-theme-metal.myshopify.com/collections/headphones?page=2
```

Try clicking on the link to page 4. You'll see that the pagination links update and show more pages. But can you trust that this will include all pages and won't stop at some point?

Test your assumptions

Similarly to the issue with filters explained above, the existence of pagination does not guarantee that you can simply paginate through all the results. Always test your assumptions about pagination. Otherwise, you might miss a chunk of results, and not even know about it.

At the time of writing the `Headphones` collection results counter showed 75 results - products. Quick count of products on one page of results makes 24. 6 rows times 4 products. This means that there are 4 pages of results.

If you're not convinced, you can visit a page somewhere in the middle, like `https://warehouse-theme-metal.myshopify.com/collections/headphones?page=2` and see how the pagination looks there.

## The crawling strategy[​](#the-crawling-strategy "Direct link to The crawling strategy")

Now that you know where to start and how to find all the collection details, let's look at the crawling process.

1. Visit the store page containing the list of categories (our start URL).

2. Enqueue all links to all categories.

3. Enqueue all product pages from the current page.

4. Enqueue links to next pages of results.

5. Open the next page in queue.

   <!-- -->

   * When it's a results list page, go to 2.
   * When it's a product page, scrape the data.

6. Repeat until all results pages and all products have been processed.

`PlaywrightCrawler` will make sure to visit the pages for you, if you provide the correct requests, and you already know how to enqueue pages, so this should be fairly easy. Nevertheless, there are few more tricks that we'd like to showcase.

## Sanity check[​](#sanity-check "Direct link to Sanity check")

Let's check that everything is set up correctly before writing the scraping logic itself. You might realize that something in your previous analysis doesn't quite add up, or the website might not behave exactly as you expected.

The example below creates a new crawler that visits the start URL and prints the text content of all the categories on that page. When you run the code, you will see the *very badly formatted* content of the individual category card.

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuXFxuIyBJbnN0ZWFkIG9mIEJlYXV0aWZ1bFNvdXBDcmF3bGVyIGxldCdzIHVzZSBQbGF5d3JpZ2h0IHRvIGJlIGFibGUgdG8gcmVuZGVyIEphdmFTY3JpcHQuXFxuZnJvbSBjcmF3bGVlLmNyYXdsZXJzIGltcG9ydCBQbGF5d3JpZ2h0Q3Jhd2xlciwgUGxheXdyaWdodENyYXdsaW5nQ29udGV4dFxcblxcblxcbmFzeW5jIGRlZiBtYWluKCkgLT4gTm9uZTpcXG4gICAgY3Jhd2xlciA9IFBsYXl3cmlnaHRDcmF3bGVyKClcXG5cXG4gICAgQGNyYXdsZXIucm91dGVyLmRlZmF1bHRfaGFuZGxlclxcbiAgICBhc3luYyBkZWYgcmVxdWVzdF9oYW5kbGVyKGNvbnRleHQ6IFBsYXl3cmlnaHRDcmF3bGluZ0NvbnRleHQpIC0-IE5vbmU6XFxuICAgICAgICAjIFdhaXQgZm9yIHRoZSBjb2xsZWN0aW9uIGNhcmRzIHRvIHJlbmRlciBvbiB0aGUgcGFnZS4gVGhpcyBlbnN1cmVzIHRoYXRcXG4gICAgICAgICMgdGhlIGVsZW1lbnRzIHdlIHdhbnQgdG8gaW50ZXJhY3Qgd2l0aCBhcmUgcHJlc2VudCBpbiB0aGUgRE9NLlxcbiAgICAgICAgYXdhaXQgY29udGV4dC5wYWdlLndhaXRfZm9yX3NlbGVjdG9yKCcuY29sbGVjdGlvbi1ibG9jay1pdGVtJylcXG5cXG4gICAgICAgICMgRXhlY3V0ZSBhIGZ1bmN0aW9uIHdpdGhpbiB0aGUgYnJvd3NlciBjb250ZXh0IHRvIHRhcmdldCB0aGUgY29sbGVjdGlvblxcbiAgICAgICAgIyBjYXJkIGVsZW1lbnRzIGFuZCBleHRyYWN0IHRoZWlyIHRleHQgY29udGVudCwgdHJpbW1pbmcgYW55IGxlYWRpbmcgb3JcXG4gICAgICAgICMgdHJhaWxpbmcgd2hpdGVzcGFjZS5cXG4gICAgICAgIGNhdGVnb3J5X3RleHRzID0gYXdhaXQgY29udGV4dC5wYWdlLmV2YWxfb25fc2VsZWN0b3JfYWxsKFxcbiAgICAgICAgICAgICcuY29sbGVjdGlvbi1ibG9jay1pdGVtJyxcXG4gICAgICAgICAgICAnKGVscykgPT4gZWxzLm1hcChlbCA9PiBlbC50ZXh0Q29udGVudC50cmltKCkpJyxcXG4gICAgICAgIClcXG5cXG4gICAgICAgICMgTG9nIHRoZSBleHRyYWN0ZWQgdGV4dHMuXFxuICAgICAgICBmb3IgaSwgdGV4dCBpbiBlbnVtZXJhdGUoY2F0ZWdvcnlfdGV4dHMpOlxcbiAgICAgICAgICAgIGNvbnRleHQubG9nLmluZm8oZidDQVRFR09SWV97aSArIDF9OiB7dGV4dH0nKVxcblxcbiAgICBhd2FpdCBjcmF3bGVyLnJ1bihbJ2h0dHBzOi8vd2FyZWhvdXNlLXRoZW1lLW1ldGFsLm15c2hvcGlmeS5jb20vY29sbGVjdGlvbnMnXSlcXG5cXG5cXG5pZiBfX25hbWVfXyA9PSAnX19tYWluX18nOlxcbiAgICBhc3luY2lvLnJ1bihtYWluKCkpXFxuXCJ9Iiwib3B0aW9ucyI6eyJidWlsZCI6ImxhdGVzdCIsImNvbnRlbnRUeXBlIjoiYXBwbGljYXRpb24vanNvbjsgY2hhcnNldD11dGYtOCIsIm1lbW9yeSI6NDA5NiwidGltZW91dCI6MTgwfX0.nz8wkvaqD3c-jvkrLLrNDSMO6beEwztdRb3xXdkiJTI\&asrc=run_on_apify)

```
import asyncio



# Instead of BeautifulSoupCrawler let's use Playwright to be able to render JavaScript.

from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext





async def main() -> None:

    crawler = PlaywrightCrawler()



    @crawler.router.default_handler

    async def request_handler(context: PlaywrightCrawlingContext) -> None:

        # Wait for the collection cards to render on the page. This ensures that

        # the elements we want to interact with are present in the DOM.

        await context.page.wait_for_selector('.collection-block-item')



        # Execute a function within the browser context to target the collection

        # card elements and extract their text content, trimming any leading or

        # trailing whitespace.

        category_texts = await context.page.eval_on_selector_all(

            '.collection-block-item',

            '(els) => els.map(el => el.textContent.trim())',

        )



        # Log the extracted texts.

        for i, text in enumerate(category_texts):

            context.log.info(f'CATEGORY_{i + 1}: {text}')



    await crawler.run(['https://warehouse-theme-metal.myshopify.com/collections'])





if __name__ == '__main__':

    asyncio.run(main())
```

If you're wondering how to get that `.collection-block-item` selector. We'll explain it in the next chapter on DevTools.

## DevTools - the scraper's toolbox[​](#devtools---the-scrapers-toolbox "Direct link to DevTools - the scraper's toolbox")

DevTool choice

We'll use Chrome DevTools here, since it's the most common browser, but feel free to use any other, they're all very similar.

Let's open DevTools by going to <https://warehouse-theme-metal.myshopify.com/collections> in Chrome and then right-clicking anywhere in the page and selecting **Inspect**, or by pressing **F12** or whatever your system prefers. With DevTools, you can inspect or manipulate any aspect of the currently open web page. You can learn more about DevTools in their [official documentation](https://developer.chrome.com/docs/devtools/).

## Selecting elements[​](#selecting-elements "Direct link to Selecting elements")

In the DevTools, choose the **Select an element** tool and try hovering over one of the Actor cards.

![select an element](/python/assets/images/select-an-element-64d58df5af5cde98d2d63ba3e57af890.jpg "Finding the select an element tool.")

You'll see that you can select different elements inside the card. Instead, select the whole card, not just some of its contents, such as its title or description.

![selected element](/python/assets/images/selected-element-b2a329cd79075402842c664410116454.jpg "Selecting an element by hovering over it.")

Selecting an element will highlight it in the DevTools HTML inspector. When carefully look at the elements, you'll see that there are some **classes** attached to the different HTML elements. Those are called **CSS classes**, and we can make a use of them in scraping.

Conversely, by hovering over elements in the HTML inspector, you will see them highlight on the page. Inspect the page's structure around the collection card. You'll see that all the card's data is displayed in an `<a>` element with a `class` attribute that includes **collection-block-item**. It should now make sense how we got that `.collection-block-item` selector. It's just a way to find all elements that are annotated with the `collection-block-item`.

It's always a good idea to double-check that you're not getting any unwanted elements with this class. To do that, go into the **Console** tab of DevTools and run:

```
document.querySelectorAll('.collection-block-item');
```

You will see that only the 31 collection cards will be returned, and nothing else.

Learn more about CSS selectors and DevTools

CSS selectors and DevTools are quite a big topic. If you want to learn more, visit the [Web scraping for beginners course](https://developers.apify.com/academy/web-scraping-for-beginners) in the Apify Academy. **It's free and open-source** ❤️.

## Next steps[​](#next-steps "Direct link to Next steps")

Next, you will crawl the whole store, including all the listing pages and all the product detail pages.

[Edit this page](https://github.com/apify/crawlee-python/edit/master/website/versioned_docs/version-1.9/introduction/04_real_world_project.mdx)

Last updated

<!-- -->

on **Aug 4, 2026** by **Vlada Dusek**

[Previous](https://crawlee.dev/python/python/docs/introduction/adding-more-urls.md)

[Adding more URLs](https://crawlee.dev/python/python/docs/introduction/adding-more-urls.md)

[Next](https://crawlee.dev/python/python/docs/introduction/crawling.md)

[Crawling](https://crawlee.dev/python/python/docs/introduction/crawling.md)

* [](https://crawlee.dev/python/python)
* [Introduction](https://crawlee.dev/python/python/docs/introduction.md)
* Crawling

Version: 1.9

On this page

# Crawling

To crawl the whole [Warehouse store example](https://warehouse-theme-metal.myshopify.com/collections) and find all the data, you first need to visit all the pages with products - going through all categories available and also all the product detail pages.

## Crawling the listing pages[​](#crawling-the-listing-pages "Direct link to Crawling the listing pages")

In previous lessons, you used the [`enqueue_links`](https://crawlee.dev/python/python/api/class/EnqueueLinksFunction.md) function like this:

```
await enqueue_links()
```

While useful in that scenario, you need something different now. Instead of finding all the `<a href="..">` elements with links to the same hostname, you need to find only the specific ones that will take your crawler to the next page of results. Otherwise, the crawler will visit a lot of other pages that you're not interested in. Using the power of DevTools and yet another [`enqueue_links`](https://crawlee.dev/python/python/api/class/EnqueueLinksFunction.md) parameter, this becomes fairly easy.

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuXFxuZnJvbSBjcmF3bGVlLmNyYXdsZXJzIGltcG9ydCBQbGF5d3JpZ2h0Q3Jhd2xlciwgUGxheXdyaWdodENyYXdsaW5nQ29udGV4dFxcblxcblxcbmFzeW5jIGRlZiBtYWluKCkgLT4gTm9uZTpcXG4gICAgY3Jhd2xlciA9IFBsYXl3cmlnaHRDcmF3bGVyKClcXG5cXG4gICAgQGNyYXdsZXIucm91dGVyLmRlZmF1bHRfaGFuZGxlclxcbiAgICBhc3luYyBkZWYgcmVxdWVzdF9oYW5kbGVyKGNvbnRleHQ6IFBsYXl3cmlnaHRDcmF3bGluZ0NvbnRleHQpIC0-IE5vbmU6XFxuICAgICAgICBjb250ZXh0LmxvZy5pbmZvKGYnUHJvY2Vzc2luZyB7Y29udGV4dC5yZXF1ZXN0LnVybH0nKVxcblxcbiAgICAgICAgIyBXYWl0IGZvciB0aGUgY2F0ZWdvcnkgY2FyZHMgdG8gcmVuZGVyIG9uIHRoZSBwYWdlLiBUaGlzIGVuc3VyZXMgdGhhdFxcbiAgICAgICAgIyB0aGUgZWxlbWVudHMgd2Ugd2FudCB0byBpbnRlcmFjdCB3aXRoIGFyZSBwcmVzZW50IGluIHRoZSBET00uXFxuICAgICAgICBhd2FpdCBjb250ZXh0LnBhZ2Uud2FpdF9mb3Jfc2VsZWN0b3IoJy5jb2xsZWN0aW9uLWJsb2NrLWl0ZW0nKVxcblxcbiAgICAgICAgIyBFbnF1ZXVlIGxpbmtzIGZvdW5kIHdpdGhpbiBlbGVtZW50cyB0aGF0IG1hdGNoIHRoZSBzcGVjaWZpZWQgc2VsZWN0b3IuXFxuICAgICAgICAjIFRoZXNlIGxpbmtzIHdpbGwgYmUgYWRkZWQgdG8gdGhlIGNyYXdsaW5nIHF1ZXVlIHdpdGggdGhlIGxhYmVsIENBVEVHT1JZLlxcbiAgICAgICAgYXdhaXQgY29udGV4dC5lbnF1ZXVlX2xpbmtzKFxcbiAgICAgICAgICAgIHNlbGVjdG9yPScuY29sbGVjdGlvbi1ibG9jay1pdGVtJyxcXG4gICAgICAgICAgICBsYWJlbD0nQ0FURUdPUlknLFxcbiAgICAgICAgKVxcblxcbiAgICBhd2FpdCBjcmF3bGVyLnJ1bihbJ2h0dHBzOi8vd2FyZWhvdXNlLXRoZW1lLW1ldGFsLm15c2hvcGlmeS5jb20vY29sbGVjdGlvbnMnXSlcXG5cXG5cXG5pZiBfX25hbWVfXyA9PSAnX19tYWluX18nOlxcbiAgICBhc3luY2lvLnJ1bihtYWluKCkpXFxuXCJ9Iiwib3B0aW9ucyI6eyJidWlsZCI6ImxhdGVzdCIsImNvbnRlbnRUeXBlIjoiYXBwbGljYXRpb24vanNvbjsgY2hhcnNldD11dGYtOCIsIm1lbW9yeSI6NDA5NiwidGltZW91dCI6MTgwfX0.X9WWCidJxivEV99HXElBusVeZZu2wf-ZTDSkyUZJ0Ew\&asrc=run_on_apify)

```
import asyncio



from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext





async def main() -> None:

    crawler = PlaywrightCrawler()



    @crawler.router.default_handler

    async def request_handler(context: PlaywrightCrawlingContext) -> None:

        context.log.info(f'Processing {context.request.url}')



        # Wait for the category cards to render on the page. This ensures that

        # the elements we want to interact with are present in the DOM.

        await context.page.wait_for_selector('.collection-block-item')



        # Enqueue links found within elements that match the specified selector.

        # These links will be added to the crawling queue with the label CATEGORY.

        await context.enqueue_links(

            selector='.collection-block-item',

            label='CATEGORY',

        )



    await crawler.run(['https://warehouse-theme-metal.myshopify.com/collections'])





if __name__ == '__main__':

    asyncio.run(main())
```

The code should look pretty familiar to you. It's a very simple request handler where we log the currently processed URL to the console and enqueue more links. But there are also a few new, interesting additions. Let's break it down.

### The `selector` parameter of `enqueue_links`[​](#the-selector-parameter-of-enqueue_links "Direct link to the-selector-parameter-of-enqueue_links")

When you previously used [`enqueue_links`](https://crawlee.dev/python/python/api/class/EnqueueLinksFunction.md), you were not providing any `selector` parameter, and it was fine, because you wanted to use the default value, which is `a` - finds all `<a>` elements. But now, you need to be more specific. There are multiple `<a>` links on the `Categories` page, and you're only interested in those that will take your crawler to the available list of results. Using the DevTools, you'll find that you can select the links you need using the `.collection-block-item` selector, which selects all the elements that have the `class=collection-block-item` attribute.

### The `label` of `enqueue_links`[​](#the-label-of-enqueue_links "Direct link to the-label-of-enqueue_links")

You will see `label` used often throughout Crawlee, as it's a convenient way of labelling a [`Request`](https://crawlee.dev/python/python/api/class/Request.md) instance for quick identification later. You can access it with `request.label` and it's a `string`. You can name your requests any way you want. Here, we used the label `CATEGORY` to note that we're enqueueing pages that represent a category of products. The [`enqueue_links`](https://crawlee.dev/python/python/api/class/EnqueueLinksFunction.md) function will add this label to all requests before enqueueing them to the [`RequestQueue`](https://crawlee.dev/python/python/api/class/RequestQueue.md). Why this is useful will become obvious in a minute.

## Crawling the detail pages[​](#crawling-the-detail-pages "Direct link to Crawling the detail pages")

In a similar fashion, you need to collect all the URLs to the product detail pages, because only from there you can scrape all the data you need. The following code only repeats the concepts you already know for another set of links.

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuXFxuZnJvbSBjcmF3bGVlLmNyYXdsZXJzIGltcG9ydCBQbGF5d3JpZ2h0Q3Jhd2xlciwgUGxheXdyaWdodENyYXdsaW5nQ29udGV4dFxcblxcblxcbmFzeW5jIGRlZiBtYWluKCkgLT4gTm9uZTpcXG4gICAgY3Jhd2xlciA9IFBsYXl3cmlnaHRDcmF3bGVyKClcXG5cXG4gICAgQGNyYXdsZXIucm91dGVyLmRlZmF1bHRfaGFuZGxlclxcbiAgICBhc3luYyBkZWYgcmVxdWVzdF9oYW5kbGVyKGNvbnRleHQ6IFBsYXl3cmlnaHRDcmF3bGluZ0NvbnRleHQpIC0-IE5vbmU6XFxuICAgICAgICBjb250ZXh0LmxvZy5pbmZvKGYnUHJvY2Vzc2luZyB7Y29udGV4dC5yZXF1ZXN0LnVybH0nKVxcblxcbiAgICAgICAgIyBXZSdyZSBub3QgcHJvY2Vzc2luZyBkZXRhaWwgcGFnZXMgeWV0LCBzbyB3ZSBqdXN0IHBhc3MuXFxuICAgICAgICBpZiBjb250ZXh0LnJlcXVlc3QubGFiZWwgPT0gJ0RFVEFJTCc6XFxuICAgICAgICAgICAgcGFzc1xcblxcbiAgICAgICAgIyBXZSBhcmUgbm93IG9uIGEgY2F0ZWdvcnkgcGFnZS4gV2UgY2FuIHVzZSB0aGlzIHRvIHBhZ2luYXRlIHRocm91Z2ggYW5kXFxuICAgICAgICAjIGVucXVldWUgYWxsIHByb2R1Y3RzLCBhcyB3ZWxsIGFzIGFueSBzdWJzZXF1ZW50IHBhZ2VzIHdlIGZpbmQuXFxuICAgICAgICBlbGlmIGNvbnRleHQucmVxdWVzdC5sYWJlbCA9PSAnQ0FURUdPUlknOlxcbiAgICAgICAgICAgICMgV2FpdCBmb3IgdGhlIHByb2R1Y3QgaXRlbXMgdG8gcmVuZGVyLlxcbiAgICAgICAgICAgIGF3YWl0IGNvbnRleHQucGFnZS53YWl0X2Zvcl9zZWxlY3RvcignLnByb2R1Y3QtaXRlbSA-IGEnKVxcblxcbiAgICAgICAgICAgICMgRW5xdWV1ZSBsaW5rcyBmb3VuZCB3aXRoaW4gZWxlbWVudHMgbWF0Y2hpbmcgdGhlIHByb3ZpZGVkIHNlbGVjdG9yLlxcbiAgICAgICAgICAgICMgVGhlc2UgbGlua3Mgd2lsbCBiZSBhZGRlZCB0byB0aGUgY3Jhd2xpbmcgcXVldWUgd2l0aCB0aGUgbGFiZWwgREVUQUlMLlxcbiAgICAgICAgICAgIGF3YWl0IGNvbnRleHQuZW5xdWV1ZV9saW5rcyhcXG4gICAgICAgICAgICAgICAgc2VsZWN0b3I9Jy5wcm9kdWN0LWl0ZW0gPiBhJyxcXG4gICAgICAgICAgICAgICAgbGFiZWw9J0RFVEFJTCcsXFxuICAgICAgICAgICAgKVxcblxcbiAgICAgICAgICAgICMgRmluZCB0aGUgXFxcIk5leHRcXFwiIGJ1dHRvbiB0byBwYWdpbmF0ZSB0aHJvdWdoIHRoZSBjYXRlZ29yeSBwYWdlcy5cXG4gICAgICAgICAgICBuZXh0X2J1dHRvbiA9IGF3YWl0IGNvbnRleHQucGFnZS5xdWVyeV9zZWxlY3RvcignYS5wYWdpbmF0aW9uX19uZXh0JylcXG5cXG4gICAgICAgICAgICAjIElmIGEgXFxcIk5leHRcXFwiIGJ1dHRvbiBpcyBmb3VuZCwgZW5xdWV1ZSB0aGUgbmV4dCBwYWdlIG9mIHJlc3VsdHMuXFxuICAgICAgICAgICAgaWYgbmV4dF9idXR0b246XFxuICAgICAgICAgICAgICAgIGF3YWl0IGNvbnRleHQuZW5xdWV1ZV9saW5rcyhcXG4gICAgICAgICAgICAgICAgICAgIHNlbGVjdG9yPSdhLnBhZ2luYXRpb25fX25leHQnLFxcbiAgICAgICAgICAgICAgICAgICAgbGFiZWw9J0NBVEVHT1JZJyxcXG4gICAgICAgICAgICAgICAgKVxcblxcbiAgICAgICAgIyBUaGlzIGluZGljYXRlcyB3ZSdyZSBvbiB0aGUgc3RhcnQgcGFnZSB3aXRoIG5vIHNwZWNpZmljIGxhYmVsLlxcbiAgICAgICAgIyBPbiB0aGUgc3RhcnQgcGFnZSwgd2Ugd2FudCB0byBlbnF1ZXVlIGFsbCB0aGUgY2F0ZWdvcnkgcGFnZXMuXFxuICAgICAgICBlbHNlOlxcbiAgICAgICAgICAgICMgV2FpdCBmb3IgdGhlIGNvbGxlY3Rpb24gY2FyZHMgdG8gcmVuZGVyLlxcbiAgICAgICAgICAgIGF3YWl0IGNvbnRleHQucGFnZS53YWl0X2Zvcl9zZWxlY3RvcignLmNvbGxlY3Rpb24tYmxvY2staXRlbScpXFxuXFxuICAgICAgICAgICAgIyBFbnF1ZXVlIGxpbmtzIGZvdW5kIHdpdGhpbiBlbGVtZW50cyBtYXRjaGluZyB0aGUgcHJvdmlkZWQgc2VsZWN0b3IuXFxuICAgICAgICAgICAgIyBUaGVzZSBsaW5rcyB3aWxsIGJlIGFkZGVkIHRvIHRoZSBjcmF3bGluZyBxdWV1ZSB3aXRoIHRoZSBsYWJlbCBDQVRFR09SWS5cXG4gICAgICAgICAgICBhd2FpdCBjb250ZXh0LmVucXVldWVfbGlua3MoXFxuICAgICAgICAgICAgICAgIHNlbGVjdG9yPScuY29sbGVjdGlvbi1ibG9jay1pdGVtJyxcXG4gICAgICAgICAgICAgICAgbGFiZWw9J0NBVEVHT1JZJyxcXG4gICAgICAgICAgICApXFxuXFxuICAgIGF3YWl0IGNyYXdsZXIucnVuKFsnaHR0cHM6Ly93YXJlaG91c2UtdGhlbWUtbWV0YWwubXlzaG9waWZ5LmNvbS9jb2xsZWN0aW9ucyddKVxcblxcblxcbmlmIF9fbmFtZV9fID09ICdfX21haW5fXyc6XFxuICAgIGFzeW5jaW8ucnVuKG1haW4oKSlcXG5cIn0iLCJvcHRpb25zIjp7ImJ1aWxkIjoibGF0ZXN0IiwiY29udGVudFR5cGUiOiJhcHBsaWNhdGlvbi9qc29uOyBjaGFyc2V0PXV0Zi04IiwibWVtb3J5Ijo0MDk2LCJ0aW1lb3V0IjoxODB9fQ.moljdzO1LGX-DchS3DDHfhUU9aGpzgHDLeBfzX_Q76Q\&asrc=run_on_apify)

```
import asyncio



from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext





async def main() -> None:

    crawler = PlaywrightCrawler()



    @crawler.router.default_handler

    async def request_handler(context: PlaywrightCrawlingContext) -> None:

        context.log.info(f'Processing {context.request.url}')



        # We're not processing detail pages yet, so we just pass.

        if context.request.label == 'DETAIL':

            pass



        # We are now on a category page. We can use this to paginate through and

        # enqueue all products, as well as any subsequent pages we find.

        elif context.request.label == 'CATEGORY':

            # Wait for the product items to render.

            await context.page.wait_for_selector('.product-item > a')



            # Enqueue links found within elements matching the provided selector.

            # These links will be added to the crawling queue with the label DETAIL.

            await context.enqueue_links(

                selector='.product-item > a',

                label='DETAIL',

            )



            # Find the "Next" button to paginate through the category pages.

            next_button = await context.page.query_selector('a.pagination__next')



            # If a "Next" button is found, enqueue the next page of results.

            if next_button:

                await context.enqueue_links(

                    selector='a.pagination__next',

                    label='CATEGORY',

                )



        # This indicates we're on the start page with no specific label.

        # On the start page, we want to enqueue all the category pages.

        else:

            # Wait for the collection cards to render.

            await context.page.wait_for_selector('.collection-block-item')



            # Enqueue links found within elements matching the provided selector.

            # These links will be added to the crawling queue with the label CATEGORY.

            await context.enqueue_links(

                selector='.collection-block-item',

                label='CATEGORY',

            )



    await crawler.run(['https://warehouse-theme-metal.myshopify.com/collections'])





if __name__ == '__main__':

    asyncio.run(main())
```

The crawling code is now complete. When you run the code, you'll see the crawler visit all the listing URLs and all the detail URLs.

## Next steps[​](#next-steps "Direct link to Next steps")

This concludes the Crawling lesson, because you have taught the crawler to visit all the pages it needs. Let's continue with scraping data.

[Edit this page](https://github.com/apify/crawlee-python/edit/master/website/versioned_docs/version-1.9/introduction/05_crawling.mdx)

Last updated

<!-- -->

on **Aug 4, 2026** by **Vlada Dusek**

[Previous](https://crawlee.dev/python/python/docs/introduction/real-world-project.md)

[Real-world project](https://crawlee.dev/python/python/docs/introduction/real-world-project.md)

[Next](https://crawlee.dev/python/python/docs/introduction/scraping.md)

[Scraping](https://crawlee.dev/python/python/docs/introduction/scraping.md)

* [](https://crawlee.dev/python/python)
* [Introduction](https://crawlee.dev/python/python/docs/introduction.md)
* Scraping

Version: 1.9

On this page

# Scraping

In the [Real-world project](https://crawlee.dev/python/python/docs/introduction/real-world-project.md#choosing-the-data-you-need) chapter, you've created a list of the information you wanted to collect about the products in the example Warehouse store. Let's review that and figure out ways to access the data.

* URL
* Manufacturer
* SKU
* Title
* Current price
* Stock available

![data to scrape](/python/assets/images/scraping-practice-c3a7bcc681e36946e25b1f8cfd090a8a.jpg "Overview of data to be scraped.")

## Scraping the URL and manufacturer[​](#scraping-the-url-and-manufacturer "Direct link to Scraping the URL and manufacturer")

Some information is lying right there in front of us without even having to touch the product detail pages. The `URL` we already have - the `context.request.url`. And by looking at it carefully, we realize that we can also extract the manufacturer from the URL (as all product urls start with `/products/<manufacturer>`). We can just split the `string` and be on our way then!

url vs loaded url

You can use `request.loaded_url` as well. Remember the difference: `request.url` is what you enqueue, `request.loaded_url` is what gets processed (after possible redirects).

By splitting the `request.url`, we can extract the manufacturer name directly from the URL. This is done by first splitting the URL to get the product identifier and then splitting that identifier to get the manufacturer name.

```
# context.request.url:

# https://warehouse-theme-metal.myshopify.com/products/sennheiser-mke-440-professional-stereo-shotgun-microphone-mke-440



# Split the URL and get the last part.

url_part = context.request.url.split('/').pop()

# url_part: sennheiser-mke-440-professional-stereo-shotgun-microphone-mke-440



# Split the last part by '-' and get the first element.

manufacturer = url_part.split('-')[0]

# manufacturer: 'sennheiser'
```

Storing information

It's a matter of preference, whether to store this information separately in the resulting dataset, or not. Whoever uses the dataset can easily parse the `manufacturer` from the `URL`, so should you duplicate the data unnecessarily? Our opinion is that unless the increased data consumption would be too large to bear, it's better to make the dataset as rich as possible. For example, someone might want to filter by `manufacturer`.

Adapt and extract

One thing you may notice is that the `manufacturer` might have a `-` in its name. If that's the case, your best bet is extracting it from the details page instead, but it's not mandatory. At the end of the day, you should always adjust and pick the best solution for your use case, and website you are crawling.

Now it's time to add more data to the results. Let's open one of the product detail pages, for example the [Sony XBR-950G](https://warehouse-theme-metal.myshopify.com/products/sony-xbr-65x950g-65-class-64-5-diag-bravia-4k-hdr-ultra-hd-tv) page and use our DevTools-Fu 🥋 to figure out how to get the title of the product.

## Scraping title[​](#scraping-title "Direct link to Scraping title")

To scrape the product title from a webpage, you need to identify its location in the HTML structure. By using the element selector tool in your browser's DevTools, you can see that the title is within an `<h1>` tag, which is a common practice for important headers. This `<h1>` tag is enclosed in a `<div>` with the class product-meta. We can leverage this structure to create a combined selector `.product-meta h1`. This selector targets any `<h1>` element that is a child of an element with the class `product-meta`.

![product title](/python/assets/images/title-ead2d5aff4a326c2268db2b640d3db9d.jpg "Finding product title in DevTools.")

Verifying selectors with DevTools

Remember that you can press CTRL+F (or CMD+F on Mac) in the **Elements** tab of DevTools to open the search bar where you can quickly search for elements using their selectors. Always verify your scraping process and assumptions using the DevTools. It's faster than changing the crawler code all the time.

To get the title, you need to locate it using Playwright with the `.product-meta h1` selector. This selector specifically targets the `<h1>` element you need. If multiple elements match, it will throw an error, which is beneficial as it prevents returning incorrect data silently. Ensuring the accuracy of your selectors is crucial for reliable data extraction.

```
title = await context.page.locator('.product-meta h1').text_content()
```

## Scraping SKU[​](#scraping-sku "Direct link to Scraping SKU")

Using the DevTools, you can find that the product SKU is inside a `<span>` tag with the class `product-meta__sku-number`. Since there is no other `<span>` with that class on the page, you can safely use this selector to extract the SKU.

![product sku selector](/python/assets/images/sku-dbf299877f71a3c4a03fb52f01e1c202.jpg "Finding product SKU in DevTools.")

```
# Find the SKU element using the selector and get its text content.

sku = await context.page.locator('span.product-meta__sku-number').text_content()
```

## Scraping current price[​](#scraping-current-price "Direct link to Scraping current price")

Using DevTools, you can find that the current price is within a `<span>` element tagged with the `price` class. However, it is nested alongside another `<span>` element with the `visually-hidden` class. To avoid extracting the wrong text, you can filter the elements to get the correct one using the `has_text` helper.

![product current price selector](/python/assets/images/current-price-31a43915970fa9a766b57392b8f1f764.jpg "Finding product current price in DevTools.")

```
# Locate the price element and filter out the visually hidden elements.

price_element = context.page.locator('span.price', has_text='$').first



# Extract the text content of the price element.

current_price_string = await price_element.text_content() or ''

# current_price_string: 'Sale price$1,398.00'



# Split the string by the '$' sign to get the numeric part.

raw_price = current_price_string.split('$')[1]

# raw_price: '1,398.00'



# Convert the raw price string to a float after removing commas.

price = float(raw_price.replace(',', ''))

# price: 1398.00
```

It might look a little complex at first glance, but let's walk through what you did. First, you locate the correct part of the `price` span by filtering for elements containing the `$` sign. This ensures that you get the actual price element. Once you have the right element, you extract its text content, which gives you a string similar to `Sale price$1,398.00`. To get the numeric value, you split this string by the `$` sign. Next, you remove any commas from the resulting numeric string and convert it to a float, allowing you to work with the price as a number. This process ensures that you accurately extract and convert the current price from the product page.

## Scraping stock availability[​](#scraping-stock-availability "Direct link to Scraping stock availability")

The final step is to scrape the stock availability information. There is a `<span>` with the class `product-form__inventory`, which contains the text `In stock` if the product is available. You can use the `has_text` helper to filter out the correct element.

```
# Locate the element that contains the text 'In stock' and filter out other elements.

in_stock_element = context.page.locator(

    selector='span.product-form__inventory',

    has_text='In stock',

).first



# Check if the element exists by counting the matching elements.

in_stock = await in_stock_element.count() > 0
```

For this, all that matters is whether the element exists or not. You can use the `count()` method to check if any elements match the selector. If there are, it means the product is in stock.

## Trying it out[​](#trying-it-out "Direct link to Trying it out")

You have everything that is needed, so grab your newly created scraping logic, dump it into your original request handler and see the magic happen!

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuXFxuZnJvbSBjcmF3bGVlLmNyYXdsZXJzIGltcG9ydCBQbGF5d3JpZ2h0Q3Jhd2xlciwgUGxheXdyaWdodENyYXdsaW5nQ29udGV4dFxcblxcblxcbmFzeW5jIGRlZiBtYWluKCkgLT4gTm9uZTpcXG4gICAgY3Jhd2xlciA9IFBsYXl3cmlnaHRDcmF3bGVyKFxcbiAgICAgICAgIyBMZXQncyBsaW1pdCBvdXIgY3Jhd2xzIHRvIG1ha2Ugb3VyIHRlc3RzIHNob3J0ZXIgYW5kIHNhZmVyLlxcbiAgICAgICAgbWF4X3JlcXVlc3RzX3Blcl9jcmF3bD0xMCxcXG4gICAgKVxcblxcbiAgICBAY3Jhd2xlci5yb3V0ZXIuZGVmYXVsdF9oYW5kbGVyXFxuICAgIGFzeW5jIGRlZiByZXF1ZXN0X2hhbmRsZXIoY29udGV4dDogUGxheXdyaWdodENyYXdsaW5nQ29udGV4dCkgLT4gTm9uZTpcXG4gICAgICAgIGNvbnRleHQubG9nLmluZm8oZidQcm9jZXNzaW5nIHtjb250ZXh0LnJlcXVlc3QudXJsfScpXFxuXFxuICAgICAgICAjIFdlJ3JlIG5vdCBwcm9jZXNzaW5nIGRldGFpbCBwYWdlcyB5ZXQsIHNvIHdlIGp1c3QgcGFzcy5cXG4gICAgICAgIGlmIGNvbnRleHQucmVxdWVzdC5sYWJlbCA9PSAnREVUQUlMJzpcXG4gICAgICAgICAgICAjIFNwbGl0IHRoZSBVUkwgYW5kIGdldCB0aGUgbGFzdCBwYXJ0IHRvIGV4dHJhY3QgdGhlIG1hbnVmYWN0dXJlci5cXG4gICAgICAgICAgICB1cmxfcGFydCA9IGNvbnRleHQucmVxdWVzdC51cmwuc3BsaXQoJy8nKS5wb3AoKVxcbiAgICAgICAgICAgIG1hbnVmYWN0dXJlciA9IHVybF9wYXJ0LnNwbGl0KCctJylbMF1cXG5cXG4gICAgICAgICAgICAjIEV4dHJhY3QgdGhlIHRpdGxlIHVzaW5nIHRoZSBjb21iaW5lZCBzZWxlY3Rvci5cXG4gICAgICAgICAgICB0aXRsZSA9IGF3YWl0IGNvbnRleHQucGFnZS5sb2NhdG9yKCcucHJvZHVjdC1tZXRhIGgxJykudGV4dF9jb250ZW50KClcXG5cXG4gICAgICAgICAgICAjIEV4dHJhY3QgdGhlIFNLVSB1c2luZyBpdHMgc2VsZWN0b3IuXFxuICAgICAgICAgICAgc2t1ID0gYXdhaXQgY29udGV4dC5wYWdlLmxvY2F0b3IoXFxuICAgICAgICAgICAgICAgICdzcGFuLnByb2R1Y3QtbWV0YV9fc2t1LW51bWJlcidcXG4gICAgICAgICAgICApLnRleHRfY29udGVudCgpXFxuXFxuICAgICAgICAgICAgIyBMb2NhdGUgdGhlIHByaWNlIGVsZW1lbnQgdGhhdCBjb250YWlucyB0aGUgJyQnIHNpZ24gYW5kIGZpbHRlciBvdXRcXG4gICAgICAgICAgICAjIHRoZSB2aXN1YWxseSBoaWRkZW4gZWxlbWVudHMuXFxuICAgICAgICAgICAgcHJpY2VfZWxlbWVudCA9IGNvbnRleHQucGFnZS5sb2NhdG9yKCdzcGFuLnByaWNlJywgaGFzX3RleHQ9JyQnKS5maXJzdFxcbiAgICAgICAgICAgIGN1cnJlbnRfcHJpY2Vfc3RyaW5nID0gYXdhaXQgcHJpY2VfZWxlbWVudC50ZXh0X2NvbnRlbnQoKSBvciAnJ1xcbiAgICAgICAgICAgIHJhd19wcmljZSA9IGN1cnJlbnRfcHJpY2Vfc3RyaW5nLnNwbGl0KCckJylbMV1cXG4gICAgICAgICAgICBwcmljZSA9IGZsb2F0KHJhd19wcmljZS5yZXBsYWNlKCcsJywgJycpKVxcblxcbiAgICAgICAgICAgICMgTG9jYXRlIHRoZSBlbGVtZW50IHRoYXQgY29udGFpbnMgdGhlIHRleHQgJ0luIHN0b2NrJ1xcbiAgICAgICAgICAgICMgYW5kIGZpbHRlciBvdXQgb3RoZXIgZWxlbWVudHMuXFxuICAgICAgICAgICAgaW5fc3RvY2tfZWxlbWVudCA9IGNvbnRleHQucGFnZS5sb2NhdG9yKFxcbiAgICAgICAgICAgICAgICBzZWxlY3Rvcj0nc3Bhbi5wcm9kdWN0LWZvcm1fX2ludmVudG9yeScsXFxuICAgICAgICAgICAgICAgIGhhc190ZXh0PSdJbiBzdG9jaycsXFxuICAgICAgICAgICAgKS5maXJzdFxcbiAgICAgICAgICAgIGluX3N0b2NrID0gYXdhaXQgaW5fc3RvY2tfZWxlbWVudC5jb3VudCgpID4gMFxcblxcbiAgICAgICAgICAgICMgUHV0IGl0IGFsbCB0b2dldGhlciBpbiBhIGRpY3Rpb25hcnkuXFxuICAgICAgICAgICAgZGF0YSA9IHtcXG4gICAgICAgICAgICAgICAgJ21hbnVmYWN0dXJlcic6IG1hbnVmYWN0dXJlcixcXG4gICAgICAgICAgICAgICAgJ3RpdGxlJzogdGl0bGUsXFxuICAgICAgICAgICAgICAgICdza3UnOiBza3UsXFxuICAgICAgICAgICAgICAgICdwcmljZSc6IHByaWNlLFxcbiAgICAgICAgICAgICAgICAnaW5fc3RvY2snOiBpbl9zdG9jayxcXG4gICAgICAgICAgICB9XFxuXFxuICAgICAgICAgICAgIyBQcmludCB0aGUgZXh0cmFjdGVkIGRhdGEuXFxuICAgICAgICAgICAgY29udGV4dC5sb2cuaW5mbyhkYXRhKVxcblxcbiAgICAgICAgIyBXZSBhcmUgbm93IG9uIGEgY2F0ZWdvcnkgcGFnZS4gV2UgY2FuIHVzZSB0aGlzIHRvIHBhZ2luYXRlIHRocm91Z2ggYW5kXFxuICAgICAgICAjIGVucXVldWUgYWxsIHByb2R1Y3RzLCBhcyB3ZWxsIGFzIGFueSBzdWJzZXF1ZW50IHBhZ2VzIHdlIGZpbmQuXFxuICAgICAgICBlbGlmIGNvbnRleHQucmVxdWVzdC5sYWJlbCA9PSAnQ0FURUdPUlknOlxcbiAgICAgICAgICAgICMgV2FpdCBmb3IgdGhlIHByb2R1Y3QgaXRlbXMgdG8gcmVuZGVyLlxcbiAgICAgICAgICAgIGF3YWl0IGNvbnRleHQucGFnZS53YWl0X2Zvcl9zZWxlY3RvcignLnByb2R1Y3QtaXRlbSA-IGEnKVxcblxcbiAgICAgICAgICAgICMgRW5xdWV1ZSBsaW5rcyBmb3VuZCB3aXRoaW4gZWxlbWVudHMgbWF0Y2hpbmcgdGhlIHByb3ZpZGVkIHNlbGVjdG9yLlxcbiAgICAgICAgICAgICMgVGhlc2UgbGlua3Mgd2lsbCBiZSBhZGRlZCB0byB0aGUgY3Jhd2xpbmcgcXVldWUgd2l0aCB0aGUgbGFiZWwgREVUQUlMLlxcbiAgICAgICAgICAgIGF3YWl0IGNvbnRleHQuZW5xdWV1ZV9saW5rcyhcXG4gICAgICAgICAgICAgICAgc2VsZWN0b3I9Jy5wcm9kdWN0LWl0ZW0gPiBhJyxcXG4gICAgICAgICAgICAgICAgbGFiZWw9J0RFVEFJTCcsXFxuICAgICAgICAgICAgKVxcblxcbiAgICAgICAgICAgICMgRmluZCB0aGUgXFxcIk5leHRcXFwiIGJ1dHRvbiB0byBwYWdpbmF0ZSB0aHJvdWdoIHRoZSBjYXRlZ29yeSBwYWdlcy5cXG4gICAgICAgICAgICBuZXh0X2J1dHRvbiA9IGF3YWl0IGNvbnRleHQucGFnZS5xdWVyeV9zZWxlY3RvcignYS5wYWdpbmF0aW9uX19uZXh0JylcXG5cXG4gICAgICAgICAgICAjIElmIGEgXFxcIk5leHRcXFwiIGJ1dHRvbiBpcyBmb3VuZCwgZW5xdWV1ZSB0aGUgbmV4dCBwYWdlIG9mIHJlc3VsdHMuXFxuICAgICAgICAgICAgaWYgbmV4dF9idXR0b246XFxuICAgICAgICAgICAgICAgIGF3YWl0IGNvbnRleHQuZW5xdWV1ZV9saW5rcyhcXG4gICAgICAgICAgICAgICAgICAgIHNlbGVjdG9yPSdhLnBhZ2luYXRpb25fX25leHQnLFxcbiAgICAgICAgICAgICAgICAgICAgbGFiZWw9J0NBVEVHT1JZJyxcXG4gICAgICAgICAgICAgICAgKVxcblxcbiAgICAgICAgIyBUaGlzIGluZGljYXRlcyB3ZSdyZSBvbiB0aGUgc3RhcnQgcGFnZSB3aXRoIG5vIHNwZWNpZmljIGxhYmVsLlxcbiAgICAgICAgIyBPbiB0aGUgc3RhcnQgcGFnZSwgd2Ugd2FudCB0byBlbnF1ZXVlIGFsbCB0aGUgY2F0ZWdvcnkgcGFnZXMuXFxuICAgICAgICBlbHNlOlxcbiAgICAgICAgICAgICMgV2FpdCBmb3IgdGhlIGNvbGxlY3Rpb24gY2FyZHMgdG8gcmVuZGVyLlxcbiAgICAgICAgICAgIGF3YWl0IGNvbnRleHQucGFnZS53YWl0X2Zvcl9zZWxlY3RvcignLmNvbGxlY3Rpb24tYmxvY2staXRlbScpXFxuXFxuICAgICAgICAgICAgIyBFbnF1ZXVlIGxpbmtzIGZvdW5kIHdpdGhpbiBlbGVtZW50cyBtYXRjaGluZyB0aGUgcHJvdmlkZWQgc2VsZWN0b3IuXFxuICAgICAgICAgICAgIyBUaGVzZSBsaW5rcyB3aWxsIGJlIGFkZGVkIHRvIHRoZSBjcmF3bGluZyBxdWV1ZSB3aXRoIHRoZSBsYWJlbCBDQVRFR09SWS5cXG4gICAgICAgICAgICBhd2FpdCBjb250ZXh0LmVucXVldWVfbGlua3MoXFxuICAgICAgICAgICAgICAgIHNlbGVjdG9yPScuY29sbGVjdGlvbi1ibG9jay1pdGVtJyxcXG4gICAgICAgICAgICAgICAgbGFiZWw9J0NBVEVHT1JZJyxcXG4gICAgICAgICAgICApXFxuXFxuICAgIGF3YWl0IGNyYXdsZXIucnVuKFsnaHR0cHM6Ly93YXJlaG91c2UtdGhlbWUtbWV0YWwubXlzaG9waWZ5LmNvbS9jb2xsZWN0aW9ucyddKVxcblxcblxcbmlmIF9fbmFtZV9fID09ICdfX21haW5fXyc6XFxuICAgIGFzeW5jaW8ucnVuKG1haW4oKSlcXG5cIn0iLCJvcHRpb25zIjp7ImJ1aWxkIjoibGF0ZXN0IiwiY29udGVudFR5cGUiOiJhcHBsaWNhdGlvbi9qc29uOyBjaGFyc2V0PXV0Zi04IiwibWVtb3J5Ijo0MDk2LCJ0aW1lb3V0IjoxODB9fQ.S0H-0OH57HUd7McisdrTLitNGpf_mV9o2tXD2JY1Vc4\&asrc=run_on_apify)

```
import asyncio



from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext





async def main() -> None:

    crawler = PlaywrightCrawler(

        # Let's limit our crawls to make our tests shorter and safer.

        max_requests_per_crawl=10,

    )



    @crawler.router.default_handler

    async def request_handler(context: PlaywrightCrawlingContext) -> None:

        context.log.info(f'Processing {context.request.url}')



        # We're not processing detail pages yet, so we just pass.

        if context.request.label == 'DETAIL':

            # Split the URL and get the last part to extract the manufacturer.

            url_part = context.request.url.split('/').pop()

            manufacturer = url_part.split('-')[0]



            # Extract the title using the combined selector.

            title = await context.page.locator('.product-meta h1').text_content()



            # Extract the SKU using its selector.

            sku = await context.page.locator(

                'span.product-meta__sku-number'

            ).text_content()



            # Locate the price element that contains the '$' sign and filter out

            # the visually hidden elements.

            price_element = context.page.locator('span.price', has_text='$').first

            current_price_string = await price_element.text_content() or ''

            raw_price = current_price_string.split('$')[1]

            price = float(raw_price.replace(',', ''))



            # Locate the element that contains the text 'In stock'

            # and filter out other elements.

            in_stock_element = context.page.locator(

                selector='span.product-form__inventory',

                has_text='In stock',

            ).first

            in_stock = await in_stock_element.count() > 0



            # Put it all together in a dictionary.

            data = {

                'manufacturer': manufacturer,

                'title': title,

                'sku': sku,

                'price': price,

                'in_stock': in_stock,

            }



            # Print the extracted data.

            context.log.info(data)



        # We are now on a category page. We can use this to paginate through and

        # enqueue all products, as well as any subsequent pages we find.

        elif context.request.label == 'CATEGORY':

            # Wait for the product items to render.

            await context.page.wait_for_selector('.product-item > a')



            # Enqueue links found within elements matching the provided selector.

            # These links will be added to the crawling queue with the label DETAIL.

            await context.enqueue_links(

                selector='.product-item > a',

                label='DETAIL',

            )



            # Find the "Next" button to paginate through the category pages.

            next_button = await context.page.query_selector('a.pagination__next')



            # If a "Next" button is found, enqueue the next page of results.

            if next_button:

                await context.enqueue_links(

                    selector='a.pagination__next',

                    label='CATEGORY',

                )



        # This indicates we're on the start page with no specific label.

        # On the start page, we want to enqueue all the category pages.

        else:

            # Wait for the collection cards to render.

            await context.page.wait_for_selector('.collection-block-item')



            # Enqueue links found within elements matching the provided selector.

            # These links will be added to the crawling queue with the label CATEGORY.

            await context.enqueue_links(

                selector='.collection-block-item',

                label='CATEGORY',

            )



    await crawler.run(['https://warehouse-theme-metal.myshopify.com/collections'])





if __name__ == '__main__':

    asyncio.run(main())
```

When you run the crawler, you will see the crawled URLs and their scraped data printed to the console. The output will look something like this:

```
{

    "url": "https://warehouse-theme-metal.myshopify.com/products/sony-str-za810es-7-2-channel-hi-res-wi-fi-network-av-receiver",

    "manufacturer": "sony",

    "title": "Sony STR-ZA810ES 7.2-Ch Hi-Res Wi-Fi Network A/V Receiver",

    "sku": "SON-692802-STR-DE",

    "price": 698,

    "in_stock": true

}
```

## Next steps[​](#next-steps "Direct link to Next steps")

Next, you'll see how to save the data you scraped to the disk for further processing.

[Edit this page](https://github.com/apify/crawlee-python/edit/master/website/versioned_docs/version-1.9/introduction/06_scraping.mdx)

Last updated

<!-- -->

on **Aug 4, 2026** by **Vlada Dusek**

[Previous](https://crawlee.dev/python/python/docs/introduction/crawling.md)

[Crawling](https://crawlee.dev/python/python/docs/introduction/crawling.md)

[Next](https://crawlee.dev/python/python/docs/introduction/saving-data.md)

[Saving data](https://crawlee.dev/python/python/docs/introduction/saving-data.md)

* [](https://crawlee.dev/python/python)
* [Introduction](https://crawlee.dev/python/python/docs/introduction.md)
* Saving data

Version: 1.9

On this page

# Saving data

A data extraction job would not be complete without saving the data for later use and processing. You've come to the final and most difficult part of this tutorial so make sure to pay attention very carefully!

## Save data to the dataset[​](#save-data-to-the-dataset "Direct link to Save data to the dataset")

Crawlee provides a [`Dataset`](https://crawlee.dev/python/python/api/class/Dataset.md) class, which acts as an abstraction over tabular storage, making it useful for storing scraping results. To get started:

* Add the necessary imports: Include the [`Dataset`](https://crawlee.dev/python/python/api/class/Dataset.md) and any required crawler classes at the top of your file.
* Create a Dataset instance: Use the asynchronous [`Dataset.open`](https://crawlee.dev/python/python/api/class/Dataset.md#open) constructor to initialize the dataset instance within your crawler's setup.

Here's an example:

```
import asyncio



from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext

from crawlee.storages import Dataset



# ...





async def main() -> None:

    crawler = PlaywrightCrawler()

    dataset = await Dataset.open()



    # ...



    @crawler.router.default_handler

    async def request_handler(context: PlaywrightCrawlingContext) -> None:

        ...

        # ...





if __name__ == '__main__':

    asyncio.run(main())
```

Finally, instead of logging the extracted data to stdout, we can export them to the dataset:

```
# ...



    @crawler.router.default_handler

    async def request_handler(context: PlaywrightCrawlingContext) -> None:

        # ...



        data = {

            'manufacturer': manufacturer,

            'title': title,

            'sku': sku,

            'price': price,

            'in_stock': in_stock,

        }



        # Push the data to the dataset.

        await dataset.push_data(data)



        # ...
```

### Using a context helper[​](#using-a-context-helper "Direct link to Using a context helper")

Instead of importing a new class and manually creating an instance of the dataset, you can use the context helper [`context.push_data`](https://crawlee.dev/python/python/api/class/PushDataFunction.md). Remove the dataset import and instantiation, and replace `dataset.push_data` with the following:

```
# ...



    @crawler.router.default_handler

    async def request_handler(context: PlaywrightCrawlingContext) -> None:

        # ...



        data = {

            'manufacturer': manufacturer,

            'title': title,

            'sku': sku,

            'price': price,

            'in_stock': in_stock,

        }



        # Push the data to the dataset.

        await context.push_data(data)



        # ...
```

### Final code[​](#final-code "Direct link to Final code")

And that's it. Unlike earlier, we are being serious now. That's it, you're done. The final code looks like this:

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuXFxuZnJvbSBjcmF3bGVlLmNyYXdsZXJzIGltcG9ydCBQbGF5d3JpZ2h0Q3Jhd2xlciwgUGxheXdyaWdodENyYXdsaW5nQ29udGV4dFxcblxcblxcbmFzeW5jIGRlZiBtYWluKCkgLT4gTm9uZTpcXG4gICAgY3Jhd2xlciA9IFBsYXl3cmlnaHRDcmF3bGVyKFxcbiAgICAgICAgIyBMZXQncyBsaW1pdCBvdXIgY3Jhd2xzIHRvIG1ha2Ugb3VyIHRlc3RzIHNob3J0ZXIgYW5kIHNhZmVyLlxcbiAgICAgICAgbWF4X3JlcXVlc3RzX3Blcl9jcmF3bD0xMCxcXG4gICAgKVxcblxcbiAgICBAY3Jhd2xlci5yb3V0ZXIuZGVmYXVsdF9oYW5kbGVyXFxuICAgIGFzeW5jIGRlZiByZXF1ZXN0X2hhbmRsZXIoY29udGV4dDogUGxheXdyaWdodENyYXdsaW5nQ29udGV4dCkgLT4gTm9uZTpcXG4gICAgICAgIGNvbnRleHQubG9nLmluZm8oZidQcm9jZXNzaW5nIHtjb250ZXh0LnJlcXVlc3QudXJsfScpXFxuXFxuICAgICAgICAjIFdlJ3JlIG5vdCBwcm9jZXNzaW5nIGRldGFpbCBwYWdlcyB5ZXQsIHNvIHdlIGp1c3QgcGFzcy5cXG4gICAgICAgIGlmIGNvbnRleHQucmVxdWVzdC5sYWJlbCA9PSAnREVUQUlMJzpcXG4gICAgICAgICAgICAjIFNwbGl0IHRoZSBVUkwgYW5kIGdldCB0aGUgbGFzdCBwYXJ0IHRvIGV4dHJhY3QgdGhlIG1hbnVmYWN0dXJlci5cXG4gICAgICAgICAgICB1cmxfcGFydCA9IGNvbnRleHQucmVxdWVzdC51cmwuc3BsaXQoJy8nKS5wb3AoKVxcbiAgICAgICAgICAgIG1hbnVmYWN0dXJlciA9IHVybF9wYXJ0LnNwbGl0KCctJylbMF1cXG5cXG4gICAgICAgICAgICAjIEV4dHJhY3QgdGhlIHRpdGxlIHVzaW5nIHRoZSBjb21iaW5lZCBzZWxlY3Rvci5cXG4gICAgICAgICAgICB0aXRsZSA9IGF3YWl0IGNvbnRleHQucGFnZS5sb2NhdG9yKCcucHJvZHVjdC1tZXRhIGgxJykudGV4dF9jb250ZW50KClcXG5cXG4gICAgICAgICAgICAjIEV4dHJhY3QgdGhlIFNLVSB1c2luZyBpdHMgc2VsZWN0b3IuXFxuICAgICAgICAgICAgc2t1ID0gYXdhaXQgY29udGV4dC5wYWdlLmxvY2F0b3IoXFxuICAgICAgICAgICAgICAgICdzcGFuLnByb2R1Y3QtbWV0YV9fc2t1LW51bWJlcidcXG4gICAgICAgICAgICApLnRleHRfY29udGVudCgpXFxuXFxuICAgICAgICAgICAgIyBMb2NhdGUgdGhlIHByaWNlIGVsZW1lbnQgdGhhdCBjb250YWlucyB0aGUgJyQnIHNpZ24gYW5kIGZpbHRlciBvdXRcXG4gICAgICAgICAgICAjIHRoZSB2aXN1YWxseSBoaWRkZW4gZWxlbWVudHMuXFxuICAgICAgICAgICAgcHJpY2VfZWxlbWVudCA9IGNvbnRleHQucGFnZS5sb2NhdG9yKCdzcGFuLnByaWNlJywgaGFzX3RleHQ9JyQnKS5maXJzdFxcbiAgICAgICAgICAgIGN1cnJlbnRfcHJpY2Vfc3RyaW5nID0gYXdhaXQgcHJpY2VfZWxlbWVudC50ZXh0X2NvbnRlbnQoKSBvciAnJ1xcbiAgICAgICAgICAgIHJhd19wcmljZSA9IGN1cnJlbnRfcHJpY2Vfc3RyaW5nLnNwbGl0KCckJylbMV1cXG4gICAgICAgICAgICBwcmljZSA9IGZsb2F0KHJhd19wcmljZS5yZXBsYWNlKCcsJywgJycpKVxcblxcbiAgICAgICAgICAgICMgTG9jYXRlIHRoZSBlbGVtZW50IHRoYXQgY29udGFpbnMgdGhlIHRleHQgJ0luIHN0b2NrJyBhbmQgZmlsdGVyIG91dFxcbiAgICAgICAgICAgICMgb3RoZXIgZWxlbWVudHMuXFxuICAgICAgICAgICAgaW5fc3RvY2tfZWxlbWVudCA9IGNvbnRleHQucGFnZS5sb2NhdG9yKFxcbiAgICAgICAgICAgICAgICBzZWxlY3Rvcj0nc3Bhbi5wcm9kdWN0LWZvcm1fX2ludmVudG9yeScsXFxuICAgICAgICAgICAgICAgIGhhc190ZXh0PSdJbiBzdG9jaycsXFxuICAgICAgICAgICAgKS5maXJzdFxcbiAgICAgICAgICAgIGluX3N0b2NrID0gYXdhaXQgaW5fc3RvY2tfZWxlbWVudC5jb3VudCgpID4gMFxcblxcbiAgICAgICAgICAgICMgUHV0IGl0IGFsbCB0b2dldGhlciBpbiBhIGRpY3Rpb25hcnkuXFxuICAgICAgICAgICAgZGF0YSA9IHtcXG4gICAgICAgICAgICAgICAgJ21hbnVmYWN0dXJlcic6IG1hbnVmYWN0dXJlcixcXG4gICAgICAgICAgICAgICAgJ3RpdGxlJzogdGl0bGUsXFxuICAgICAgICAgICAgICAgICdza3UnOiBza3UsXFxuICAgICAgICAgICAgICAgICdwcmljZSc6IHByaWNlLFxcbiAgICAgICAgICAgICAgICAnaW5fc3RvY2snOiBpbl9zdG9jayxcXG4gICAgICAgICAgICB9XFxuXFxuICAgICAgICAgICAgIyBQdXNoIHRoZSBkYXRhIHRvIHRoZSBkYXRhc2V0LlxcbiAgICAgICAgICAgIGF3YWl0IGNvbnRleHQucHVzaF9kYXRhKGRhdGEpXFxuXFxuICAgICAgICAjIFdlIGFyZSBub3cgb24gYSBjYXRlZ29yeSBwYWdlLiBXZSBjYW4gdXNlIHRoaXMgdG8gcGFnaW5hdGUgdGhyb3VnaCBhbmRcXG4gICAgICAgICMgZW5xdWV1ZSBhbGwgcHJvZHVjdHMsIGFzIHdlbGwgYXMgYW55IHN1YnNlcXVlbnQgcGFnZXMgd2UgZmluZC5cXG4gICAgICAgIGVsaWYgY29udGV4dC5yZXF1ZXN0LmxhYmVsID09ICdDQVRFR09SWSc6XFxuICAgICAgICAgICAgIyBXYWl0IGZvciB0aGUgcHJvZHVjdCBpdGVtcyB0byByZW5kZXIuXFxuICAgICAgICAgICAgYXdhaXQgY29udGV4dC5wYWdlLndhaXRfZm9yX3NlbGVjdG9yKCcucHJvZHVjdC1pdGVtID4gYScpXFxuXFxuICAgICAgICAgICAgIyBFbnF1ZXVlIGxpbmtzIGZvdW5kIHdpdGhpbiBlbGVtZW50cyBtYXRjaGluZyB0aGUgcHJvdmlkZWQgc2VsZWN0b3IuXFxuICAgICAgICAgICAgIyBUaGVzZSBsaW5rcyB3aWxsIGJlIGFkZGVkIHRvIHRoZSBjcmF3bGluZyBxdWV1ZSB3aXRoIHRoZSBsYWJlbCBERVRBSUwuXFxuICAgICAgICAgICAgYXdhaXQgY29udGV4dC5lbnF1ZXVlX2xpbmtzKFxcbiAgICAgICAgICAgICAgICBzZWxlY3Rvcj0nLnByb2R1Y3QtaXRlbSA-IGEnLFxcbiAgICAgICAgICAgICAgICBsYWJlbD0nREVUQUlMJyxcXG4gICAgICAgICAgICApXFxuXFxuICAgICAgICAgICAgIyBGaW5kIHRoZSBcXFwiTmV4dFxcXCIgYnV0dG9uIHRvIHBhZ2luYXRlIHRocm91Z2ggdGhlIGNhdGVnb3J5IHBhZ2VzLlxcbiAgICAgICAgICAgIG5leHRfYnV0dG9uID0gYXdhaXQgY29udGV4dC5wYWdlLnF1ZXJ5X3NlbGVjdG9yKCdhLnBhZ2luYXRpb25fX25leHQnKVxcblxcbiAgICAgICAgICAgICMgSWYgYSBcXFwiTmV4dFxcXCIgYnV0dG9uIGlzIGZvdW5kLCBlbnF1ZXVlIHRoZSBuZXh0IHBhZ2Ugb2YgcmVzdWx0cy5cXG4gICAgICAgICAgICBpZiBuZXh0X2J1dHRvbjpcXG4gICAgICAgICAgICAgICAgYXdhaXQgY29udGV4dC5lbnF1ZXVlX2xpbmtzKFxcbiAgICAgICAgICAgICAgICAgICAgc2VsZWN0b3I9J2EucGFnaW5hdGlvbl9fbmV4dCcsXFxuICAgICAgICAgICAgICAgICAgICBsYWJlbD0nQ0FURUdPUlknLFxcbiAgICAgICAgICAgICAgICApXFxuXFxuICAgICAgICAjIFRoaXMgaW5kaWNhdGVzIHdlJ3JlIG9uIHRoZSBzdGFydCBwYWdlIHdpdGggbm8gc3BlY2lmaWMgbGFiZWwuXFxuICAgICAgICAjIE9uIHRoZSBzdGFydCBwYWdlLCB3ZSB3YW50IHRvIGVucXVldWUgYWxsIHRoZSBjYXRlZ29yeSBwYWdlcy5cXG4gICAgICAgIGVsc2U6XFxuICAgICAgICAgICAgIyBXYWl0IGZvciB0aGUgY29sbGVjdGlvbiBjYXJkcyB0byByZW5kZXIuXFxuICAgICAgICAgICAgYXdhaXQgY29udGV4dC5wYWdlLndhaXRfZm9yX3NlbGVjdG9yKCcuY29sbGVjdGlvbi1ibG9jay1pdGVtJylcXG5cXG4gICAgICAgICAgICAjIEVucXVldWUgbGlua3MgZm91bmQgd2l0aGluIGVsZW1lbnRzIG1hdGNoaW5nIHRoZSBwcm92aWRlZCBzZWxlY3Rvci5cXG4gICAgICAgICAgICAjIFRoZXNlIGxpbmtzIHdpbGwgYmUgYWRkZWQgdG8gdGhlIGNyYXdsaW5nIHF1ZXVlIHdpdGggdGhlIGxhYmVsIENBVEVHT1JZLlxcbiAgICAgICAgICAgIGF3YWl0IGNvbnRleHQuZW5xdWV1ZV9saW5rcyhcXG4gICAgICAgICAgICAgICAgc2VsZWN0b3I9Jy5jb2xsZWN0aW9uLWJsb2NrLWl0ZW0nLFxcbiAgICAgICAgICAgICAgICBsYWJlbD0nQ0FURUdPUlknLFxcbiAgICAgICAgICAgIClcXG5cXG4gICAgYXdhaXQgY3Jhd2xlci5ydW4oWydodHRwczovL3dhcmVob3VzZS10aGVtZS1tZXRhbC5teXNob3BpZnkuY29tL2NvbGxlY3Rpb25zJ10pXFxuXFxuXFxuaWYgX19uYW1lX18gPT0gJ19fbWFpbl9fJzpcXG4gICAgYXN5bmNpby5ydW4obWFpbigpKVxcblwifSIsIm9wdGlvbnMiOnsiYnVpbGQiOiJsYXRlc3QiLCJjb250ZW50VHlwZSI6ImFwcGxpY2F0aW9uL2pzb247IGNoYXJzZXQ9dXRmLTgiLCJtZW1vcnkiOjQwOTYsInRpbWVvdXQiOjE4MH19.v7DDzHWFI6tkeduEq8uWmtO1WfUXHLloL-e5spzkZu4\&asrc=run_on_apify)

```
import asyncio



from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext





async def main() -> None:

    crawler = PlaywrightCrawler(

        # Let's limit our crawls to make our tests shorter and safer.

        max_requests_per_crawl=10,

    )



    @crawler.router.default_handler

    async def request_handler(context: PlaywrightCrawlingContext) -> None:

        context.log.info(f'Processing {context.request.url}')



        # We're not processing detail pages yet, so we just pass.

        if context.request.label == 'DETAIL':

            # Split the URL and get the last part to extract the manufacturer.

            url_part = context.request.url.split('/').pop()

            manufacturer = url_part.split('-')[0]



            # Extract the title using the combined selector.

            title = await context.page.locator('.product-meta h1').text_content()



            # Extract the SKU using its selector.

            sku = await context.page.locator(

                'span.product-meta__sku-number'

            ).text_content()



            # Locate the price element that contains the '$' sign and filter out

            # the visually hidden elements.

            price_element = context.page.locator('span.price', has_text='$').first

            current_price_string = await price_element.text_content() or ''

            raw_price = current_price_string.split('$')[1]

            price = float(raw_price.replace(',', ''))



            # Locate the element that contains the text 'In stock' and filter out

            # other elements.

            in_stock_element = context.page.locator(

                selector='span.product-form__inventory',

                has_text='In stock',

            ).first

            in_stock = await in_stock_element.count() > 0



            # Put it all together in a dictionary.

            data = {

                'manufacturer': manufacturer,

                'title': title,

                'sku': sku,

                'price': price,

                'in_stock': in_stock,

            }



            # Push the data to the dataset.

            await context.push_data(data)



        # We are now on a category page. We can use this to paginate through and

        # enqueue all products, as well as any subsequent pages we find.

        elif context.request.label == 'CATEGORY':

            # Wait for the product items to render.

            await context.page.wait_for_selector('.product-item > a')



            # Enqueue links found within elements matching the provided selector.

            # These links will be added to the crawling queue with the label DETAIL.

            await context.enqueue_links(

                selector='.product-item > a',

                label='DETAIL',

            )



            # Find the "Next" button to paginate through the category pages.

            next_button = await context.page.query_selector('a.pagination__next')



            # If a "Next" button is found, enqueue the next page of results.

            if next_button:

                await context.enqueue_links(

                    selector='a.pagination__next',

                    label='CATEGORY',

                )



        # This indicates we're on the start page with no specific label.

        # On the start page, we want to enqueue all the category pages.

        else:

            # Wait for the collection cards to render.

            await context.page.wait_for_selector('.collection-block-item')



            # Enqueue links found within elements matching the provided selector.

            # These links will be added to the crawling queue with the label CATEGORY.

            await context.enqueue_links(

                selector='.collection-block-item',

                label='CATEGORY',

            )



    await crawler.run(['https://warehouse-theme-metal.myshopify.com/collections'])





if __name__ == '__main__':

    asyncio.run(main())
```

## What `push_data` does?[​](#what-push_data-does "Direct link to what-push_data-does")

A helper [`context.push_data`](https://crawlee.dev/python/python/api/class/PushDataFunction.md) saves data to the default dataset. You can provide additional arguments there like `id` or `name` to open a different dataset. Dataset is a storage designed to hold data in a format similar to a table. Each time you call [`context.push_data`](https://crawlee.dev/python/python/api/class/PushDataFunction.md) or direct [`Dataset.push_data`](https://crawlee.dev/python/python/api/class/Dataset.md#push_data) a new row in the table is created, with the property names serving as column titles. In the default configuration, the rows are represented as JSON files saved on your file system, but other backend storage systems can be plugged into Crawlee as well. More on that later.

Automatic dataset initialization

Each time you start Crawlee a default [`Dataset`](https://crawlee.dev/python/python/api/class/Dataset.md) is automatically created, so there's no need to initialize it or create an instance first. You can create as many datasets as you want and even give them names. For more details see the [`Dataset.open`](https://crawlee.dev/python/python/api/class/Dataset.md#open) function.

<!-- -->

## Finding saved data[​](#finding-saved-data "Direct link to Finding saved data")

Unless you changed the configuration that Crawlee uses locally, which would suggest that you knew what you were doing, and you didn't need this tutorial anyway, you'll find your data in the storage directory that Crawlee creates in the working directory of the running script:

```
{PROJECT_FOLDER}/storage/datasets/default/
```

The above folder will hold all your saved data in numbered files, as they were pushed into the dataset. Each file represents one invocation of [`Dataset.push_data`](https://crawlee.dev/python/python/api/class/Dataset.md#push_data) or one table row.

<!-- -->

## Next steps[​](#next-steps "Direct link to Next steps")

Next, you'll see some improvements that you can add to your crawler code that will make it more readable and maintainable in the long run.

[Edit this page](https://github.com/apify/crawlee-python/edit/master/website/versioned_docs/version-1.9/introduction/07_saving_data.mdx)

Last updated

<!-- -->

on **Aug 4, 2026** by **Vlada Dusek**

[Previous](https://crawlee.dev/python/python/docs/introduction/scraping.md)

[Scraping](https://crawlee.dev/python/python/docs/introduction/scraping.md)

[Next](https://crawlee.dev/python/python/docs/introduction/refactoring.md)

[Refactoring](https://crawlee.dev/python/python/docs/introduction/refactoring.md)

* [](https://crawlee.dev/python/python)
* [Introduction](https://crawlee.dev/python/python/docs/introduction.md)
* Refactoring

Version: 1.9

On this page

# Refactoring

It may seem that the data is extracted and the crawler is done, but honestly, this is just the beginning. For the sake of brevity, we've completely omitted error handling, proxies, logging, architecture, tests, documentation and other stuff that a reliable software should have. The good thing is, error handling is mostly done by Crawlee itself, so no worries on that front, unless you need some custom magic.

Navigating automatic bot-protextion avoidance

You might be wondering about the **anti-blocking, bot-protection avoiding stealthy features** and why we haven't highlighted them yet. The reason is straightforward: these features are **automatically used** within the default configuration, providing a smooth start without manual adjustments.

<!-- -->

To promote good coding practices, let's look at how you can use a [`Router`](https://crawlee.dev/python/python/api/class/Router.md) class to better structure your crawler code.

## Request routing[​](#request-routing "Direct link to Request routing")

In the following code, we've made several changes:

* Split the code into multiple files.
* Added custom instance of [`Router`](https://crawlee.dev/python/python/api/class/Router.md) to make our routing cleaner, without if clauses.
* Moved route definitions to a separate `routes.py` file.
* Simplified the `main.py` file to focus on the general structure of the crawler.

### Routes file[​](#routes-file "Direct link to Routes file")

First, let's define our routes in a separate file:

src/routes.py

```
from crawlee.crawlers import PlaywrightCrawlingContext

from crawlee.router import Router



router = Router[PlaywrightCrawlingContext]()





@router.default_handler

async def default_handler(context: PlaywrightCrawlingContext) -> None:

    # This is a fallback route which will handle the start URL.

    context.log.info(f'default_handler is processing {context.request.url}')



    await context.page.wait_for_selector('.collection-block-item')



    await context.enqueue_links(

        selector='.collection-block-item',

        label='CATEGORY',

    )





@router.handler('CATEGORY')

async def category_handler(context: PlaywrightCrawlingContext) -> None:

    # This replaces the context.request.label == CATEGORY branch of the if clause.

    context.log.info(f'category_handler is processing {context.request.url}')



    await context.page.wait_for_selector('.product-item > a')



    await context.enqueue_links(

        selector='.product-item > a',

        label='DETAIL',

    )



    next_button = await context.page.query_selector('a.pagination__next')



    if next_button:

        await context.enqueue_links(

            selector='a.pagination__next',

            label='CATEGORY',

        )





@router.handler('DETAIL')

async def detail_handler(context: PlaywrightCrawlingContext) -> None:

    # This replaces the context.request.label == DETAIL branch of the if clause.

    context.log.info(f'detail_handler is processing {context.request.url}')



    url_part = context.request.url.split('/').pop()

    manufacturer = url_part.split('-')[0]



    title = await context.page.locator('.product-meta h1').text_content()



    sku = await context.page.locator('span.product-meta__sku-number').text_content()



    price_element = context.page.locator('span.price', has_text='$').first

    current_price_string = await price_element.text_content() or ''

    raw_price = current_price_string.split('$')[1]

    price = float(raw_price.replace(',', ''))



    in_stock_element = context.page.locator(

        selector='span.product-form__inventory',

        has_text='In stock',

    ).first

    in_stock = await in_stock_element.count() > 0



    data = {

        'manufacturer': manufacturer,

        'title': title,

        'sku': sku,

        'price': price,

        'in_stock': in_stock,

    }



    await context.push_data(data)
```

### Main file[​](#main-file "Direct link to Main file")

Next, our main file becomes much simpler and cleaner:

src/main.py

```
import asyncio



from crawlee.crawlers import PlaywrightCrawler



from .routes import router





async def main() -> None:

    crawler = PlaywrightCrawler(

        # Let's limit our crawls to make our tests shorter and safer.

        max_requests_per_crawl=10,

        # Provide our router instance to the crawler.

        request_handler=router,

    )



    await crawler.run(['https://warehouse-theme-metal.myshopify.com/collections'])





if __name__ == '__main__':

    asyncio.run(main())
```

By structuring your code this way, you achieve better separation of concerns, making the code easier to read, manage and extend. The [`Router`](https://crawlee.dev/python/python/api/class/Router.md) class keeps your routing logic clean and modular, replacing if clauses with function decorators.

## Summary[​](#summary "Direct link to Summary")

Refactoring your crawler code with these practices enhances readability, maintainability, and scalability.

### Splitting your code into multiple files[​](#splitting-your-code-into-multiple-files "Direct link to Splitting your code into multiple files")

There's no reason not to split your code into multiple files and keep your logic separate. Less code in a single file means less complexity to handle at any time, which improves overall readability and maintainability. Consider further splitting the routes into separate files for even better organization.

### Using a router to structure your crawling[​](#using-a-router-to-structure-your-crawling "Direct link to Using a router to structure your crawling")

Initially, using a simple `if` / `else` statement for selecting different logic based on the crawled pages might appear more readable. However, this approach can become cumbersome with more than two types of pages, especially when the logic for each page extends over dozens or even hundreds of lines of code.

It's good practice in any programming language to split your logic into bite-sized chunks that are easy to read and reason about. Scrolling through a thousand line long `request_handler()` where everything interacts with everything and variables can be used everywhere is not a beautiful thing to do and a pain to debug. That's why we prefer the separation of routes into their own files.

## Next steps[​](#next-steps "Direct link to Next steps")

In the next and final step, you'll see how to deploy your Crawlee project to the cloud. If you used the CLI to bootstrap your project, you already have a `Dockerfile` ready, and the next section will show you how to deploy it to the [Apify platform](https://crawlee.dev/python/python/docs/deployment/apify-platform.md) with ease.

[Edit this page](https://github.com/apify/crawlee-python/edit/master/website/versioned_docs/version-1.9/introduction/08_refactoring.mdx)

Last updated

<!-- -->

on **Aug 4, 2026** by **Vlada Dusek**

[Previous](https://crawlee.dev/python/python/docs/introduction/saving-data.md)

[Saving data](https://crawlee.dev/python/python/docs/introduction/saving-data.md)

[Next](https://crawlee.dev/python/python/docs/introduction/deployment.md)

[Running in the Cloud](https://crawlee.dev/python/python/docs/introduction/deployment.md)

* [](https://crawlee.dev/python/python)
* [Guides](https://crawlee.dev/python/python/docs/guides.md)
* HTTP crawlers

Version: 1.9

On this page

# HTTP crawlers

HTTP crawlers are ideal for extracting data from server-rendered websites that don't require JavaScript execution. These crawlers make requests via HTTP clients to fetch HTML content and then parse it using various parsing libraries. For client-side rendered content, where you need to execute JavaScript consider using [Playwright crawler](https://crawlee.dev/python/python/docs/guides/playwright-crawler.md) instead.

## Overview[​](#overview "Direct link to Overview")

All HTTP crawlers share a common architecture built around the [`AbstractHttpCrawler`](https://crawlee.dev/python/python/api/class/AbstractHttpCrawler.md) base class. The main differences lie in the parsing strategy and the context provided to request handlers. There are [`BeautifulSoupCrawler`](https://crawlee.dev/python/python/api/class/BeautifulSoupCrawler.md), [`ParselCrawler`](https://crawlee.dev/python/python/api/class/ParselCrawler.md), [`HttpCrawler`](https://crawlee.dev/python/python/api/class/HttpCrawler.md), and [`FileDownloadCrawler`](https://crawlee.dev/python/python/api/class/FileDownloadCrawler.md). It can also be extended to create custom crawlers with specialized parsing requirements. They use HTTP clients to fetch page content and parsing libraries to extract data from the HTML, check out the [HTTP clients guide](https://crawlee.dev/python/python/docs/guides/http-clients.md) to learn about the HTTP clients used by these crawlers, how to switch between them, and how to create custom HTTP clients tailored to your specific requirements.

<!-- -->

## BeautifulSoupCrawler[​](#beautifulsoupcrawler "Direct link to BeautifulSoupCrawler")

The [`BeautifulSoupCrawler`](https://crawlee.dev/python/python/api/class/BeautifulSoupCrawler.md) uses the [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) library for HTML parsing. It provides fault-tolerant parsing that handles malformed HTML, automatic character encoding detection, and supports CSS selectors, tag navigation, and custom search functions. Use this crawler when working with imperfect HTML structures, when you prefer BeautifulSoup's intuitive API, or when prototyping web scraping solutions.

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuXFxuZnJvbSBjcmF3bGVlLmNyYXdsZXJzIGltcG9ydCBCZWF1dGlmdWxTb3VwQ3Jhd2xlciwgQmVhdXRpZnVsU291cENyYXdsaW5nQ29udGV4dFxcblxcblxcbmFzeW5jIGRlZiBtYWluKCkgLT4gTm9uZTpcXG4gICAgIyBDcmVhdGUgYSBCZWF1dGlmdWxTb3VwQ3Jhd2xlciBpbnN0YW5jZVxcbiAgICBjcmF3bGVyID0gQmVhdXRpZnVsU291cENyYXdsZXIoXFxuICAgICAgICAjIExpbWl0IHRoZSBjcmF3bCB0byAxMCByZXF1ZXN0c1xcbiAgICAgICAgbWF4X3JlcXVlc3RzX3Blcl9jcmF3bD0xMCxcXG4gICAgKVxcblxcbiAgICAjIERlZmluZSB0aGUgZGVmYXVsdCByZXF1ZXN0IGhhbmRsZXJcXG4gICAgQGNyYXdsZXIucm91dGVyLmRlZmF1bHRfaGFuZGxlclxcbiAgICBhc3luYyBkZWYgcmVxdWVzdF9oYW5kbGVyKGNvbnRleHQ6IEJlYXV0aWZ1bFNvdXBDcmF3bGluZ0NvbnRleHQpIC0-IE5vbmU6XFxuICAgICAgICBjb250ZXh0LmxvZy5pbmZvKGYnUHJvY2Vzc2luZyB7Y29udGV4dC5yZXF1ZXN0LnVybH0nKVxcblxcbiAgICAgICAgIyBFeHRyYWN0IGRhdGEgdXNpbmcgQmVhdXRpZnVsU291cFxcbiAgICAgICAgZGF0YSA9IHtcXG4gICAgICAgICAgICAndXJsJzogY29udGV4dC5yZXF1ZXN0LnVybCxcXG4gICAgICAgICAgICAndGl0bGUnOiBjb250ZXh0LnNvdXAudGl0bGUuc3RyaW5nIGlmIGNvbnRleHQuc291cC50aXRsZSBlbHNlIE5vbmUsXFxuICAgICAgICB9XFxuXFxuICAgICAgICAjIFB1c2ggZXh0cmFjdGVkIGRhdGEgdG8gdGhlIGRhdGFzZXRcXG4gICAgICAgIGF3YWl0IGNvbnRleHQucHVzaF9kYXRhKGRhdGEpXFxuXFxuICAgICAgICAjIEVucXVldWUgbGlua3MgZm91bmQgb24gdGhlIHBhZ2UgZm9yIGZ1cnRoZXIgY3Jhd2xpbmdcXG4gICAgICAgIGF3YWl0IGNvbnRleHQuZW5xdWV1ZV9saW5rcygpXFxuXFxuICAgICMgUnVuIHRoZSBjcmF3bGVyXFxuICAgIGF3YWl0IGNyYXdsZXIucnVuKFsnaHR0cHM6Ly9jcmF3bGVlLmRldiddKVxcblxcblxcbmlmIF9fbmFtZV9fID09ICdfX21haW5fXyc6XFxuICAgIGFzeW5jaW8ucnVuKG1haW4oKSlcXG5cIn0iLCJvcHRpb25zIjp7ImJ1aWxkIjoibGF0ZXN0IiwiY29udGVudFR5cGUiOiJhcHBsaWNhdGlvbi9qc29uOyBjaGFyc2V0PXV0Zi04IiwibWVtb3J5IjoxMDI0LCJ0aW1lb3V0IjoxODB9fQ.qAMYVdW9wPVErdMU9sTZA89XCv6QZmj-vd2_mPjfFU4\&asrc=run_on_apify)

```
import asyncio



from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext





async def main() -> None:

    # Create a BeautifulSoupCrawler instance

    crawler = BeautifulSoupCrawler(

        # Limit the crawl to 10 requests

        max_requests_per_crawl=10,

    )



    # Define the default request handler

    @crawler.router.default_handler

    async def request_handler(context: BeautifulSoupCrawlingContext) -> None:

        context.log.info(f'Processing {context.request.url}')



        # Extract data using BeautifulSoup

        data = {

            'url': context.request.url,

            'title': context.soup.title.string if context.soup.title else None,

        }



        # Push extracted data to the dataset

        await context.push_data(data)



        # Enqueue links found on the page for further crawling

        await context.enqueue_links()



    # Run the crawler

    await crawler.run(['https://crawlee.dev'])





if __name__ == '__main__':

    asyncio.run(main())
```

## ParselCrawler[​](#parselcrawler "Direct link to ParselCrawler")

The [`ParselCrawler`](https://crawlee.dev/python/python/api/class/ParselCrawler.md) uses the [Parsel](https://parsel.readthedocs.io/) library, which provides XPath 1.0 and CSS selector support built on `lxml` for high performance. It includes built-in regex support for pattern matching, proper XML namespace handling, and offers better performance than BeautifulSoup while maintaining a clean API. Use this crawler when you need XPath functionality, require high-performance parsing, or need to extract data using regular expressions.

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuXFxuZnJvbSBjcmF3bGVlLmNyYXdsZXJzIGltcG9ydCBQYXJzZWxDcmF3bGVyLCBQYXJzZWxDcmF3bGluZ0NvbnRleHRcXG5cXG5cXG5hc3luYyBkZWYgbWFpbigpIC0-IE5vbmU6XFxuICAgICMgQ3JlYXRlIGEgUGFyc2VsQ3Jhd2xlciBpbnN0YW5jZVxcbiAgICBjcmF3bGVyID0gUGFyc2VsQ3Jhd2xlcihcXG4gICAgICAgICMgTGltaXQgdGhlIGNyYXdsIHRvIDEwIHJlcXVlc3RzXFxuICAgICAgICBtYXhfcmVxdWVzdHNfcGVyX2NyYXdsPTEwLFxcbiAgICApXFxuXFxuICAgICMgRGVmaW5lIHRoZSBkZWZhdWx0IHJlcXVlc3QgaGFuZGxlclxcbiAgICBAY3Jhd2xlci5yb3V0ZXIuZGVmYXVsdF9oYW5kbGVyXFxuICAgIGFzeW5jIGRlZiByZXF1ZXN0X2hhbmRsZXIoY29udGV4dDogUGFyc2VsQ3Jhd2xpbmdDb250ZXh0KSAtPiBOb25lOlxcbiAgICAgICAgY29udGV4dC5sb2cuaW5mbyhmJ1Byb2Nlc3Npbmcge2NvbnRleHQucmVxdWVzdC51cmx9JylcXG5cXG4gICAgICAgICMgRXh0cmFjdCBkYXRhIHVzaW5nIFBhcnNlbCdzIFhQYXRoIGFuZCBDU1Mgc2VsZWN0b3JzXFxuICAgICAgICBkYXRhID0ge1xcbiAgICAgICAgICAgICd1cmwnOiBjb250ZXh0LnJlcXVlc3QudXJsLFxcbiAgICAgICAgICAgICd0aXRsZSc6IGNvbnRleHQuc2VsZWN0b3IueHBhdGgoJy8vdGl0bGUvdGV4dCgpJykuZ2V0KCksXFxuICAgICAgICB9XFxuXFxuICAgICAgICAjIFB1c2ggZXh0cmFjdGVkIGRhdGEgdG8gdGhlIGRhdGFzZXRcXG4gICAgICAgIGF3YWl0IGNvbnRleHQucHVzaF9kYXRhKGRhdGEpXFxuXFxuICAgICAgICAjIEVucXVldWUgbGlua3MgZm91bmQgb24gdGhlIHBhZ2UgZm9yIGZ1cnRoZXIgY3Jhd2xpbmdcXG4gICAgICAgIGF3YWl0IGNvbnRleHQuZW5xdWV1ZV9saW5rcygpXFxuXFxuICAgICMgUnVuIHRoZSBjcmF3bGVyXFxuICAgIGF3YWl0IGNyYXdsZXIucnVuKFsnaHR0cHM6Ly9jcmF3bGVlLmRldiddKVxcblxcblxcbmlmIF9fbmFtZV9fID09ICdfX21haW5fXyc6XFxuICAgIGFzeW5jaW8ucnVuKG1haW4oKSlcXG5cIn0iLCJvcHRpb25zIjp7ImJ1aWxkIjoibGF0ZXN0IiwiY29udGVudFR5cGUiOiJhcHBsaWNhdGlvbi9qc29uOyBjaGFyc2V0PXV0Zi04IiwibWVtb3J5IjoxMDI0LCJ0aW1lb3V0IjoxODB9fQ.rO-CUHkR6UqBNdmGMcEZ8cBkBEHjNdfYG9VRbF1ZNCc\&asrc=run_on_apify)

```
import asyncio



from crawlee.crawlers import ParselCrawler, ParselCrawlingContext





async def main() -> None:

    # Create a ParselCrawler instance

    crawler = ParselCrawler(

        # Limit the crawl to 10 requests

        max_requests_per_crawl=10,

    )



    # Define the default request handler

    @crawler.router.default_handler

    async def request_handler(context: ParselCrawlingContext) -> None:

        context.log.info(f'Processing {context.request.url}')



        # Extract data using Parsel's XPath and CSS selectors

        data = {

            'url': context.request.url,

            'title': context.selector.xpath('//title/text()').get(),

        }



        # Push extracted data to the dataset

        await context.push_data(data)



        # Enqueue links found on the page for further crawling

        await context.enqueue_links()



    # Run the crawler

    await crawler.run(['https://crawlee.dev'])





if __name__ == '__main__':

    asyncio.run(main())
```

## HttpCrawler[​](#httpcrawler "Direct link to HttpCrawler")

The [`HttpCrawler`](https://crawlee.dev/python/python/api/class/HttpCrawler.md) provides direct access to HTTP response body and headers without automatic parsing, offering maximum performance with no parsing overhead. It supports any content type (JSON, XML, binary) and allows complete control over response processing, including memory-efficient handling of large responses. Use this crawler when working with non-HTML content, requiring maximum performance, implementing custom parsing logic, or needing access to raw response data.

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuaW1wb3J0IHJlXFxuXFxuZnJvbSBjcmF3bGVlLmNyYXdsZXJzIGltcG9ydCBIdHRwQ3Jhd2xlciwgSHR0cENyYXdsaW5nQ29udGV4dFxcblxcblxcbmFzeW5jIGRlZiBtYWluKCkgLT4gTm9uZTpcXG4gICAgIyBDcmVhdGUgYW4gSHR0cENyYXdsZXIgaW5zdGFuY2UgLSBubyBhdXRvbWF0aWMgcGFyc2luZ1xcbiAgICBjcmF3bGVyID0gSHR0cENyYXdsZXIoXFxuICAgICAgICAjIExpbWl0IHRoZSBjcmF3bCB0byAxMCByZXF1ZXN0c1xcbiAgICAgICAgbWF4X3JlcXVlc3RzX3Blcl9jcmF3bD0xMCxcXG4gICAgKVxcblxcbiAgICAjIERlZmluZSB0aGUgZGVmYXVsdCByZXF1ZXN0IGhhbmRsZXJcXG4gICAgQGNyYXdsZXIucm91dGVyLmRlZmF1bHRfaGFuZGxlclxcbiAgICBhc3luYyBkZWYgcmVxdWVzdF9oYW5kbGVyKGNvbnRleHQ6IEh0dHBDcmF3bGluZ0NvbnRleHQpIC0-IE5vbmU6XFxuICAgICAgICBjb250ZXh0LmxvZy5pbmZvKGYnUHJvY2Vzc2luZyB7Y29udGV4dC5yZXF1ZXN0LnVybH0nKVxcblxcbiAgICAgICAgIyBHZXQgdGhlIHJhdyByZXNwb25zZSBjb250ZW50XFxuICAgICAgICByZXNwb25zZV9ib2R5ID0gYXdhaXQgY29udGV4dC5odHRwX3Jlc3BvbnNlLnJlYWQoKVxcbiAgICAgICAgcmVzcG9uc2VfdGV4dCA9IHJlc3BvbnNlX2JvZHkuZGVjb2RlKCd1dGYtOCcpXFxuXFxuICAgICAgICAjIEV4dHJhY3QgdGl0bGUgbWFudWFsbHkgdXNpbmcgcmVnZXggKHNpbmNlIHdlIGRvbid0IGhhdmUgYSBwYXJzZXIpXFxuICAgICAgICB0aXRsZV9tYXRjaCA9IHJlLnNlYXJjaChcXG4gICAgICAgICAgICByJzx0aXRsZVtePl0qPihbXjxdKyk8L3RpdGxlPicsIHJlc3BvbnNlX3RleHQsIHJlLklHTk9SRUNBU0VcXG4gICAgICAgIClcXG4gICAgICAgIHRpdGxlID0gdGl0bGVfbWF0Y2guZ3JvdXAoMSkuc3RyaXAoKSBpZiB0aXRsZV9tYXRjaCBlbHNlIE5vbmVcXG5cXG4gICAgICAgICMgRXh0cmFjdCBiYXNpYyBpbmZvcm1hdGlvblxcbiAgICAgICAgZGF0YSA9IHtcXG4gICAgICAgICAgICAndXJsJzogY29udGV4dC5yZXF1ZXN0LnVybCxcXG4gICAgICAgICAgICAndGl0bGUnOiB0aXRsZSxcXG4gICAgICAgIH1cXG5cXG4gICAgICAgICMgUHVzaCBleHRyYWN0ZWQgZGF0YSB0byB0aGUgZGF0YXNldFxcbiAgICAgICAgYXdhaXQgY29udGV4dC5wdXNoX2RhdGEoZGF0YSlcXG5cXG4gICAgICAgICMgU2ltcGxlIGxpbmsgZXh0cmFjdGlvbiBmb3IgZnVydGhlciBjcmF3bGluZ1xcbiAgICAgICAgaHJlZl9wYXR0ZXJuID0gcidocmVmPVtcXFwiXFxcXCddKFteXFxcIlxcXFwnXSspW1xcXCJcXFxcJ10nXFxuICAgICAgICBtYXRjaGVzID0gcmUuZmluZGFsbChocmVmX3BhdHRlcm4sIHJlc3BvbnNlX3RleHQsIHJlLklHTk9SRUNBU0UpXFxuXFxuICAgICAgICAjIEVucXVldWUgZmlyc3QgZmV3IGxpbmtzIGZvdW5kIChsaW1pdCB0byBhdm9pZCB0b28gbWFueSByZXF1ZXN0cylcXG4gICAgICAgIGZvciBocmVmIGluIG1hdGNoZXNbOjNdOlxcbiAgICAgICAgICAgIGlmIGhyZWYuc3RhcnRzd2l0aCgnaHR0cCcpIGFuZCAnY3Jhd2xlZS5kZXYnIGluIGhyZWY6XFxuICAgICAgICAgICAgICAgIGF3YWl0IGNvbnRleHQuYWRkX3JlcXVlc3RzKFtocmVmXSlcXG5cXG4gICAgIyBSdW4gdGhlIGNyYXdsZXJcXG4gICAgYXdhaXQgY3Jhd2xlci5ydW4oWydodHRwczovL2NyYXdsZWUuZGV2J10pXFxuXFxuXFxuaWYgX19uYW1lX18gPT0gJ19fbWFpbl9fJzpcXG4gICAgYXN5bmNpby5ydW4obWFpbigpKVxcblwifSIsIm9wdGlvbnMiOnsiYnVpbGQiOiJsYXRlc3QiLCJjb250ZW50VHlwZSI6ImFwcGxpY2F0aW9uL2pzb247IGNoYXJzZXQ9dXRmLTgiLCJtZW1vcnkiOjEwMjQsInRpbWVvdXQiOjE4MH19.q1ejL-3xTUHHOTt6_aYK8di7CreyzV0stFUCVZEwfVI\&asrc=run_on_apify)

```
import asyncio

import re



from crawlee.crawlers import HttpCrawler, HttpCrawlingContext





async def main() -> None:

    # Create an HttpCrawler instance - no automatic parsing

    crawler = HttpCrawler(

        # Limit the crawl to 10 requests

        max_requests_per_crawl=10,

    )



    # Define the default request handler

    @crawler.router.default_handler

    async def request_handler(context: HttpCrawlingContext) -> None:

        context.log.info(f'Processing {context.request.url}')



        # Get the raw response content

        response_body = await context.http_response.read()

        response_text = response_body.decode('utf-8')



        # Extract title manually using regex (since we don't have a parser)

        title_match = re.search(

            r'<title[^>]*>([^<]+)</title>', response_text, re.IGNORECASE

        )

        title = title_match.group(1).strip() if title_match else None



        # Extract basic information

        data = {

            'url': context.request.url,

            'title': title,

        }



        # Push extracted data to the dataset

        await context.push_data(data)



        # Simple link extraction for further crawling

        href_pattern = r'href=(?:"|\')([^"\']+)(?:"|\')'

        matches = re.findall(href_pattern, response_text, re.IGNORECASE)



        # Enqueue first few links found (limit to avoid too many requests)

        for href in matches[:3]:

            if href.startswith('http') and 'crawlee.dev' in href:

                await context.add_requests([href])



    # Run the crawler

    await crawler.run(['https://crawlee.dev'])





if __name__ == '__main__':

    asyncio.run(main())
```

### Using custom parsers[​](#using-custom-parsers "Direct link to Using custom parsers")

Since [`HttpCrawler`](https://crawlee.dev/python/python/api/class/HttpCrawler.md) provides raw HTTP responses, you can integrate any parsing library. Note that helpers like [`enqueue_links`](https://crawlee.dev/python/python/api/class/EnqueueLinksFunction.md) and [`extract_links`](https://crawlee.dev/python/python/api/class/ExtractLinksFunction.md) are not available with this approach.

The following examples demonstrate how to integrate with several popular parsing libraries, including [lxml](https://lxml.de/) (high-performance parsing with XPath 1.0), [lxml with SaxonC-HE](https://pypi.org/project/saxonche/) (XPath 3.1 support), [selectolax](https://github.com/rushter/selectolax) (high-speed CSS selectors), [PyQuery](https://pyquery.readthedocs.io/) (jQuery-like syntax), and [scrapling](https://github.com/D4Vinci/Scrapling) (a Scrapy/Parsel-style API offering BeautifulSoup-like methods).

* lxml
* lxml with SaxonC-HE
* selectolax
* PyQuery
* Scrapling

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuXFxuZnJvbSBseG1sIGltcG9ydCBodG1sXFxuZnJvbSBweWRhbnRpYyBpbXBvcnQgVmFsaWRhdGlvbkVycm9yXFxuXFxuZnJvbSBjcmF3bGVlIGltcG9ydCBSZXF1ZXN0XFxuZnJvbSBjcmF3bGVlLmNyYXdsZXJzIGltcG9ydCBIdHRwQ3Jhd2xlciwgSHR0cENyYXdsaW5nQ29udGV4dFxcblxcblxcbmFzeW5jIGRlZiBtYWluKCkgLT4gTm9uZTpcXG4gICAgY3Jhd2xlciA9IEh0dHBDcmF3bGVyKFxcbiAgICAgICAgbWF4X3JlcXVlc3RfcmV0cmllcz0xLFxcbiAgICAgICAgbWF4X3JlcXVlc3RzX3Blcl9jcmF3bD0xMCxcXG4gICAgKVxcblxcbiAgICBAY3Jhd2xlci5yb3V0ZXIuZGVmYXVsdF9oYW5kbGVyXFxuICAgIGFzeW5jIGRlZiByZXF1ZXN0X2hhbmRsZXIoY29udGV4dDogSHR0cENyYXdsaW5nQ29udGV4dCkgLT4gTm9uZTpcXG4gICAgICAgIGNvbnRleHQubG9nLmluZm8oZidQcm9jZXNzaW5nIHtjb250ZXh0LnJlcXVlc3QudXJsfSAuLi4nKVxcblxcbiAgICAgICAgIyBQYXJzZSB0aGUgSFRNTCBjb250ZW50IHVzaW5nIGx4bWwuXFxuICAgICAgICBwYXJzZWRfaHRtbCA9IGh0bWwuZnJvbXN0cmluZyhhd2FpdCBjb250ZXh0Lmh0dHBfcmVzcG9uc2UucmVhZCgpKVxcblxcbiAgICAgICAgIyBFeHRyYWN0IGRhdGEgZnJvbSB0aGUgcGFnZS5cXG4gICAgICAgIGRhdGEgPSB7XFxuICAgICAgICAgICAgJ3VybCc6IGNvbnRleHQucmVxdWVzdC51cmwsXFxuICAgICAgICAgICAgJ3RpdGxlJzogcGFyc2VkX2h0bWwuZmluZHRleHQoJy4vL3RpdGxlJyksXFxuICAgICAgICAgICAgJ2gxcyc6IFtoMS50ZXh0X2NvbnRlbnQoKSBmb3IgaDEgaW4gcGFyc2VkX2h0bWwuZmluZGFsbCgnLi8vaDEnKV0sXFxuICAgICAgICAgICAgJ2gycyc6IFtoMi50ZXh0X2NvbnRlbnQoKSBmb3IgaDIgaW4gcGFyc2VkX2h0bWwuZmluZGFsbCgnLi8vaDInKV0sXFxuICAgICAgICAgICAgJ2gzcyc6IFtoMy50ZXh0X2NvbnRlbnQoKSBmb3IgaDMgaW4gcGFyc2VkX2h0bWwuZmluZGFsbCgnLi8vaDMnKV0sXFxuICAgICAgICB9XFxuICAgICAgICBhd2FpdCBjb250ZXh0LnB1c2hfZGF0YShkYXRhKVxcblxcbiAgICAgICAgIyBDb252ZXJ0IHJlbGF0aXZlIFVSTHMgdG8gYWJzb2x1dGUgYmVmb3JlIGV4dHJhY3RpbmcgbGlua3MuXFxuICAgICAgICBwYXJzZWRfaHRtbC5tYWtlX2xpbmtzX2Fic29sdXRlKGNvbnRleHQucmVxdWVzdC51cmwsIHJlc29sdmVfYmFzZV9ocmVmPVRydWUpXFxuXFxuICAgICAgICAjIFhwYXRoIDEuMCBzZWxlY3RvciBmb3IgZXh0cmFjdGluZyB2YWxpZCBocmVmIGF0dHJpYnV0ZXMuXFxuICAgICAgICBsaW5rc194cGF0aCA9IChcXG4gICAgICAgICAgICAnLy9hL0BocmVmW25vdChzdGFydHMtd2l0aCguLCBcXFwiI1xcXCIpKSAnXFxuICAgICAgICAgICAgJ2FuZCBub3Qoc3RhcnRzLXdpdGgoLiwgXFxcImphdmFzY3JpcHQ6XFxcIikpICdcXG4gICAgICAgICAgICAnYW5kIG5vdChzdGFydHMtd2l0aCguLCBcXFwibWFpbHRvOlxcXCIpKV0nXFxuICAgICAgICApXFxuXFxuICAgICAgICBleHRyYWN0ZWRfcmVxdWVzdHMgPSBbXVxcblxcbiAgICAgICAgIyBFeHRyYWN0IGxpbmtzLlxcbiAgICAgICAgZm9yIHVybCBpbiBwYXJzZWRfaHRtbC54cGF0aChsaW5rc194cGF0aCk6XFxuICAgICAgICAgICAgdHJ5OlxcbiAgICAgICAgICAgICAgICByZXF1ZXN0ID0gUmVxdWVzdC5mcm9tX3VybCh1cmwpXFxuICAgICAgICAgICAgZXhjZXB0IFZhbGlkYXRpb25FcnJvciBhcyBleGM6XFxuICAgICAgICAgICAgICAgIGNvbnRleHQubG9nLndhcm5pbmcoZidTa2lwcGluZyBpbnZhbGlkIFVSTCBcXFwie3VybH1cXFwiOiB7ZXhjfScpXFxuICAgICAgICAgICAgICAgIGNvbnRpbnVlXFxuICAgICAgICAgICAgZXh0cmFjdGVkX3JlcXVlc3RzLmFwcGVuZChyZXF1ZXN0KVxcblxcbiAgICAgICAgIyBBZGQgZXh0cmFjdGVkIHJlcXVlc3RzIHRvIHRoZSBxdWV1ZSB3aXRoIHRoZSBzYW1lLWRvbWFpbiBzdHJhdGVneS5cXG4gICAgICAgIGF3YWl0IGNvbnRleHQuYWRkX3JlcXVlc3RzKGV4dHJhY3RlZF9yZXF1ZXN0cywgc3RyYXRlZ3k9J3NhbWUtZG9tYWluJylcXG5cXG4gICAgYXdhaXQgY3Jhd2xlci5ydW4oWydodHRwczovL2NyYXdsZWUuZGV2J10pXFxuXFxuXFxuaWYgX19uYW1lX18gPT0gJ19fbWFpbl9fJzpcXG4gICAgYXN5bmNpby5ydW4obWFpbigpKVxcblwifSIsIm9wdGlvbnMiOnsiYnVpbGQiOiJsYXRlc3QiLCJjb250ZW50VHlwZSI6ImFwcGxpY2F0aW9uL2pzb247IGNoYXJzZXQ9dXRmLTgiLCJtZW1vcnkiOjEwMjQsInRpbWVvdXQiOjE4MH19.F0mTlHpK3XR5JjB6no2nuCuYuDbrk7SBPrDCWB4hgUc\&asrc=run_on_apify)

```
import asyncio



from lxml import html

from pydantic import ValidationError



from crawlee import Request

from crawlee.crawlers import HttpCrawler, HttpCrawlingContext





async def main() -> None:

    crawler = HttpCrawler(

        max_request_retries=1,

        max_requests_per_crawl=10,

    )



    @crawler.router.default_handler

    async def request_handler(context: HttpCrawlingContext) -> None:

        context.log.info(f'Processing {context.request.url} ...')



        # Parse the HTML content using lxml.

        parsed_html = html.fromstring(await context.http_response.read())



        # Extract data from the page.

        data = {

            'url': context.request.url,

            'title': parsed_html.findtext('.//title'),

            'h1s': [h1.text_content() for h1 in parsed_html.findall('.//h1')],

            'h2s': [h2.text_content() for h2 in parsed_html.findall('.//h2')],

            'h3s': [h3.text_content() for h3 in parsed_html.findall('.//h3')],

        }

        await context.push_data(data)



        # Convert relative URLs to absolute before extracting links.

        parsed_html.make_links_absolute(context.request.url, resolve_base_href=True)



        # Xpath 1.0 selector for extracting valid href attributes.

        links_xpath = (

            '//a/@href[not(starts-with(., "#")) '

            'and not(starts-with(., "javascript:")) '

            'and not(starts-with(., "mailto:"))]'

        )



        extracted_requests = []



        # Extract links.

        for url in parsed_html.xpath(links_xpath):

            try:

                request = Request.from_url(url)

            except ValidationError as exc:

                context.log.warning(f'Skipping invalid URL "{url}": {exc}')

                continue

            extracted_requests.append(request)



        # Add extracted requests to the queue with the same-domain strategy.

        await context.add_requests(extracted_requests, strategy='same-domain')



    await crawler.run(['https://crawlee.dev'])





if __name__ == '__main__':

    asyncio.run(main())
```

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuXFxuZnJvbSBseG1sIGltcG9ydCBodG1sXFxuZnJvbSBweWRhbnRpYyBpbXBvcnQgVmFsaWRhdGlvbkVycm9yXFxuZnJvbSBzYXhvbmNoZSBpbXBvcnQgUHlTYXhvblByb2Nlc3NvclxcblxcbmZyb20gY3Jhd2xlZSBpbXBvcnQgUmVxdWVzdFxcbmZyb20gY3Jhd2xlZS5jcmF3bGVycyBpbXBvcnQgSHR0cENyYXdsZXIsIEh0dHBDcmF3bGluZ0NvbnRleHRcXG5cXG5cXG5hc3luYyBkZWYgbWFpbigpIC0-IE5vbmU6XFxuICAgIGNyYXdsZXIgPSBIdHRwQ3Jhd2xlcihcXG4gICAgICAgIG1heF9yZXF1ZXN0X3JldHJpZXM9MSxcXG4gICAgICAgIG1heF9yZXF1ZXN0c19wZXJfY3Jhd2w9MTAsXFxuICAgIClcXG5cXG4gICAgIyBDcmVhdGUgU2F4b24gcHJvY2Vzc29yIG9uY2UgYW5kIHJldXNlIGFjcm9zcyByZXF1ZXN0cy5cXG4gICAgc2F4b25fcHJvYyA9IFB5U2F4b25Qcm9jZXNzb3IobGljZW5zZT1GYWxzZSlcXG4gICAgeHBhdGhfcHJvYyA9IHNheG9uX3Byb2MubmV3X3hwYXRoX3Byb2Nlc3NvcigpXFxuXFxuICAgIEBjcmF3bGVyLnJvdXRlci5kZWZhdWx0X2hhbmRsZXJcXG4gICAgYXN5bmMgZGVmIHJlcXVlc3RfaGFuZGxlcihjb250ZXh0OiBIdHRwQ3Jhd2xpbmdDb250ZXh0KSAtPiBOb25lOlxcbiAgICAgICAgY29udGV4dC5sb2cuaW5mbyhmJ1Byb2Nlc3Npbmcge2NvbnRleHQucmVxdWVzdC51cmx9IC4uLicpXFxuXFxuICAgICAgICAjIFBhcnNlIEhUTUwgd2l0aCBseG1sLlxcbiAgICAgICAgcGFyc2VkX2h0bWwgPSBodG1sLmZyb21zdHJpbmcoYXdhaXQgY29udGV4dC5odHRwX3Jlc3BvbnNlLnJlYWQoKSlcXG4gICAgICAgICMgQ29udmVydCByZWxhdGl2ZSBVUkxzIHRvIGFic29sdXRlIGJlZm9yZSBleHRyYWN0aW5nIGxpbmtzLlxcbiAgICAgICAgcGFyc2VkX2h0bWwubWFrZV9saW5rc19hYnNvbHV0ZShjb250ZXh0LnJlcXVlc3QudXJsLCByZXNvbHZlX2Jhc2VfaHJlZj1UcnVlKVxcbiAgICAgICAgIyBDb252ZXJ0IHBhcnNlZCBIVE1MIHRvIFhNTCBmb3IgU2F4b24gcHJvY2Vzc2luZy5cXG4gICAgICAgIHhtbCA9IGh0bWwudG9zdHJpbmcocGFyc2VkX2h0bWwsIGVuY29kaW5nPSd1bmljb2RlJywgbWV0aG9kPSd4bWwnKVxcbiAgICAgICAgIyBQYXJzZSBYTUwgd2l0aCBTYXhvbi5cXG4gICAgICAgIHBhcnNlZF94bWwgPSBzYXhvbl9wcm9jLnBhcnNlX3htbCh4bWxfdGV4dD14bWwpXFxuICAgICAgICAjIFNldCB0aGUgcGFyc2VkIGNvbnRleHQgZm9yIFhQYXRoIGV2YWx1YXRpb24uXFxuICAgICAgICB4cGF0aF9wcm9jLnNldF9jb250ZXh0KHhkbV9pdGVtPXBhcnNlZF94bWwpXFxuXFxuICAgICAgICAjIEV4dHJhY3QgZGF0YSB1c2luZyBYUGF0aCAyLjAgc3RyaW5nKCkgZnVuY3Rpb24uXFxuICAgICAgICBkYXRhID0ge1xcbiAgICAgICAgICAgICd1cmwnOiBjb250ZXh0LnJlcXVlc3QudXJsLFxcbiAgICAgICAgICAgICd0aXRsZSc6IHhwYXRoX3Byb2MuZXZhbHVhdGVfc2luZ2xlKCcuLy90aXRsZS9zdHJpbmcoKScpLFxcbiAgICAgICAgICAgICdoMXMnOiBbc3RyKGgpIGZvciBoIGluICh4cGF0aF9wcm9jLmV2YWx1YXRlKCcvL2gxL3N0cmluZygpJykgb3IgW10pXSxcXG4gICAgICAgICAgICAnaDJzJzogW3N0cihoKSBmb3IgaCBpbiAoeHBhdGhfcHJvYy5ldmFsdWF0ZSgnLy9oMi9zdHJpbmcoKScpIG9yIFtdKV0sXFxuICAgICAgICAgICAgJ2gzcyc6IFtzdHIoaCkgZm9yIGggaW4gKHhwYXRoX3Byb2MuZXZhbHVhdGUoJy8vaDMvc3RyaW5nKCknKSBvciBbXSldLFxcbiAgICAgICAgfVxcbiAgICAgICAgYXdhaXQgY29udGV4dC5wdXNoX2RhdGEoZGF0YSlcXG5cXG4gICAgICAgICMgWFBhdGggMi4wIHdpdGggZGlzdGluY3QtdmFsdWVzKCkgdG8gZ2V0IHVuaXF1ZSBsaW5rcyBhbmQgcmVtb3ZlIGZyYWdtZW50cy5cXG4gICAgICAgIGxpbmtzX3hwYXRoID0gXFxcIlxcXCJcXFwiXFxuICAgICAgICAgICAgZGlzdGluY3QtdmFsdWVzKFxcbiAgICAgICAgICAgICAgICBmb3IgJGhyZWYgaW4gLy9hL0BocmVmW1xcbiAgICAgICAgICAgICAgICAgICAgbm90KHN0YXJ0cy13aXRoKC4sIFxcXCIjXFxcIikpXFxuICAgICAgICAgICAgICAgICAgICBhbmQgbm90KHN0YXJ0cy13aXRoKC4sIFxcXCJqYXZhc2NyaXB0OlxcXCIpKVxcbiAgICAgICAgICAgICAgICAgICAgYW5kIG5vdChzdGFydHMtd2l0aCguLCBcXFwibWFpbHRvOlxcXCIpKVxcbiAgICAgICAgICAgICAgICBdXFxuICAgICAgICAgICAgICAgIHJldHVybiByZXBsYWNlKCRocmVmLCBcXFwiIy4qJFxcXCIsIFxcXCJcXFwiKVxcbiAgICAgICAgICAgIClcXG4gICAgICAgIFxcXCJcXFwiXFxcIlxcblxcbiAgICAgICAgZXh0cmFjdGVkX3JlcXVlc3RzID0gW11cXG5cXG4gICAgICAgICMgRXh0cmFjdCBsaW5rcy5cXG4gICAgICAgIGZvciBpdGVtIGluIHhwYXRoX3Byb2MuZXZhbHVhdGUobGlua3NfeHBhdGgpIG9yIFtdOlxcbiAgICAgICAgICAgIHVybCA9IGl0ZW0uc3RyaW5nX3ZhbHVlXFxuICAgICAgICAgICAgdHJ5OlxcbiAgICAgICAgICAgICAgICByZXF1ZXN0ID0gUmVxdWVzdC5mcm9tX3VybCh1cmwpXFxuICAgICAgICAgICAgZXhjZXB0IFZhbGlkYXRpb25FcnJvciBhcyBleGM6XFxuICAgICAgICAgICAgICAgIGNvbnRleHQubG9nLndhcm5pbmcoZidTa2lwcGluZyBpbnZhbGlkIFVSTCBcXFwie3VybH1cXFwiOiB7ZXhjfScpXFxuICAgICAgICAgICAgICAgIGNvbnRpbnVlXFxuICAgICAgICAgICAgZXh0cmFjdGVkX3JlcXVlc3RzLmFwcGVuZChyZXF1ZXN0KVxcblxcbiAgICAgICAgIyBBZGQgZXh0cmFjdGVkIHJlcXVlc3RzIHRvIHRoZSBxdWV1ZSB3aXRoIHRoZSBzYW1lLWRvbWFpbiBzdHJhdGVneS5cXG4gICAgICAgIGF3YWl0IGNvbnRleHQuYWRkX3JlcXVlc3RzKGV4dHJhY3RlZF9yZXF1ZXN0cywgc3RyYXRlZ3k9J3NhbWUtZG9tYWluJylcXG5cXG4gICAgYXdhaXQgY3Jhd2xlci5ydW4oWydodHRwczovL2NyYXdsZWUuZGV2J10pXFxuXFxuXFxuaWYgX19uYW1lX18gPT0gJ19fbWFpbl9fJzpcXG4gICAgYXN5bmNpby5ydW4obWFpbigpKVxcblwifSIsIm9wdGlvbnMiOnsiYnVpbGQiOiJsYXRlc3QiLCJjb250ZW50VHlwZSI6ImFwcGxpY2F0aW9uL2pzb247IGNoYXJzZXQ9dXRmLTgiLCJtZW1vcnkiOjEwMjQsInRpbWVvdXQiOjE4MH19.UwrjVfCuCOBwNSREHrA90Jz91W_8CUc34yB44z8WXFI\&asrc=run_on_apify)

```
import asyncio



from lxml import html

from pydantic import ValidationError

from saxonche import PySaxonProcessor



from crawlee import Request

from crawlee.crawlers import HttpCrawler, HttpCrawlingContext





async def main() -> None:

    crawler = HttpCrawler(

        max_request_retries=1,

        max_requests_per_crawl=10,

    )



    # Create Saxon processor once and reuse across requests.

    saxon_proc = PySaxonProcessor(license=False)

    xpath_proc = saxon_proc.new_xpath_processor()



    @crawler.router.default_handler

    async def request_handler(context: HttpCrawlingContext) -> None:

        context.log.info(f'Processing {context.request.url} ...')



        # Parse HTML with lxml.

        parsed_html = html.fromstring(await context.http_response.read())

        # Convert relative URLs to absolute before extracting links.

        parsed_html.make_links_absolute(context.request.url, resolve_base_href=True)

        # Convert parsed HTML to XML for Saxon processing.

        xml = html.tostring(parsed_html, encoding='unicode', method='xml')

        # Parse XML with Saxon.

        parsed_xml = saxon_proc.parse_xml(xml_text=xml)

        # Set the parsed context for XPath evaluation.

        xpath_proc.set_context(xdm_item=parsed_xml)



        # Extract data using XPath 2.0 string() function.

        data = {

            'url': context.request.url,

            'title': xpath_proc.evaluate_single('.//title/string()'),

            'h1s': [str(h) for h in (xpath_proc.evaluate('//h1/string()') or [])],

            'h2s': [str(h) for h in (xpath_proc.evaluate('//h2/string()') or [])],

            'h3s': [str(h) for h in (xpath_proc.evaluate('//h3/string()') or [])],

        }

        await context.push_data(data)



        # XPath 2.0 with distinct-values() to get unique links and remove fragments.

        links_xpath = """

            distinct-values(

                for $href in //a/@href[

                    not(starts-with(., "#"))

                    and not(starts-with(., "javascript:"))

                    and not(starts-with(., "mailto:"))

                ]

                return replace($href, "#.*$", "")

            )

        """



        extracted_requests = []



        # Extract links.

        for item in xpath_proc.evaluate(links_xpath) or []:

            url = item.string_value

            try:

                request = Request.from_url(url)

            except ValidationError as exc:

                context.log.warning(f'Skipping invalid URL "{url}": {exc}')

                continue

            extracted_requests.append(request)



        # Add extracted requests to the queue with the same-domain strategy.

        await context.add_requests(extracted_requests, strategy='same-domain')



    await crawler.run(['https://crawlee.dev'])





if __name__ == '__main__':

    asyncio.run(main())
```

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuXFxuZnJvbSBweWRhbnRpYyBpbXBvcnQgVmFsaWRhdGlvbkVycm9yXFxuZnJvbSBzZWxlY3RvbGF4LmxleGJvciBpbXBvcnQgTGV4Ym9ySFRNTFBhcnNlclxcbmZyb20geWFybCBpbXBvcnQgVVJMXFxuXFxuZnJvbSBjcmF3bGVlIGltcG9ydCBSZXF1ZXN0XFxuZnJvbSBjcmF3bGVlLmNyYXdsZXJzIGltcG9ydCBIdHRwQ3Jhd2xlciwgSHR0cENyYXdsaW5nQ29udGV4dFxcblxcblxcbmFzeW5jIGRlZiBtYWluKCkgLT4gTm9uZTpcXG4gICAgY3Jhd2xlciA9IEh0dHBDcmF3bGVyKFxcbiAgICAgICAgbWF4X3JlcXVlc3RfcmV0cmllcz0xLFxcbiAgICAgICAgbWF4X3JlcXVlc3RzX3Blcl9jcmF3bD0xMCxcXG4gICAgKVxcblxcbiAgICBAY3Jhd2xlci5yb3V0ZXIuZGVmYXVsdF9oYW5kbGVyXFxuICAgIGFzeW5jIGRlZiByZXF1ZXN0X2hhbmRsZXIoY29udGV4dDogSHR0cENyYXdsaW5nQ29udGV4dCkgLT4gTm9uZTpcXG4gICAgICAgIGNvbnRleHQubG9nLmluZm8oZidQcm9jZXNzaW5nIHtjb250ZXh0LnJlcXVlc3QudXJsfSAuLi4nKVxcblxcbiAgICAgICAgIyBQYXJzZSB0aGUgSFRNTCBjb250ZW50IHVzaW5nIFNlbGVjdG9sYXggd2l0aCBMZXhib3IgYmFja2VuZC5cXG4gICAgICAgIHBhcnNlZF9odG1sID0gTGV4Ym9ySFRNTFBhcnNlcihhd2FpdCBjb250ZXh0Lmh0dHBfcmVzcG9uc2UucmVhZCgpKVxcblxcbiAgICAgICAgIyBFeHRyYWN0IGRhdGEgZnJvbSB0aGUgcGFnZS5cXG4gICAgICAgIGRhdGEgPSB7XFxuICAgICAgICAgICAgJ3VybCc6IGNvbnRleHQucmVxdWVzdC51cmwsXFxuICAgICAgICAgICAgJ3RpdGxlJzogcGFyc2VkX2h0bWwuY3NzX2ZpcnN0KCd0aXRsZScpLnRleHQoKSxcXG4gICAgICAgICAgICAnaDFzJzogW2gxLnRleHQoKSBmb3IgaDEgaW4gcGFyc2VkX2h0bWwuY3NzKCdoMScpXSxcXG4gICAgICAgICAgICAnaDJzJzogW2gyLnRleHQoKSBmb3IgaDIgaW4gcGFyc2VkX2h0bWwuY3NzKCdoMicpXSxcXG4gICAgICAgICAgICAnaDNzJzogW2gzLnRleHQoKSBmb3IgaDMgaW4gcGFyc2VkX2h0bWwuY3NzKCdoMycpXSxcXG4gICAgICAgIH1cXG4gICAgICAgIGF3YWl0IGNvbnRleHQucHVzaF9kYXRhKGRhdGEpXFxuXFxuICAgICAgICAjIENzcyBzZWxlY3RvciB0byBleHRyYWN0IHZhbGlkIGhyZWYgYXR0cmlidXRlcy5cXG4gICAgICAgIGxpbmtzX3NlbGVjdG9yID0gKFxcbiAgICAgICAgICAgICdhW2hyZWZdOm5vdChbaHJlZl49XFxcIiNcXFwiXSk6bm90KFtocmVmXj1cXFwiamF2YXNjcmlwdDpcXFwiXSk6bm90KFtocmVmXj1cXFwibWFpbHRvOlxcXCJdKSdcXG4gICAgICAgIClcXG4gICAgICAgIGJhc2VfdXJsID0gVVJMKGNvbnRleHQucmVxdWVzdC51cmwpXFxuICAgICAgICBleHRyYWN0ZWRfcmVxdWVzdHMgPSBbXVxcblxcbiAgICAgICAgIyBFeHRyYWN0IGxpbmtzLlxcbiAgICAgICAgZm9yIGl0ZW0gaW4gcGFyc2VkX2h0bWwuY3NzKGxpbmtzX3NlbGVjdG9yKTpcXG4gICAgICAgICAgICBocmVmID0gaXRlbS5hdHRyaWJ1dGVzLmdldCgnaHJlZicpXFxuICAgICAgICAgICAgaWYgbm90IGhyZWY6XFxuICAgICAgICAgICAgICAgIGNvbnRpbnVlXFxuXFxuICAgICAgICAgICAgIyBDb252ZXJ0IHJlbGF0aXZlIFVSTHMgdG8gYWJzb2x1dGUgaWYgbmVlZGVkLlxcbiAgICAgICAgICAgIHVybCA9IHN0cihiYXNlX3VybC5qb2luKFVSTChocmVmKSkpXFxuICAgICAgICAgICAgdHJ5OlxcbiAgICAgICAgICAgICAgICByZXF1ZXN0ID0gUmVxdWVzdC5mcm9tX3VybCh1cmwpXFxuICAgICAgICAgICAgZXhjZXB0IFZhbGlkYXRpb25FcnJvciBhcyBleGM6XFxuICAgICAgICAgICAgICAgIGNvbnRleHQubG9nLndhcm5pbmcoZidTa2lwcGluZyBpbnZhbGlkIFVSTCBcXFwie3VybH1cXFwiOiB7ZXhjfScpXFxuICAgICAgICAgICAgICAgIGNvbnRpbnVlXFxuICAgICAgICAgICAgZXh0cmFjdGVkX3JlcXVlc3RzLmFwcGVuZChyZXF1ZXN0KVxcblxcbiAgICAgICAgIyBBZGQgZXh0cmFjdGVkIHJlcXVlc3RzIHRvIHRoZSBxdWV1ZSB3aXRoIHRoZSBzYW1lLWRvbWFpbiBzdHJhdGVneS5cXG4gICAgICAgIGF3YWl0IGNvbnRleHQuYWRkX3JlcXVlc3RzKGV4dHJhY3RlZF9yZXF1ZXN0cywgc3RyYXRlZ3k9J3NhbWUtZG9tYWluJylcXG5cXG4gICAgYXdhaXQgY3Jhd2xlci5ydW4oWydodHRwczovL2NyYXdsZWUuZGV2J10pXFxuXFxuXFxuaWYgX19uYW1lX18gPT0gJ19fbWFpbl9fJzpcXG4gICAgYXN5bmNpby5ydW4obWFpbigpKVxcblwifSIsIm9wdGlvbnMiOnsiYnVpbGQiOiJsYXRlc3QiLCJjb250ZW50VHlwZSI6ImFwcGxpY2F0aW9uL2pzb247IGNoYXJzZXQ9dXRmLTgiLCJtZW1vcnkiOjEwMjQsInRpbWVvdXQiOjE4MH19.vccoyBSbYPEP9O3wqtA96J5pqt2VqbQs1POBjVXT7rY\&asrc=run_on_apify)

```
import asyncio



from pydantic import ValidationError

from selectolax.lexbor import LexborHTMLParser

from yarl import URL



from crawlee import Request

from crawlee.crawlers import HttpCrawler, HttpCrawlingContext





async def main() -> None:

    crawler = HttpCrawler(

        max_request_retries=1,

        max_requests_per_crawl=10,

    )



    @crawler.router.default_handler

    async def request_handler(context: HttpCrawlingContext) -> None:

        context.log.info(f'Processing {context.request.url} ...')



        # Parse the HTML content using Selectolax with Lexbor backend.

        parsed_html = LexborHTMLParser(await context.http_response.read())



        # Extract data from the page.

        data = {

            'url': context.request.url,

            'title': parsed_html.css_first('title').text(),

            'h1s': [h1.text() for h1 in parsed_html.css('h1')],

            'h2s': [h2.text() for h2 in parsed_html.css('h2')],

            'h3s': [h3.text() for h3 in parsed_html.css('h3')],

        }

        await context.push_data(data)



        # Css selector to extract valid href attributes.

        links_selector = (

            'a[href]:not([href^="#"]):not([href^="javascript:"]):not([href^="mailto:"])'

        )

        base_url = URL(context.request.url)

        extracted_requests = []



        # Extract links.

        for item in parsed_html.css(links_selector):

            href = item.attributes.get('href')

            if not href:

                continue



            # Convert relative URLs to absolute if needed.

            url = str(base_url.join(URL(href)))

            try:

                request = Request.from_url(url)

            except ValidationError as exc:

                context.log.warning(f'Skipping invalid URL "{url}": {exc}')

                continue

            extracted_requests.append(request)



        # Add extracted requests to the queue with the same-domain strategy.

        await context.add_requests(extracted_requests, strategy='same-domain')



    await crawler.run(['https://crawlee.dev'])





if __name__ == '__main__':

    asyncio.run(main())
```

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuXFxuZnJvbSBweWRhbnRpYyBpbXBvcnQgVmFsaWRhdGlvbkVycm9yXFxuZnJvbSBweXF1ZXJ5IGltcG9ydCBQeVF1ZXJ5XFxuZnJvbSB5YXJsIGltcG9ydCBVUkxcXG5cXG5mcm9tIGNyYXdsZWUgaW1wb3J0IFJlcXVlc3RcXG5mcm9tIGNyYXdsZWUuY3Jhd2xlcnMgaW1wb3J0IEh0dHBDcmF3bGVyLCBIdHRwQ3Jhd2xpbmdDb250ZXh0XFxuXFxuXFxuYXN5bmMgZGVmIG1haW4oKSAtPiBOb25lOlxcbiAgICBjcmF3bGVyID0gSHR0cENyYXdsZXIoXFxuICAgICAgICBtYXhfcmVxdWVzdF9yZXRyaWVzPTEsXFxuICAgICAgICBtYXhfcmVxdWVzdHNfcGVyX2NyYXdsPTEwLFxcbiAgICApXFxuXFxuICAgIEBjcmF3bGVyLnJvdXRlci5kZWZhdWx0X2hhbmRsZXJcXG4gICAgYXN5bmMgZGVmIHJlcXVlc3RfaGFuZGxlcihjb250ZXh0OiBIdHRwQ3Jhd2xpbmdDb250ZXh0KSAtPiBOb25lOlxcbiAgICAgICAgY29udGV4dC5sb2cuaW5mbyhmJ1Byb2Nlc3Npbmcge2NvbnRleHQucmVxdWVzdC51cmx9IC4uLicpXFxuXFxuICAgICAgICAjIFBhcnNlIHRoZSBIVE1MIGNvbnRlbnQgdXNpbmcgUHlRdWVyeS5cXG4gICAgICAgIHBhcnNlZF9odG1sID0gUHlRdWVyeShhd2FpdCBjb250ZXh0Lmh0dHBfcmVzcG9uc2UucmVhZCgpKVxcblxcbiAgICAgICAgIyBFeHRyYWN0IGRhdGEgdXNpbmcgalF1ZXJ5LXN0eWxlIHNlbGVjdG9ycy5cXG4gICAgICAgIGRhdGEgPSB7XFxuICAgICAgICAgICAgJ3VybCc6IGNvbnRleHQucmVxdWVzdC51cmwsXFxuICAgICAgICAgICAgJ3RpdGxlJzogcGFyc2VkX2h0bWwoJ3RpdGxlJykudGV4dCgpLFxcbiAgICAgICAgICAgICdoMXMnOiBbaDEudGV4dCgpIGZvciBoMSBpbiBwYXJzZWRfaHRtbCgnaDEnKS5pdGVtcygpXSxcXG4gICAgICAgICAgICAnaDJzJzogW2gyLnRleHQoKSBmb3IgaDIgaW4gcGFyc2VkX2h0bWwoJ2gyJykuaXRlbXMoKV0sXFxuICAgICAgICAgICAgJ2gzcyc6IFtoMy50ZXh0KCkgZm9yIGgzIGluIHBhcnNlZF9odG1sKCdoMycpLml0ZW1zKCldLFxcbiAgICAgICAgfVxcbiAgICAgICAgYXdhaXQgY29udGV4dC5wdXNoX2RhdGEoZGF0YSlcXG5cXG4gICAgICAgICMgQ3NzIHNlbGVjdG9yIHRvIGV4dHJhY3QgdmFsaWQgaHJlZiBhdHRyaWJ1dGVzLlxcbiAgICAgICAgbGlua3Nfc2VsZWN0b3IgPSAoXFxuICAgICAgICAgICAgJ2FbaHJlZl06bm90KFtocmVmXj1cXFwiI1xcXCJdKTpub3QoW2hyZWZePVxcXCJqYXZhc2NyaXB0OlxcXCJdKTpub3QoW2hyZWZePVxcXCJtYWlsdG86XFxcIl0pJ1xcbiAgICAgICAgKVxcbiAgICAgICAgYmFzZV91cmwgPSBVUkwoY29udGV4dC5yZXF1ZXN0LnVybClcXG5cXG4gICAgICAgIGV4dHJhY3RlZF9yZXF1ZXN0cyA9IFtdXFxuXFxuICAgICAgICAjIEV4dHJhY3QgbGlua3MuXFxuICAgICAgICBmb3IgaXRlbSBpbiBwYXJzZWRfaHRtbChsaW5rc19zZWxlY3RvcikuaXRlbXMoKTpcXG4gICAgICAgICAgICBocmVmID0gaXRlbS5hdHRyKCdocmVmJylcXG4gICAgICAgICAgICBpZiBub3QgaHJlZjpcXG4gICAgICAgICAgICAgICAgY29udGludWVcXG5cXG4gICAgICAgICAgICAjIENvbnZlcnQgcmVsYXRpdmUgVVJMcyB0byBhYnNvbHV0ZSBpZiBuZWVkZWQuXFxuICAgICAgICAgICAgdXJsID0gc3RyKGJhc2VfdXJsLmpvaW4oVVJMKHN0cihocmVmKSkpKVxcbiAgICAgICAgICAgIHRyeTpcXG4gICAgICAgICAgICAgICAgcmVxdWVzdCA9IFJlcXVlc3QuZnJvbV91cmwodXJsKVxcbiAgICAgICAgICAgIGV4Y2VwdCBWYWxpZGF0aW9uRXJyb3IgYXMgZXhjOlxcbiAgICAgICAgICAgICAgICBjb250ZXh0LmxvZy53YXJuaW5nKGYnU2tpcHBpbmcgaW52YWxpZCBVUkwgXFxcInt1cmx9XFxcIjoge2V4Y30nKVxcbiAgICAgICAgICAgICAgICBjb250aW51ZVxcbiAgICAgICAgICAgIGV4dHJhY3RlZF9yZXF1ZXN0cy5hcHBlbmQocmVxdWVzdClcXG5cXG4gICAgICAgICMgQWRkIGV4dHJhY3RlZCByZXF1ZXN0cyB0byB0aGUgcXVldWUgd2l0aCB0aGUgc2FtZS1kb21haW4gc3RyYXRlZ3kuXFxuICAgICAgICBhd2FpdCBjb250ZXh0LmFkZF9yZXF1ZXN0cyhleHRyYWN0ZWRfcmVxdWVzdHMsIHN0cmF0ZWd5PSdzYW1lLWRvbWFpbicpXFxuXFxuICAgIGF3YWl0IGNyYXdsZXIucnVuKFsnaHR0cHM6Ly9jcmF3bGVlLmRldiddKVxcblxcblxcbmlmIF9fbmFtZV9fID09ICdfX21haW5fXyc6XFxuICAgIGFzeW5jaW8ucnVuKG1haW4oKSlcXG5cIn0iLCJvcHRpb25zIjp7ImJ1aWxkIjoibGF0ZXN0IiwiY29udGVudFR5cGUiOiJhcHBsaWNhdGlvbi9qc29uOyBjaGFyc2V0PXV0Zi04IiwibWVtb3J5IjoxMDI0LCJ0aW1lb3V0IjoxODB9fQ.qJE5FSido7yGTg5je1T2xBWM-_AGPnDjqDRa9KEI_N4\&asrc=run_on_apify)

```
import asyncio



from pydantic import ValidationError

from pyquery import PyQuery

from yarl import URL



from crawlee import Request

from crawlee.crawlers import HttpCrawler, HttpCrawlingContext





async def main() -> None:

    crawler = HttpCrawler(

        max_request_retries=1,

        max_requests_per_crawl=10,

    )



    @crawler.router.default_handler

    async def request_handler(context: HttpCrawlingContext) -> None:

        context.log.info(f'Processing {context.request.url} ...')



        # Parse the HTML content using PyQuery.

        parsed_html = PyQuery(await context.http_response.read())



        # Extract data using jQuery-style selectors.

        data = {

            'url': context.request.url,

            'title': parsed_html('title').text(),

            'h1s': [h1.text() for h1 in parsed_html('h1').items()],

            'h2s': [h2.text() for h2 in parsed_html('h2').items()],

            'h3s': [h3.text() for h3 in parsed_html('h3').items()],

        }

        await context.push_data(data)



        # Css selector to extract valid href attributes.

        links_selector = (

            'a[href]:not([href^="#"]):not([href^="javascript:"]):not([href^="mailto:"])'

        )

        base_url = URL(context.request.url)



        extracted_requests = []



        # Extract links.

        for item in parsed_html(links_selector).items():

            href = item.attr('href')

            if not href:

                continue



            # Convert relative URLs to absolute if needed.

            url = str(base_url.join(URL(str(href))))

            try:

                request = Request.from_url(url)

            except ValidationError as exc:

                context.log.warning(f'Skipping invalid URL "{url}": {exc}')

                continue

            extracted_requests.append(request)



        # Add extracted requests to the queue with the same-domain strategy.

        await context.add_requests(extracted_requests, strategy='same-domain')



    await crawler.run(['https://crawlee.dev'])





if __name__ == '__main__':

    asyncio.run(main())
```

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuXFxuZnJvbSBweWRhbnRpYyBpbXBvcnQgVmFsaWRhdGlvbkVycm9yXFxuZnJvbSBzY3JhcGxpbmcucGFyc2VyIGltcG9ydCBTZWxlY3RvclxcbmZyb20geWFybCBpbXBvcnQgVVJMXFxuXFxuZnJvbSBjcmF3bGVlIGltcG9ydCBSZXF1ZXN0XFxuZnJvbSBjcmF3bGVlLmNyYXdsZXJzIGltcG9ydCBIdHRwQ3Jhd2xlciwgSHR0cENyYXdsaW5nQ29udGV4dFxcblxcblxcbmFzeW5jIGRlZiBtYWluKCkgLT4gTm9uZTpcXG4gICAgY3Jhd2xlciA9IEh0dHBDcmF3bGVyKFxcbiAgICAgICAgbWF4X3JlcXVlc3RfcmV0cmllcz0xLFxcbiAgICAgICAgbWF4X3JlcXVlc3RzX3Blcl9jcmF3bD0xMCxcXG4gICAgKVxcblxcbiAgICBAY3Jhd2xlci5yb3V0ZXIuZGVmYXVsdF9oYW5kbGVyXFxuICAgIGFzeW5jIGRlZiByZXF1ZXN0X2hhbmRsZXIoY29udGV4dDogSHR0cENyYXdsaW5nQ29udGV4dCkgLT4gTm9uZTpcXG4gICAgICAgIGNvbnRleHQubG9nLmluZm8oZidQcm9jZXNzaW5nIHtjb250ZXh0LnJlcXVlc3QudXJsfSAuLi4nKVxcblxcbiAgICAgICAgIyBQYXJzZSB0aGUgSFRNTCBjb250ZW50IHVzaW5nIFNjcmFwbGluZy5cXG4gICAgICAgIHBhZ2UgPSBTZWxlY3Rvcihhd2FpdCBjb250ZXh0Lmh0dHBfcmVzcG9uc2UucmVhZCgpLCB1cmw9Y29udGV4dC5yZXF1ZXN0LnVybClcXG5cXG4gICAgICAgICMgRXh0cmFjdCBkYXRhIHVzaW5nIFhwYXRoIHNlbGVjdG9ycyB3aXRoIC5nZXRfYWxsX3RleHQgbWV0aG9kIGZvciBmdWxsIHRleHRcXG4gICAgICAgICMgY29udGVudC5cXG4gICAgICAgIHRpdGxlX2VsID0gcGFnZS54cGF0aF9maXJzdCgnLy90aXRsZScpXFxuICAgICAgICBkYXRhID0ge1xcbiAgICAgICAgICAgICd1cmwnOiBjb250ZXh0LnJlcXVlc3QudXJsLFxcbiAgICAgICAgICAgICd0aXRsZSc6IHRpdGxlX2VsLnRleHQgaWYgaXNpbnN0YW5jZSh0aXRsZV9lbCwgU2VsZWN0b3IpIGVsc2UgdGl0bGVfZWwsXFxuICAgICAgICAgICAgJ2gxcyc6IFtcXG4gICAgICAgICAgICAgICAgaDEuZ2V0X2FsbF90ZXh0KCkgaWYgaXNpbnN0YW5jZShoMSwgU2VsZWN0b3IpIGVsc2UgaDFcXG4gICAgICAgICAgICAgICAgZm9yIGgxIGluIHBhZ2UueHBhdGgoJy8vaDEnKVxcbiAgICAgICAgICAgIF0sXFxuICAgICAgICAgICAgJ2gycyc6IFtcXG4gICAgICAgICAgICAgICAgaDIuZ2V0X2FsbF90ZXh0KCkgaWYgaXNpbnN0YW5jZShoMiwgU2VsZWN0b3IpIGVsc2UgaDJcXG4gICAgICAgICAgICAgICAgZm9yIGgyIGluIHBhZ2UueHBhdGgoJy8vaDInKVxcbiAgICAgICAgICAgIF0sXFxuICAgICAgICAgICAgJ2gzcyc6IFtcXG4gICAgICAgICAgICAgICAgaDMuZ2V0X2FsbF90ZXh0KCkgaWYgaXNpbnN0YW5jZShoMywgU2VsZWN0b3IpIGVsc2UgaDNcXG4gICAgICAgICAgICAgICAgZm9yIGgzIGluIHBhZ2UueHBhdGgoJy8vaDMnKVxcbiAgICAgICAgICAgIF0sXFxuICAgICAgICB9XFxuICAgICAgICBhd2FpdCBjb250ZXh0LnB1c2hfZGF0YShkYXRhKVxcblxcbiAgICAgICAgIyBDc3Mgc2VsZWN0b3IgdG8gZXh0cmFjdCB2YWxpZCBocmVmIGF0dHJpYnV0ZXMuXFxuICAgICAgICBsaW5rc19zZWxlY3RvciA9IChcXG4gICAgICAgICAgICAnYVtocmVmXTpub3QoW2hyZWZePVxcXCIjXFxcIl0pOm5vdChbaHJlZl49XFxcImphdmFzY3JpcHQ6XFxcIl0pOm5vdChbaHJlZl49XFxcIm1haWx0bzpcXFwiXSknXFxuICAgICAgICApXFxuICAgICAgICBiYXNlX3VybCA9IFVSTChjb250ZXh0LnJlcXVlc3QudXJsKVxcbiAgICAgICAgZXh0cmFjdGVkX3JlcXVlc3RzID0gW11cXG5cXG4gICAgICAgICMgRXh0cmFjdCBsaW5rcy5cXG4gICAgICAgIGZvciBpdGVtIGluIHBhZ2UuY3NzKGxpbmtzX3NlbGVjdG9yKTpcXG4gICAgICAgICAgICBocmVmID0gaXRlbS5hdHRyaWIuZ2V0KCdocmVmJykgaWYgaXNpbnN0YW5jZShpdGVtLCBTZWxlY3RvcikgZWxzZSBOb25lXFxuICAgICAgICAgICAgaWYgbm90IGhyZWY6XFxuICAgICAgICAgICAgICAgIGNvbnRpbnVlXFxuXFxuICAgICAgICAgICAgIyBDb252ZXJ0IHJlbGF0aXZlIFVSTHMgdG8gYWJzb2x1dGUgaWYgbmVlZGVkLlxcbiAgICAgICAgICAgIHVybCA9IHN0cihiYXNlX3VybC5qb2luKFVSTChocmVmKSkpXFxuICAgICAgICAgICAgdHJ5OlxcbiAgICAgICAgICAgICAgICByZXF1ZXN0ID0gUmVxdWVzdC5mcm9tX3VybCh1cmwpXFxuICAgICAgICAgICAgZXhjZXB0IFZhbGlkYXRpb25FcnJvciBhcyBleGM6XFxuICAgICAgICAgICAgICAgIGNvbnRleHQubG9nLndhcm5pbmcoZidTa2lwcGluZyBpbnZhbGlkIFVSTCBcXFwie3VybH1cXFwiOiB7ZXhjfScpXFxuICAgICAgICAgICAgICAgIGNvbnRpbnVlXFxuICAgICAgICAgICAgZXh0cmFjdGVkX3JlcXVlc3RzLmFwcGVuZChyZXF1ZXN0KVxcblxcbiAgICAgICAgIyBBZGQgZXh0cmFjdGVkIHJlcXVlc3RzIHRvIHRoZSBxdWV1ZSB3aXRoIHRoZSBzYW1lLWRvbWFpbiBzdHJhdGVneS5cXG4gICAgICAgIGF3YWl0IGNvbnRleHQuYWRkX3JlcXVlc3RzKGV4dHJhY3RlZF9yZXF1ZXN0cywgc3RyYXRlZ3k9J3NhbWUtZG9tYWluJylcXG5cXG4gICAgYXdhaXQgY3Jhd2xlci5ydW4oWydodHRwczovL2NyYXdsZWUuZGV2J10pXFxuXFxuXFxuaWYgX19uYW1lX18gPT0gJ19fbWFpbl9fJzpcXG4gICAgYXN5bmNpby5ydW4obWFpbigpKVxcblwifSIsIm9wdGlvbnMiOnsiYnVpbGQiOiJsYXRlc3QiLCJjb250ZW50VHlwZSI6ImFwcGxpY2F0aW9uL2pzb247IGNoYXJzZXQ9dXRmLTgiLCJtZW1vcnkiOjEwMjQsInRpbWVvdXQiOjE4MH19.cDVjDeVxU7XhHNqvYVvh5vb3dBrsoJnyU6Aas0Ur7bY\&asrc=run_on_apify)

```
import asyncio



from pydantic import ValidationError

from scrapling.parser import Selector

from yarl import URL



from crawlee import Request

from crawlee.crawlers import HttpCrawler, HttpCrawlingContext





async def main() -> None:

    crawler = HttpCrawler(

        max_request_retries=1,

        max_requests_per_crawl=10,

    )



    @crawler.router.default_handler

    async def request_handler(context: HttpCrawlingContext) -> None:

        context.log.info(f'Processing {context.request.url} ...')



        # Parse the HTML content using Scrapling.

        page = Selector(await context.http_response.read(), url=context.request.url)



        # Extract data using Xpath selectors with .get_all_text method for full text

        # content.

        title_el = page.xpath_first('//title')

        data = {

            'url': context.request.url,

            'title': title_el.text if isinstance(title_el, Selector) else title_el,

            'h1s': [

                h1.get_all_text() if isinstance(h1, Selector) else h1

                for h1 in page.xpath('//h1')

            ],

            'h2s': [

                h2.get_all_text() if isinstance(h2, Selector) else h2

                for h2 in page.xpath('//h2')

            ],

            'h3s': [

                h3.get_all_text() if isinstance(h3, Selector) else h3

                for h3 in page.xpath('//h3')

            ],

        }

        await context.push_data(data)



        # Css selector to extract valid href attributes.

        links_selector = (

            'a[href]:not([href^="#"]):not([href^="javascript:"]):not([href^="mailto:"])'

        )

        base_url = URL(context.request.url)

        extracted_requests = []



        # Extract links.

        for item in page.css(links_selector):

            href = item.attrib.get('href') if isinstance(item, Selector) else None

            if not href:

                continue



            # Convert relative URLs to absolute if needed.

            url = str(base_url.join(URL(href)))

            try:

                request = Request.from_url(url)

            except ValidationError as exc:

                context.log.warning(f'Skipping invalid URL "{url}": {exc}')

                continue

            extracted_requests.append(request)



        # Add extracted requests to the queue with the same-domain strategy.

        await context.add_requests(extracted_requests, strategy='same-domain')



    await crawler.run(['https://crawlee.dev'])





if __name__ == '__main__':

    asyncio.run(main())
```

## FileDownloadCrawler[​](#filedownloadcrawler "Direct link to FileDownloadCrawler")

The [`FileDownloadCrawler`](https://crawlee.dev/python/python/api/class/FileDownloadCrawler.md) downloads files instead of scraping pages. It accepts any content type without parsing and gives the request handler direct access to the response body. By default the whole file is buffered in memory. For large files, construct the crawler with `stream=True` and consume the body in chunks via [`read_stream()`](https://crawlee.dev/python/python/api/class/HttpResponse.md#read_stream). For usage, see the [Download files](https://crawlee.dev/python/python/docs/examples/file-download.md) example.

## Custom HTTP crawler[​](#custom-http-crawler "Direct link to Custom HTTP crawler")

While the built-in crawlers cover most use cases, you might need a custom HTTP crawler for specialized parsing requirements. To create a custom HTTP crawler, inherit directly from [`AbstractHttpCrawler`](https://crawlee.dev/python/python/api/class/AbstractHttpCrawler.md). This approach requires implementing:

1. **Custom parser class**: Inherit from [`AbstractHttpParser`](https://crawlee.dev/python/python/api/class/AbstractHttpParser.md).
2. **Custom context class**: Define what data and helpers are available to handlers.
3. **Custom crawler class**: Tie everything together.

This approach is recommended when you need tight integration between parsing and the crawling context, or when you're building a reusable crawler for a specific technology or format.

The following example demonstrates how to create a custom crawler using `selectolax` with the `Lexbor` engine.

### Parser implementation[​](#parser-implementation "Direct link to Parser implementation")

The parser converts HTTP responses into a parsed document and provides methods for element selection. Implement [`AbstractHttpParser`](https://crawlee.dev/python/python/api/class/AbstractHttpParser.md) using `selectolax` with required methods for parsing and querying:

selectolax\_parser.py

```
from __future__ import annotations



import asyncio

from typing import TYPE_CHECKING



from selectolax.lexbor import LexborHTMLParser, LexborNode

from typing_extensions import override



from crawlee.crawlers._abstract_http import AbstractHttpParser



if TYPE_CHECKING:

    from collections.abc import Iterable, Sequence



    from crawlee.http_clients import HttpResponse





class SelectolaxLexborParser(AbstractHttpParser[LexborHTMLParser, LexborNode]):

    """Parser for parsing HTTP response using Selectolax Lexbor."""



    @override

    async def parse(self, response: HttpResponse) -> LexborHTMLParser:

        """Parse HTTP response body into a document object."""

        response_body = await response.read()

        # Run parsing in a thread to avoid blocking the event loop.

        return await asyncio.to_thread(LexborHTMLParser, response_body)



    @override

    async def parse_text(self, text: str) -> LexborHTMLParser:

        """Parse raw HTML string into a document object."""

        return LexborHTMLParser(text)



    @override

    async def select(

        self, parsed_content: LexborHTMLParser, selector: str

    ) -> Sequence[LexborNode]:

        """Select elements matching a CSS selector."""

        return tuple(item for item in parsed_content.css(selector))



    @override

    def is_matching_selector(

        self, parsed_content: LexborHTMLParser, selector: str

    ) -> bool:

        """Check if any element matches the selector."""

        return parsed_content.css_first(selector) is not None



    @override

    def find_links(

        self, parsed_content: LexborHTMLParser, selector: str, attribute: str

    ) -> Iterable[str]:

        """Extract href attributes from elements matching the selector.



        Used by `enqueue_links` helper to discover URLs.

        """

        link: LexborNode

        urls: list[str] = []

        for link in parsed_content.css(selector):

            url = link.attributes.get(attribute)

            if url:

                urls.append(url.strip())

        return urls
```

This is enough to use your parser with `AbstractHttpCrawler.create_parsed_http_crawler_class` factory method. For more control, continue with custom context and crawler classes below.

### Crawling context definition (optional)[​](#crawling-context-definition-optional "Direct link to Crawling context definition (optional)")

The crawling context is passed to request handlers and provides access to the parsed content. Extend [`ParsedHttpCrawlingContext`](https://crawlee.dev/python/python/api/class/ParsedHttpCrawlingContext.md) to define the interface your handlers will work with. Here you can implement additional helpers for the crawler context.

selectolax\_context.py

```
from dataclasses import dataclass, fields



from selectolax.lexbor import LexborHTMLParser

from typing_extensions import Self



from crawlee.crawlers._abstract_http import ParsedHttpCrawlingContext





# Custom context for Selectolax parser, you can add your own methods here

# to facilitate working with the parsed document.

@dataclass(frozen=True)

class SelectolaxLexborContext(ParsedHttpCrawlingContext[LexborHTMLParser]):

    """Crawling context providing access to the parsed page.



    This context is passed to request handlers and includes all standard

    context methods (push_data, enqueue_links, etc.) plus custom helpers.

    """



    @property

    def parser(self) -> LexborHTMLParser:

        """Convenient alias for accessing the parsed document."""

        return self.parsed_content



    @classmethod

    def from_parsed_http_crawling_context(

        cls, context: ParsedHttpCrawlingContext[LexborHTMLParser]

    ) -> Self:

        """Create custom context from the base context.



        Copies all fields from the base context to preserve framework

        functionality while adding custom interface.

        """

        return cls(

            **{field.name: getattr(context, field.name) for field in fields(context)}

        )
```

### Crawler composition[​](#crawler-composition "Direct link to Crawler composition")

The crawler class connects the parser and context. Extend [`AbstractHttpCrawler`](https://crawlee.dev/python/python/api/class/AbstractHttpCrawler.md) and configure the context pipeline to use your custom components:

selectolax\_crawler.py

```
from __future__ import annotations



from typing import TYPE_CHECKING



from selectolax.lexbor import LexborHTMLParser, LexborNode



from crawlee.crawlers import AbstractHttpCrawler, HttpCrawlerOptions



from .selectolax_context import SelectolaxLexborContext

from .selectolax_parser import SelectolaxLexborParser



if TYPE_CHECKING:

    from collections.abc import AsyncGenerator



    from typing_extensions import Unpack



    from crawlee.crawlers._abstract_http import ParsedHttpCrawlingContext





# Custom crawler using custom context, It is optional and you can use

# AbstractHttpCrawler directly with SelectolaxLexborParser if you don't need

# any custom context methods.

class SelectolaxLexborCrawler(

    AbstractHttpCrawler[SelectolaxLexborContext, LexborHTMLParser, LexborNode]

):

    """Custom crawler using Selectolax Lexbor for HTML parsing."""



    def __init__(

        self,

        **kwargs: Unpack[HttpCrawlerOptions[SelectolaxLexborContext]],

    ) -> None:

        # Final step converts the base context to custom context type.

        async def final_step(

            context: ParsedHttpCrawlingContext[LexborHTMLParser],

        ) -> AsyncGenerator[SelectolaxLexborContext, None]:

            # Yield custom context wrapping with additional functionality around the base

            # context.

            yield SelectolaxLexborContext.from_parsed_http_crawling_context(context)



        # Build context pipeline: HTTP request -> parsing -> custom context.

        kwargs['_context_pipeline'] = (

            self._create_static_content_crawler_pipeline().compose(final_step)

        )

        super().__init__(

            parser=SelectolaxLexborParser(),

            **kwargs,

        )
```

### Crawler usage[​](#crawler-usage "Direct link to Crawler usage")

The custom crawler works like any built-in crawler. Request handlers receive your custom context with full access to framework helpers like [`enqueue_links`](https://crawlee.dev/python/python/api/class/EnqueueLinksFunction.md). Additionally, the custom parser can be used with [`AdaptivePlaywrightCrawler`](https://crawlee.dev/python/python/api/class/AdaptivePlaywrightCrawler.md) for adaptive crawling:

* SelectolaxCrawler
* AdaptivePlaywrightCrawler with SelectolaxParser

```
import asyncio



from .selectolax_crawler import SelectolaxLexborContext, SelectolaxLexborCrawler





async def main() -> None:

    crawler = SelectolaxLexborCrawler(

        max_requests_per_crawl=10,

    )



    @crawler.router.default_handler

    async def handle_request(context: SelectolaxLexborContext) -> None:

        context.log.info(f'Processing {context.request.url} ...')



        data = {

            'url': context.request.url,

            'title': context.parser.css_first('title').text(),

        }



        await context.push_data(data)

        await context.enqueue_links()



    await crawler.run(['https://crawlee.dev/'])





if __name__ == '__main__':

    asyncio.run(main())
```

```
import asyncio



from crawlee.crawlers import (

    AdaptivePlaywrightCrawler,

    AdaptivePlaywrightCrawlingContext,

)



from .selectolax_parser import SelectolaxLexborParser





async def main() -> None:

    crawler: AdaptivePlaywrightCrawler = AdaptivePlaywrightCrawler(

        max_requests_per_crawl=10,

        # Use custom Selectolax parser for static content parsing.

        static_parser=SelectolaxLexborParser(),

    )



    @crawler.router.default_handler

    async def handle_request(context: AdaptivePlaywrightCrawlingContext) -> None:

        context.log.info(f'Processing {context.request.url} ...')

        data = {

            'url': context.request.url,

            'title': await context.query_selector_one('title'),

        }



        await context.push_data(data)



        await context.enqueue_links()



    await crawler.run(['https://crawlee.dev/'])





if __name__ == '__main__':

    asyncio.run(main())
```

## Conclusion[​](#conclusion "Direct link to Conclusion")

This guide provided a comprehensive overview of HTTP crawlers in Crawlee. You learned about the three main crawler types - [`BeautifulSoupCrawler`](https://crawlee.dev/python/python/api/class/BeautifulSoupCrawler.md) for fault-tolerant HTML parsing, [`ParselCrawler`](https://crawlee.dev/python/python/api/class/ParselCrawler.md) for high-performance extraction with XPath and CSS selectors, and [`HttpCrawler`](https://crawlee.dev/python/python/api/class/HttpCrawler.md) for raw response processing. You also discovered how to integrate third-party parsing libraries with [`HttpCrawler`](https://crawlee.dev/python/python/api/class/HttpCrawler.md) and how to create fully custom crawlers using [`AbstractHttpCrawler`](https://crawlee.dev/python/python/api/class/AbstractHttpCrawler.md) for specialized parsing requirements.

If you have questions or need assistance, feel free to reach out on our [GitHub](https://github.com/apify/crawlee-python) or join our [Discord community](https://discord.com/invite/jyEM2PRvMU). Happy scraping!

[Edit this page](https://github.com/apify/crawlee-python/edit/master/website/versioned_docs/version-1.9/guides/http_crawlers.mdx)

Last updated

<!-- -->

on **Aug 4, 2026** by **Vlada Dusek**

[Previous](https://crawlee.dev/python/python/docs/guides/http-clients.md)

[HTTP clients](https://crawlee.dev/python/python/docs/guides/http-clients.md)

[Next](https://crawlee.dev/python/python/docs/guides/http-headers.md)

[HTTP headers](https://crawlee.dev/python/python/docs/guides/http-headers.md)

* [](https://crawlee.dev/python/python)
* [Guides](https://crawlee.dev/python/python/docs/guides.md)
* HTTP headers

Version: 1.9

On this page

# HTTP headers

Every request a crawler sends includes [HTTP headers](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers). These headers tell the server who is making the request, what content is acceptable, and in what language. The server reads them and decides what to return. The same URL can return different content, a different status code, or a blocked page depending on the headers it sees. This guide covers the headers that shape a scraping request, like `User-Agent`, `Accept-Language`, and `Content-Type`, what Crawlee sends by default, and how to change them.

## What headers do[​](#what-headers-do "Direct link to What headers do")

Headers are key-value metadata attached to a request. Some of them shape what you get back. Others identify you or carry state.

### Identity headers[​](#identity-headers "Direct link to Identity headers")

`User-Agent` identifies the client. Many sites serve different markup to a browser than to a crawler. Some reject requests whose `User-Agent` doesn't look like a real browser. It's one of the first signals a server reads.

`Referer` says which page the request came from. Some sites gate content, images, or API responses behind an expected `Referer`. A direct request with no `Referer`, or the wrong one, gets a different answer than a click from inside the site.

### Content negotiation[​](#content-negotiation "Direct link to Content negotiation")

These headers tell the server what the client can handle and the server uses them to pick what to send:

`Accept` lists the formats the client wants. The same endpoint can return HTML to one `Accept` and JSON to another. If you need data from an API, try setting it to `application/json` to get JSON instead of a rendered page.

`Accept-Language` lists the languages the client prefers, in priority order. It's a preference, not a switch. A server honors it only for content it actually serves in more than one language, and ignores it otherwise. Where it applies, it changes translated text, date and number formats, and sometimes currency. Set it to match the locale you expect, then confirm from the response that the server applied it.

`Accept-Encoding` lists the compression formats the client accepts, such as `gzip`, `br`, or `zstd`. The server compresses the body to one of them. Compression matters for cost. Without compression the response body can be several times larger, and when you route traffic through a metered [proxy](https://crawlee.dev/python/python/docs/guides/proxy-management.md) that extra volume is billed bandwidth. Crawlee's HTTP clients advertise the formats they support and decompress the response for you, so you receive the smaller body and read it as plain bytes.

### Request body[​](#request-body "Direct link to Request body")

`Content-Type` declares the format of the body you send, not the format you want back. It applies whenever a request carries a body, for example a `POST` that submits a form or JSON. An API that expects `application/json` can reject a payload sent as `application/x-www-form-urlencoded`, and a form endpoint can reject the reverse. Set it to match the body you attach.

`Content-Length` is derived from the body for you, so you don't set it by hand.

`Origin` says which site the request was initiated from. Some APIs check it on requests that carry a body and reject the ones that don't match an expected value.

### Authentication and stateful headers[​](#authentication-and-stateful-headers "Direct link to Authentication and stateful headers")

`Cookie` carries session and login state. Crawlee manages cookies through [sessions](https://crawlee.dev/python/python/docs/guides/session-management.md), so you rarely set this one by hand.

`Authorization` carries credentials, such as a bearer token or basic auth. APIs commonly require it. Set it on the request when the target needs authenticated access. Treat its value as a secret, and don't send it through a [proxy you don't control](https://crawlee.dev/python/python/docs/guides/security-of-web-scraping.md#untrusted-proxies).

### Client hints and fingerprinting headers[​](#client-hints-and-fingerprinting-headers "Direct link to Client hints and fingerprinting headers")

`sec-ch-ua` and similar client hints describe the browser and its platform. `sec-fetch-*` metadata headers describe how the request was initiated. Real browsers send them. Most automated clients don't. Anti-bot systems read them to separate a browser from automated traffic.

### Non-standard headers[​](#non-standard-headers "Direct link to Non-standard headers")

A server can read any header it wants, not only the standard ones. AJAX endpoints often expect `X-Requested-With: XMLHttpRequest`. A site can require a custom `X-Api-Key` or `X-CSRF-Token`. A mobile app's backend usually expects its own set, such as an app version in `X-App-Version`, a device ID in `X-Device-Id`, or a token the app attaches itself. There is no fixed list. When a request works in a browser or an app but fails from a crawler, capture the full set of headers the original sends and look for one you're missing.

### Headers don't guarantee a result[​](#headers-dont-guarantee-a-result "Direct link to Headers don't guarantee a result")

A header is a request, not a command. The server decides what to do with it. A header it doesn't accept can be ignored, so the value you set has no effect on the response. Another can be rejected outright, and the response comes back as an error. Some headers only take effect in combination with others. Setting a header is the first step. Confirm from the response that it did what you expected.

## Default headers in Crawlee[​](#default-headers-in-crawlee "Direct link to Default headers in Crawlee")

All built-in HTTP clients impersonate a browser by default. Instead of a bare library `User-Agent` like `python-httpx/0.27`, they send a realistic set of browser-like headers: a browser `User-Agent`, an `Accept`, an `Accept-Language`, and client hints where the client supports them. Such headers make a crawl look like normal browser traffic and avoid the simplest forms of blocking.

Each client implements impersonation its own way:

* [`ImpitHttpClient`](https://crawlee.dev/python/python/api/class/ImpitHttpClient.md) (the default) impersonates Firefox at the TLS and HTTP layer through the [`impit`](https://pypi.org/project/impit/) library.
* [`HttpxHttpClient`](https://crawlee.dev/python/python/api/class/HttpxHttpClient.md) uses a [`HeaderGenerator`](https://crawlee.dev/python/python/api/class/HeaderGenerator.md) to add `Accept`, `Accept-Language`, and `User-Agent`.
* [`CurlImpersonateHttpClient`](https://crawlee.dev/python/python/api/class/CurlImpersonateHttpClient.md) impersonates Chrome at the TLS and HTTP layer through [`curl-cffi`](https://curl-cffi.readthedocs.io/).

The header values match a specific version of a real browser, so the whole set stays internally consistent rather than a mix that no real client would send. For more on staying unblocked, see the [avoid blocking](https://crawlee.dev/python/python/docs/guides/avoid-blocking.md) guide.

## When impersonation hurts[​](#when-impersonation-hurts "Direct link to When impersonation hurts")

Browser-like headers are the right default for scraping normal web pages. They are the wrong default for some APIs and custom endpoints.

A server can expect specific header values that differ from the ones a browser sends. When the headers don't match what it expects, the response can be wrong: an error, a redirect, or a payload meant for a different client. The browser-like values Crawlee adds are part of that mismatch. An endpoint can answer correctly to a plain request and break once an `Accept-Language` or a full browser header set is attached.

If a request behaves differently through Crawlee than through a minimal client, the injected headers are the first thing to check. Inspect what your crawler actually sends by requesting an echo endpoint such as `https://httpbin.org/headers` and reading the response.

## Turning impersonation off[​](#turning-impersonation-off "Direct link to Turning impersonation off")

Impersonation is configured on the HTTP client. To turn it off, build the client without it and pass it to the crawler:

```
from crawlee.crawlers import HttpCrawler

from crawlee.http_clients import ImpitHttpClient



# Send plain requests with no browser-like headers.

crawler = HttpCrawler(http_client=ImpitHttpClient(browser=None))
```

The opt-out is named differently on each client:

* `ImpitHttpClient(browser=None)`
* `HttpxHttpClient(header_generator=None)`
* `CurlImpersonateHttpClient(impersonate=None)`

## Setting your own headers[​](#setting-your-own-headers "Direct link to Setting your own headers")

To send the same custom headers on every request, set them on the HTTP client. To add a header for a single request, pass it on the [`Request`](https://crawlee.dev/python/python/api/class/Request.md). The two sets are merged, and if both define the same header, the per-request value wins.

The example below sets `X-Api-Key` on the client and `Accept` on one of two requests to an echo endpoint. The client header reaches both requests, and the per-request `Accept` is added only to the request that sets it. Impersonation stays on, so the echo also returns the full browser header set, with the request's `Accept` in place of the impersonated one:

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuXFxuZnJvbSBjcmF3bGVlIGltcG9ydCBIdHRwSGVhZGVycywgUmVxdWVzdFxcbmZyb20gY3Jhd2xlZS5jcmF3bGVycyBpbXBvcnQgSHR0cENyYXdsZXIsIEh0dHBDcmF3bGluZ0NvbnRleHRcXG5mcm9tIGNyYXdsZWUuaHR0cF9jbGllbnRzIGltcG9ydCBJbXBpdEh0dHBDbGllbnRcXG5cXG5cXG5hc3luYyBkZWYgbWFpbigpIC0-IE5vbmU6XFxuICAgICMgU2V0IGRlZmF1bHQgaGVhZGVycyBvbiB0aGUgY2xpZW50LiBUaGV5IGFyZSBzZW50IG9uIGV2ZXJ5IHJlcXVlc3QuXFxuICAgIGh0dHBfY2xpZW50ID0gSW1waXRIdHRwQ2xpZW50KGhlYWRlcnM9eydYLUFwaS1LZXknOiAnc2VjcmV0J30pXFxuXFxuICAgIGNyYXdsZXIgPSBIdHRwQ3Jhd2xlcihodHRwX2NsaWVudD1odHRwX2NsaWVudCwgbWF4X3JlcXVlc3RzX3Blcl9jcmF3bD0xMClcXG5cXG4gICAgQGNyYXdsZXIucm91dGVyLmRlZmF1bHRfaGFuZGxlclxcbiAgICBhc3luYyBkZWYgcmVxdWVzdF9oYW5kbGVyKGNvbnRleHQ6IEh0dHBDcmF3bGluZ0NvbnRleHQpIC0-IE5vbmU6XFxuICAgICAgICAjIGBodHRwYmluLm9yZy9oZWFkZXJzYCBlY2hvZXMgdGhlIHJlY2VpdmVkIHJlcXVlc3QgaGVhZGVycyBiYWNrLlxcbiAgICAgICAgcmVzcG9uc2UgPSAoYXdhaXQgY29udGV4dC5odHRwX3Jlc3BvbnNlLnJlYWQoKSkuZGVjb2RlKClcXG4gICAgICAgIGNvbnRleHQubG9nLmluZm8oZid7Y29udGV4dC5yZXF1ZXN0LnVuaXF1ZV9rZXl9OiB7cmVzcG9uc2V9JylcXG5cXG4gICAgIyBBZGQgYSBoZWFkZXIgZm9yIHRoaXMgcmVxdWVzdCBvbmx5LiBJdCBtZXJnZXMgd2l0aCB0aGUgY2xpZW50IGRlZmF1bHRzLlxcbiAgICByZXF1ZXN0ID0gUmVxdWVzdC5mcm9tX3VybChcXG4gICAgICAgICdodHRwczovL2h0dHBiaW4ub3JnL2hlYWRlcnMnLFxcbiAgICAgICAgaGVhZGVycz1IdHRwSGVhZGVycyh7J0FjY2VwdCc6ICdhcHBsaWNhdGlvbi9qc29uJ30pLFxcbiAgICAgICAgIyBCb3RoIHJlcXVlc3RzIHRhcmdldCB0aGUgc2FtZSBVUkwuIFdpdGhvdXQgYSBkaXN0aW5jdCBgdW5pcXVlX2tleWAsXFxuICAgICAgICAjIGRlZHVwbGljYXRpb24gd291bGQgZHJvcCB0aGlzIG9uZS5cXG4gICAgICAgIHVuaXF1ZV9rZXk9J3NldC1oZWFkZXJzLWV4YW1wbGUnLFxcbiAgICApXFxuXFxuICAgIGF3YWl0IGNyYXdsZXIucnVuKFsnaHR0cHM6Ly9odHRwYmluLm9yZy9oZWFkZXJzJywgcmVxdWVzdF0pXFxuXFxuXFxuaWYgX19uYW1lX18gPT0gJ19fbWFpbl9fJzpcXG4gICAgYXN5bmNpby5ydW4obWFpbigpKVxcblwifSIsIm9wdGlvbnMiOnsiYnVpbGQiOiJsYXRlc3QiLCJjb250ZW50VHlwZSI6ImFwcGxpY2F0aW9uL2pzb247IGNoYXJzZXQ9dXRmLTgiLCJtZW1vcnkiOjEwMjQsInRpbWVvdXQiOjE4MH19.-e8rJsMIs6tJhfn78mG4XwK5ZPfzWJGDxifetFpIyTc\&asrc=run_on_apify)

```
import asyncio



from crawlee import HttpHeaders, Request

from crawlee.crawlers import HttpCrawler, HttpCrawlingContext

from crawlee.http_clients import ImpitHttpClient





async def main() -> None:

    # Set default headers on the client. They are sent on every request.

    http_client = ImpitHttpClient(headers={'X-Api-Key': 'secret'})



    crawler = HttpCrawler(http_client=http_client, max_requests_per_crawl=10)



    @crawler.router.default_handler

    async def request_handler(context: HttpCrawlingContext) -> None:

        # `httpbin.org/headers` echoes the received request headers back.

        response = (await context.http_response.read()).decode()

        context.log.info(f'{context.request.unique_key}: {response}')



    # Add a header for this request only. It merges with the client defaults.

    request = Request.from_url(

        'https://httpbin.org/headers',

        headers=HttpHeaders({'Accept': 'application/json'}),

        # Both requests target the same URL. Without a distinct `unique_key`,

        # deduplication would drop this one.

        unique_key='set-headers-example',

    )



    await crawler.run(['https://httpbin.org/headers', request])





if __name__ == '__main__':

    asyncio.run(main())
```

[`HttpxHttpClient`](https://crawlee.dev/python/python/api/class/HttpxHttpClient.md) and [`CurlImpersonateHttpClient`](https://crawlee.dev/python/python/api/class/CurlImpersonateHttpClient.md) take the same `headers` argument.

Header names are case-insensitive, and [`HttpHeaders`](https://crawlee.dev/python/python/api/class/HttpHeaders.md) normalizes the casing for you, so `user-agent` and `User-Agent` refer to the same header.

## Header order and fingerprinting[​](#header-order-and-fingerprinting "Direct link to Header order and fingerprinting")

Anti-bot systems look at more than header values. They look at which headers are present, their casing, and the order they arrive in. Real browsers send a consistent, recognizable set. A request that has a browser `User-Agent` but the wrong header order, or missing client hints, still looks automated.

This fingerprinting is why `ImpitHttpClient` and `CurlImpersonateHttpClient` replicate the browser at the transport layer rather than just attaching headers. Setting a browser `User-Agent` on a plain client isn't enough to pass these checks. If a target uses fingerprinting, prefer an impersonating client over hand-set headers.

## Conclusion[​](#conclusion "Direct link to Conclusion")

Headers decide what a server sends back. Crawlee impersonates a browser by default, which keeps a crawl unblocked on normal pages but can break endpoints that expect different headers. Turn impersonation off by building the client without it when you target such an endpoint, set custom headers on the client or per request, and reach for an impersonating client when the target fingerprints its traffic.

If you have questions or need assistance, feel free to reach out on our [GitHub](https://github.com/apify/crawlee-python) or join our [Discord community](https://discord.com/invite/jyEM2PRvMU). Happy scraping!

[Edit this page](https://github.com/apify/crawlee-python/edit/master/website/versioned_docs/version-1.9/guides/http_headers.mdx)

Last updated

<!-- -->

on **Aug 4, 2026** by **Vlada Dusek**

[Previous](https://crawlee.dev/python/python/docs/guides/http-crawlers.md)

[HTTP crawlers](https://crawlee.dev/python/python/docs/guides/http-crawlers.md)

[Next](https://crawlee.dev/python/python/docs/guides/playwright-crawler.md)

[Playwright crawler](https://crawlee.dev/python/python/docs/guides/playwright-crawler.md)

* [](https://crawlee.dev/python/python)
* [Guides](https://crawlee.dev/python/python/docs/guides.md)
* Error handling

Version: 1.9

On this page

# Error handling

This guide demonstrates techniques for handling common errors encountered during web crawling operations.

## Handling proxy errors[​](#handling-proxy-errors "Direct link to Handling proxy errors")

Low-quality proxies can cause problems even with high settings for `max_request_retries` and `max_session_rotations` in [`BasicCrawlerOptions`](https://crawlee.dev/python/python/api/class/BasicCrawlerOptions.md). If you can't get data because of proxy errors, you might want to try again. You can do this using [`failed_request_handler`](https://crawlee.dev/python/python/api/class/BasicCrawler.md#failed_request_handler):

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuXFxuZnJvbSBjcmF3bGVlIGltcG9ydCBSZXF1ZXN0XFxuZnJvbSBjcmF3bGVlLmNyYXdsZXJzIGltcG9ydCBCYXNpY0NyYXdsaW5nQ29udGV4dCwgSHR0cENyYXdsZXIsIEh0dHBDcmF3bGluZ0NvbnRleHRcXG5mcm9tIGNyYXdsZWUuZXJyb3JzIGltcG9ydCBQcm94eUVycm9yXFxuXFxuXFxuYXN5bmMgZGVmIG1haW4oKSAtPiBOb25lOlxcbiAgICAjIFNldCBob3cgbWFueSBzZXNzaW9uIHJvdGF0aW9ucyB3aWxsIGhhcHBlbiBiZWZvcmUgY2FsbGluZyB0aGUgZXJyb3IgaGFuZGxlclxcbiAgICAjIHdoZW4gUHJveHlFcnJvciBvY2N1cnNcXG4gICAgY3Jhd2xlciA9IEh0dHBDcmF3bGVyKG1heF9zZXNzaW9uX3JvdGF0aW9ucz01LCBtYXhfcmVxdWVzdF9yZXRyaWVzPTYpXFxuXFxuICAgICMgRm9yIHRoaXMgZXhhbXBsZSwgd2UnbGwgY3JlYXRlIGEgcHJveHkgZXJyb3IgaW4gb3VyIGhhbmRsZXJcXG4gICAgQGNyYXdsZXIucm91dGVyLmRlZmF1bHRfaGFuZGxlclxcbiAgICBhc3luYyBkZWYgZGVmYXVsdF9oYW5kbGVyKGNvbnRleHQ6IEh0dHBDcmF3bGluZ0NvbnRleHQpIC0-IE5vbmU6XFxuICAgICAgICBjb250ZXh0LmxvZy5pbmZvKGYnUHJvY2Vzc2luZyB7Y29udGV4dC5yZXF1ZXN0LnVybH0gLi4uJylcXG4gICAgICAgIHJhaXNlIFByb3h5RXJyb3IoJ1NpbXVsYXRlZCBwcm94eSBlcnJvcicpXFxuXFxuICAgICMgVGhpcyBoYW5kbGVyIHJ1bnMgYWZ0ZXIgYWxsIHJldHJ5IGF0dGVtcHRzIGFyZSBleGhhdXN0ZWRcXG4gICAgQGNyYXdsZXIuZmFpbGVkX3JlcXVlc3RfaGFuZGxlclxcbiAgICBhc3luYyBkZWYgZmFpbGVkX2hhbmRsZXIoY29udGV4dDogQmFzaWNDcmF3bGluZ0NvbnRleHQsIGVycm9yOiBFeGNlcHRpb24pIC0-IE5vbmU6XFxuICAgICAgICBjb250ZXh0LmxvZy5lcnJvcihmJ0ZhaWxlZCByZXF1ZXN0IHtjb250ZXh0LnJlcXVlc3QudXJsfSwgYWZ0ZXIgNSByb3RhdGlvbnMnKVxcbiAgICAgICAgcmVxdWVzdCA9IGNvbnRleHQucmVxdWVzdFxcbiAgICAgICAgIyBGb3IgcHJveHkgZXJyb3JzLCB3ZSBjYW4gYWRkIGEgbmV3IGBSZXF1ZXN0YCB0byB0cnkgYWdhaW5cXG4gICAgICAgIGlmIGlzaW5zdGFuY2UoZXJyb3IsIFByb3h5RXJyb3IpIGFuZCBub3QgcmVxdWVzdC51bmlxdWVfa2V5LnN0YXJ0c3dpdGgoJ3JldHJ5Jyk6XFxuICAgICAgICAgICAgY29udGV4dC5sb2cuaW5mbyhmJ1JldHJ5aW5nIHtyZXF1ZXN0LnVybH0gLi4uJylcXG4gICAgICAgICAgICAjIENyZWF0ZSBhIG5ldyBgUmVxdWVzdGAgd2l0aCBhIG1vZGlmaWVkIGtleSB0byBhdm9pZCBkZWR1cGxpY2F0aW9uXFxuICAgICAgICAgICAgbmV3X3JlcXVlc3QgPSBSZXF1ZXN0LmZyb21fdXJsKFxcbiAgICAgICAgICAgICAgICByZXF1ZXN0LnVybCwgdW5pcXVlX2tleT1mJ3JldHJ5e3JlcXVlc3QudW5pcXVlX2tleX0nXFxuICAgICAgICAgICAgKVxcblxcbiAgICAgICAgICAgICMgQWRkIHRoZSBuZXcgYFJlcXVlc3RgIHRvIHRoZSBgUXVldWVgXFxuICAgICAgICAgICAgcnEgPSBhd2FpdCBjcmF3bGVyLmdldF9yZXF1ZXN0X21hbmFnZXIoKVxcbiAgICAgICAgICAgIGF3YWl0IHJxLmFkZF9yZXF1ZXN0KG5ld19yZXF1ZXN0KVxcblxcbiAgICBhd2FpdCBjcmF3bGVyLnJ1bihbJ2h0dHBzOi8vY3Jhd2xlZS5kZXYvJ10pXFxuXFxuXFxuaWYgX19uYW1lX18gPT0gJ19fbWFpbl9fJzpcXG4gICAgYXN5bmNpby5ydW4obWFpbigpKVxcblwifSIsIm9wdGlvbnMiOnsiYnVpbGQiOiJsYXRlc3QiLCJjb250ZW50VHlwZSI6ImFwcGxpY2F0aW9uL2pzb247IGNoYXJzZXQ9dXRmLTgiLCJtZW1vcnkiOjEwMjQsInRpbWVvdXQiOjE4MH19.SDxP0k7b-d309vC1F2mCNkS2YXNZWybeoEAXBOnq2cY\&asrc=run_on_apify)

```
import asyncio



from crawlee import Request

from crawlee.crawlers import BasicCrawlingContext, HttpCrawler, HttpCrawlingContext

from crawlee.errors import ProxyError





async def main() -> None:

    # Set how many session rotations will happen before calling the error handler

    # when ProxyError occurs

    crawler = HttpCrawler(max_session_rotations=5, max_request_retries=6)



    # For this example, we'll create a proxy error in our handler

    @crawler.router.default_handler

    async def default_handler(context: HttpCrawlingContext) -> None:

        context.log.info(f'Processing {context.request.url} ...')

        raise ProxyError('Simulated proxy error')



    # This handler runs after all retry attempts are exhausted

    @crawler.failed_request_handler

    async def failed_handler(context: BasicCrawlingContext, error: Exception) -> None:

        context.log.error(f'Failed request {context.request.url}, after 5 rotations')

        request = context.request

        # For proxy errors, we can add a new `Request` to try again

        if isinstance(error, ProxyError) and not request.unique_key.startswith('retry'):

            context.log.info(f'Retrying {request.url} ...')

            # Create a new `Request` with a modified key to avoid deduplication

            new_request = Request.from_url(

                request.url, unique_key=f'retry{request.unique_key}'

            )



            # Add the new `Request` to the `Queue`

            rq = await crawler.get_request_manager()

            await rq.add_request(new_request)



    await crawler.run(['https://crawlee.dev/'])





if __name__ == '__main__':

    asyncio.run(main())
```

You can use this same approach when testing different proxy providers. To better manage this process, you can count proxy errors and [stop the crawler](https://crawlee.dev/python/python/docs/examples/crawler-stop.md) if you get too many.

## Changing how error status codes are handled[​](#changing-how-error-status-codes-are-handled "Direct link to Changing how error status codes are handled")

By default, when [`Sessions`](https://crawlee.dev/python/python/api/class/Session.md) get status codes like [401](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/401), [403](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/403), or [429](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/429), Crawlee marks the [`Session`](https://crawlee.dev/python/python/api/class/Session.md) as `retire` and switches to a new one. This might not be what you want, especially when working with [authentication](https://crawlee.dev/python/python/docs/guides/logging-in-with-a-crawler.md). You can learn more in the [Session management guide](https://crawlee.dev/python/python/docs/guides/session-management.md).

Here's an example of how to change this behavior:

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuaW1wb3J0IGpzb25cXG5cXG5mcm9tIGNyYXdsZWUgaW1wb3J0IEh0dHBIZWFkZXJzXFxuZnJvbSBjcmF3bGVlLmNyYXdsZXJzIGltcG9ydCBIdHRwQ3Jhd2xlciwgSHR0cENyYXdsaW5nQ29udGV4dFxcbmZyb20gY3Jhd2xlZS5lcnJvcnMgaW1wb3J0IEh0dHBTdGF0dXNDb2RlRXJyb3JcXG5mcm9tIGNyYXdsZWUuc2Vzc2lvbnMgaW1wb3J0IFNlc3Npb25Qb29sXFxuXFxuIyBVc2luZyBhIHBsYWNlaG9sZGVyIHJlZnJlc2ggdG9rZW4gZm9yIHRoaXMgZXhhbXBsZVxcblJFRlJFU0hfVE9LRU4gPSAnUExBQ0VIT0xERVInXFxuVU5BVVRIT1JJWkVEX0NPREUgPSA0MDFcXG5cXG5cXG5hc3luYyBkZWYgbWFpbigpIC0-IE5vbmU6XFxuICAgIGNyYXdsZXIgPSBIdHRwQ3Jhd2xlcihcXG4gICAgICAgIG1heF9yZXF1ZXN0X3JldHJpZXM9MixcXG4gICAgICAgICMgT25seSB0cmVhdCA0MDMgYXMgYSBibG9ja2luZyBzdGF0dXMgY29kZSwgbm90IDQwMVxcbiAgICAgICAgc2Vzc2lvbl9wb29sPVNlc3Npb25Qb29sKGNyZWF0ZV9zZXNzaW9uX3NldHRpbmdzPXsnYmxvY2tlZF9zdGF0dXNfY29kZXMnOiBbNDAzXX0pLFxcbiAgICAgICAgIyBEb24ndCB0cmVhdCA0MDEgcmVzcG9uc2VzIGFzIGVycm9yc1xcbiAgICAgICAgaWdub3JlX2h0dHBfZXJyb3Jfc3RhdHVzX2NvZGVzPVtVTkFVVEhPUklaRURfQ09ERV0sXFxuICAgIClcXG5cXG4gICAgQGNyYXdsZXIucm91dGVyLmRlZmF1bHRfaGFuZGxlclxcbiAgICBhc3luYyBkZWYgZGVmYXVsdF9oYW5kbGVyKGNvbnRleHQ6IEh0dHBDcmF3bGluZ0NvbnRleHQpIC0-IE5vbmU6XFxuICAgICAgICBjb250ZXh0LmxvZy5pbmZvKGYnUHJvY2Vzc2luZyB7Y29udGV4dC5yZXF1ZXN0LnVybH0gLi4uJylcXG4gICAgICAgICMgTm93IHdlIGNhbiBoYW5kbGUgNDAxIHJlc3BvbnNlcyBvdXJzZWx2ZXNcXG4gICAgICAgIGlmIGNvbnRleHQuaHR0cF9yZXNwb25zZS5zdGF0dXNfY29kZSA9PSBVTkFVVEhPUklaRURfQ09ERTpcXG4gICAgICAgICAgICAjIEdldCBhIGZyZXNoIGFjY2VzcyB0b2tlblxcbiAgICAgICAgICAgIGhlYWRlcnMgPSB7J2F1dGhvcml6YXRpb24nOiBmJ0JlYXJlciB7UkVGUkVTSF9UT0tFTn0nfVxcbiAgICAgICAgICAgIHJlc3BvbnNlID0gYXdhaXQgY29udGV4dC5zZW5kX3JlcXVlc3QoXFxuICAgICAgICAgICAgICAgICdodHRwczovL3BsYWNlaG9sZGVyLm9yZy9yZWZyZXNoJywgaGVhZGVycz1oZWFkZXJzXFxuICAgICAgICAgICAgKVxcbiAgICAgICAgICAgIGRhdGEgPSBqc29uLmxvYWRzKGF3YWl0IHJlc3BvbnNlLnJlYWQoKSlcXG4gICAgICAgICAgICAjIEFkZCB0aGUgbmV3IHRva2VuIHRvIG91ciBgUmVxdWVzdGAgaGVhZGVyc1xcbiAgICAgICAgICAgIGNvbnRleHQucmVxdWVzdC5oZWFkZXJzIHw9IEh0dHBIZWFkZXJzKFxcbiAgICAgICAgICAgICAgICB7J2F1dGhvcml6YXRpb24nOiBmJ0JlYXJlciB7ZGF0YVtcXFwiYWNjZXNzX3Rva2VuXFxcIl19J30sXFxuICAgICAgICAgICAgKVxcbiAgICAgICAgICAgICMgVHJpZ2dlciBhIHJldHJ5IHdpdGggb3VyIHVwZGF0ZWQgaGVhZGVyc1xcbiAgICAgICAgICAgIHJhaXNlIEh0dHBTdGF0dXNDb2RlRXJyb3IoJ1VuYXV0aG9yaXplZCcsIHN0YXR1c19jb2RlPVVOQVVUSE9SSVpFRF9DT0RFKVxcblxcbiAgICBhd2FpdCBjcmF3bGVyLnJ1bihbJ2h0dHA6Ly9odHRwYmluZ28ub3JnL3N0YXR1cy80MDEnXSlcXG5cXG5cXG5pZiBfX25hbWVfXyA9PSAnX19tYWluX18nOlxcbiAgICBhc3luY2lvLnJ1bihtYWluKCkpXFxuXCJ9Iiwib3B0aW9ucyI6eyJidWlsZCI6ImxhdGVzdCIsImNvbnRlbnRUeXBlIjoiYXBwbGljYXRpb24vanNvbjsgY2hhcnNldD11dGYtOCIsIm1lbW9yeSI6MTAyNCwidGltZW91dCI6MTgwfX0.wpBMTQmPDq-a5XlbK-0JcBNcwfR0HaXuHlowld7s1Gw\&asrc=run_on_apify)

```
import asyncio

import json



from crawlee import HttpHeaders

from crawlee.crawlers import HttpCrawler, HttpCrawlingContext

from crawlee.errors import HttpStatusCodeError

from crawlee.sessions import SessionPool



# Using a placeholder refresh token for this example

REFRESH_TOKEN = 'PLACEHOLDER'

UNAUTHORIZED_CODE = 401





async def main() -> None:

    crawler = HttpCrawler(

        max_request_retries=2,

        # Only treat 403 as a blocking status code, not 401

        session_pool=SessionPool(create_session_settings={'blocked_status_codes': [403]}),

        # Don't treat 401 responses as errors

        ignore_http_error_status_codes=[UNAUTHORIZED_CODE],

    )



    @crawler.router.default_handler

    async def default_handler(context: HttpCrawlingContext) -> None:

        context.log.info(f'Processing {context.request.url} ...')

        # Now we can handle 401 responses ourselves

        if context.http_response.status_code == UNAUTHORIZED_CODE:

            # Get a fresh access token

            headers = {'authorization': f'Bearer {REFRESH_TOKEN}'}

            response = await context.send_request(

                'https://placeholder.org/refresh', headers=headers

            )

            data = json.loads(await response.read())

            # Add the new token to our `Request` headers

            context.request.headers |= HttpHeaders(

                {'authorization': f'Bearer {data["access_token"]}'},

            )

            # Trigger a retry with our updated headers

            raise HttpStatusCodeError('Unauthorized', status_code=UNAUTHORIZED_CODE)



    await crawler.run(['http://httpbingo.org/status/401'])





if __name__ == '__main__':

    asyncio.run(main())
```

## Turning off retries for non-network errors[​](#turning-off-retries-for-non-network-errors "Direct link to Turning off retries for non-network errors")

Sometimes you might get unexpected errors when parsing data, like when a website has an unusual structure. Crawlee normally tries again based on your `max_request_retries` setting, but sometimes you don't want that.

Here's how to turn off retries for non-network errors using [`error_handler`](https://crawlee.dev/python/python/api/class/BasicCrawler.md#error_handler), which runs before Crawlee tries again:

[Run on](https://console.apify.com/actors/HH9rhkFXiZbheuq1V?runConfig=eyJ1IjoiRWdQdHczb2VqNlRhRHQ1cW4iLCJ2IjoxfQ.eyJpbnB1dCI6IntcImNvZGVcIjpcImltcG9ydCBhc3luY2lvXFxuXFxuZnJvbSBjcmF3bGVlLmNyYXdsZXJzIGltcG9ydCBCYXNpY0NyYXdsaW5nQ29udGV4dCwgSHR0cENyYXdsZXIsIEh0dHBDcmF3bGluZ0NvbnRleHRcXG5mcm9tIGNyYXdsZWUuZXJyb3JzIGltcG9ydCBIdHRwU3RhdHVzQ29kZUVycm9yLCBTZXNzaW9uRXJyb3JcXG5cXG5cXG5hc3luYyBkZWYgbWFpbigpIC0-IE5vbmU6XFxuICAgIGNyYXdsZXIgPSBIdHRwQ3Jhd2xlcihtYXhfcmVxdWVzdF9yZXRyaWVzPTUpXFxuXFxuICAgICMgQ3JlYXRlIGEgcGFyc2luZyBlcnJvciBmb3IgZGVtb25zdHJhdGlvblxcbiAgICBAY3Jhd2xlci5yb3V0ZXIuZGVmYXVsdF9oYW5kbGVyXFxuICAgIGFzeW5jIGRlZiBkZWZhdWx0X2hhbmRsZXIoY29udGV4dDogSHR0cENyYXdsaW5nQ29udGV4dCkgLT4gTm9uZTpcXG4gICAgICAgIGNvbnRleHQubG9nLmluZm8oZidQcm9jZXNzaW5nIHtjb250ZXh0LnJlcXVlc3QudXJsfSAuLi4nKVxcbiAgICAgICAgcmFpc2UgVmFsdWVFcnJvcignU2ltdWxhdGVkIHBhcnNpbmcgZXJyb3InKVxcblxcbiAgICAjIFRoaXMgaGFuZGxlciBydW5zIGJlZm9yZSBhbnkgcmV0cnkgYXR0ZW1wdHNcXG4gICAgQGNyYXdsZXIuZXJyb3JfaGFuZGxlclxcbiAgICBhc3luYyBkZWYgcmV0cnlfaGFuZGxlcihjb250ZXh0OiBCYXNpY0NyYXdsaW5nQ29udGV4dCwgZXJyb3I6IEV4Y2VwdGlvbikgLT4gTm9uZTpcXG4gICAgICAgIGNvbnRleHQubG9nLmVycm9yKGYnRmFpbGVkIHJlcXVlc3Qge2NvbnRleHQucmVxdWVzdC51cmx9JylcXG4gICAgICAgICMgT25seSBhbGxvdyByZXRyaWVzIGZvciBuZXR3b3JrLXJlbGF0ZWQgZXJyb3JzXFxuICAgICAgICBpZiBub3QgaXNpbnN0YW5jZShlcnJvciwgKFNlc3Npb25FcnJvciwgSHR0cFN0YXR1c0NvZGVFcnJvcikpOlxcbiAgICAgICAgICAgIGNvbnRleHQubG9nLmVycm9yKCdOb24tbmV0d29yayBlcnJvciBkZXRlY3RlZCcpXFxuICAgICAgICAgICAgIyBTdG9wIGZ1cnRoZXIgcmV0cnkgYXR0ZW1wdHMgZm9yIHRoaXMgYFJlcXVlc3RgXFxuICAgICAgICAgICAgY29udGV4dC5yZXF1ZXN0Lm5vX3JldHJ5ID0gVHJ1ZVxcblxcbiAgICBhd2FpdCBjcmF3bGVyLnJ1bihbJ2h0dHBzOi8vY3Jhd2xlZS5kZXYvJ10pXFxuXFxuXFxuaWYgX19uYW1lX18gPT0gJ19fbWFpbl9fJzpcXG4gICAgYXN5bmNpby5ydW4obWFpbigpKVxcblwifSIsIm9wdGlvbnMiOnsiYnVpbGQiOiJsYXRlc3QiLCJjb250ZW50VHlwZSI6ImFwcGxpY2F0aW9uL2pzb247IGNoYXJzZXQ9dXRmLTgiLCJtZW1vcnkiOjEwMjQsInRpbWVvdXQiOjE4MH19.tpTb6RbC-rTLn6MaogtURkN0YgWsc6iCZfSpQNwNDSE\&asrc=run_on_apify)

```
import asyncio



from crawlee.crawlers import BasicCrawlingContext, HttpCrawler, HttpCrawlingContext

from crawlee.errors import HttpStatusCodeError, SessionError





async def main() -> None:

    crawler = HttpCrawler(max_request_retries=5)



    # Create a parsing error for demonstration

    @crawler.router.default_handler

    async def default_handler(context: HttpCrawlingContext) -> None:

        context.log.info(f'Processing {context.request.url} ...')

        raise ValueError('Simulated parsing error')



    # This handler runs before any retry attempts

    @crawler.error_handler

    async def retry_handler(context: BasicCrawlingContext, error: Exception) -> None:

        context.log.error(f'Failed request {context.request.url}')

        # Only allow retries for network-related errors

        if not isinstance(error, (SessionError, HttpStatusCodeError)):

            context.log.error('Non-network error detected')

            # Stop further retry attempts for this `Request`

            context.request.no_retry = True



    await crawler.run(['https://crawlee.dev/'])





if __name__ == '__main__':

    asyncio.run(main())
```

[Edit this page](https://github.com/apify/crawlee-python/edit/master/website/versioned_docs/version-1.9/guides/error_handling.mdx)

Last updated

<!-- -->

on **Aug 4, 2026** by **Vlada Dusek**

[Previous](https://crawlee.dev/python/python/docs/guides/creating-web-archive.md)

[Creating web archive](https://crawlee.dev/python/python/docs/guides/creating-web-archive.md)

[Next](https://crawlee.dev/python/python/docs/guides/http-clients.md)

[HTTP clients](https://crawlee.dev/python/python/docs/guides/http-clients.md)
