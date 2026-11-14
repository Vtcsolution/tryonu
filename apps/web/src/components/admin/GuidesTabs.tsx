"use client";

import type { ReactNode } from "react";
import { SectionHeader } from "./ui";

/**
 * Three admin guides, written to be followed without help:
 * - Trend research: where to see what Americans (and UK, Canada, UAE) buy this season, step by step.
 * - Growth plan: what to post every day, where, and the words people search.
 * - Project overview: what TryOnU is and how it works, to explain to a company or client.
 * Plain content only: nothing here calls the API.
 */

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-[18px] border border-line bg-surface p-5">
      <h3 className="font-display text-[19px] text-ink">{title}</h3>
      <div className="mt-2 space-y-2 text-[15px] leading-relaxed text-ink-soft">{children}</div>
    </section>
  );
}

function Steps({ items }: { items: ReactNode[] }) {
  return (
    <ol className="list-decimal space-y-1.5 pl-5">
      {items.map((it, i) => (
        <li key={i}>{it}</li>
      ))}
    </ol>
  );
}

function Bullets({ items }: { items: ReactNode[] }) {
  return (
    <ul className="list-disc space-y-1.5 pl-5">
      {items.map((it, i) => (
        <li key={i}>{it}</li>
      ))}
    </ul>
  );
}

function Grid({ head, rows }: { head: string[]; rows: ReactNode[][] }) {
  return (
    <div className="overflow-x-auto rounded-[14px] border border-line">
      <table className="w-full min-w-[620px] text-left text-[14.5px]">
        <thead className="bg-paper-2 text-ink">
          <tr>
            {head.map((h) => (
              <th key={h} className="px-3 py-2 font-semibold">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-line align-top">
              {r.map((c, j) => (
                <td key={j} className="px-3 py-2 text-ink-soft">
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const A = ({ href, children }: { href: string; children: ReactNode }) => (
  <a href={href} target="_blank" rel="noopener" className="font-semibold text-sage-deep underline underline-offset-2">
    {children}
  </a>
);

// ------------------------------------------------------------------ 1. trend research

export function TrendsGuideTab() {
  return (
    <div className="space-y-5">
      <SectionHeader
        title="Trend research"
        hint="Where to see what people in the USA (and UK, Canada, UAE) are buying this season: styles, brands and colours. About 15 minutes a week."
      />

      <Card title="The weekly routine (do it every Monday)">
        <Steps
          items={[
            <>Open <b>Amazon Best Sellers</b> and write down the top 10 coats, boots, sneakers and watches, for women and for men. Note the colours that repeat.</>,
            <>Check those styles and colours on <b>Google Trends</b> (United States, last 90 days). Keep the ones that are rising.</>,
            <>Look at the same styles on <b>Pinterest Trends</b> to see how people wear them together.</>,
            <>Build those outfits in the <b>Team panel</b> from brand stores, eBay and AliExpress, and publish them as Ready looks.</>,
            <>Post the new looks to the community and to Instagram, TikTok, Pinterest and Facebook (see the Growth plan page).</>,
          ]}
        />
      </Card>

      <Card title="Where to look, and what for">
        <Grid
          head={["Site", "What it tells you", "How to use it"]}
          rows={[
            [
              <A key="a" href="https://www.amazon.com/Best-Sellers-Clothing-Shoes-Jewelry/zgbs/fashion">Amazon Best Sellers</A>,
              "What Americans buy most, updated every hour",
              "Open Women's or Men's, then a category (Coats, Boots, Sneakers, Watches). Note the top styles, brands, colours and price range.",
            ],
            [
              <A key="b" href="https://www.amazon.com/gp/movers-and-shakers/fashion">Amazon Movers &amp; Shakers</A>,
              "What is suddenly selling more today",
              "The early signal: a style here this week is often a trend next week.",
            ],
            [
              <A key="c" href="https://trends.google.com/trends/">Google Trends</A>,
              "What people search for, by country",
              "Set the country (United States, United Kingdom…) and Past 90 days. Compare up to 5 terms, e.g. trench coat, puffer jacket, wool coat.",
            ],
            [
              <A key="d" href="https://trends.pinterest.com/">Pinterest Trends</A>,
              "Rising outfit ideas, with how they are worn",
              "Choose the country, search winter outfits, coat outfit, sneakers outfit. Look at the colours in the top pins.",
            ],
            [
              <A key="e" href="https://ads.tiktok.com/business/creativecenter/">TikTok Creative Center</A>,
              "Trending hashtags, songs and products",
              "Trends, then Hashtags or Products; region United States; industry Apparel & Accessories.",
            ],
            [
              <A key="f" href="https://www.ebay.com/sh/research">eBay Terapeak (Seller Hub)</A>,
              "What actually sells on eBay, with prices",
              "Free with an eBay seller account. Search e.g. women's wool coat and sort by total sold.",
            ],
            [
              <A key="g" href="https://www.lyst.com/data/the-lyst-index/">The Lyst Index</A>,
              "The hottest brands and products each quarter",
              "Shows which brands shoppers want right now; pick matching pieces from brand stores.",
            ],
          ]}
        />
      </Card>

      <Card title="Write it down like this">
        <p>One line per finding, so you can build looks from it:</p>
        <Grid
          head={["For", "Piece", "Style", "Colours", "Price range", "Source"]}
          rows={[
            ["Women", "Coat", "Long wool, double-breasted", "Camel, black, cream", "$60–150", "Amazon top 10 + Google Trends rising"],
            ["Men", "Jacket", "Puffer, hooded", "Black, olive", "$50–120", "Amazon Movers & Shakers"],
            ["Both", "Shoes", "Chunky white sneakers", "White", "$40–90", "Pinterest Trends"],
          ]}
        />
        <p className="text-[13.5px] text-muted">These rows are only an example of the format, not current data. Fill them from the sites above each week.</p>
      </Card>

      <Card title="Season calendar (what to prepare, and when)">
        <Grid
          head={["When", "Looks to make"]}
          rows={[
            ["November", "Winter coats and layers, Thanksgiving dinner outfits, Black Friday picks"],
            ["December", "Christmas party, holiday dinner, New Year's Eve, winter travel"],
            ["January to February", "Cold-weather basics, Valentine's Day, Ramadan (from early February 2027)"],
            ["March", "Eid outfits (early March 2027), spring jackets, transition layers"],
            ["April to May", "Spring dresses, light jackets, wedding guest, graduation"],
            ["June to August", "Summer, vacation, festival, beach"],
            ["September to October", "Back to school and work, autumn coats, Halloween"],
          ]}
        />
      </Card>
    </div>
  );
}

// ------------------------------------------------------------------ 2. growth plan

export function GrowthPlanTab() {
  return (
    <div className="space-y-5">
      <SectionHeader
        title="Daily growth plan"
        hint="What to post every day, where, and the words people search in our target countries. A starting plan: keep what brings visitors (Admin, Visitors) and drop what doesn't."
      />

      <Card title="Every day (about 1.5 hours)">
        <Grid
          head={["Where", "How many", "What"]}
          rows={[
            ["Ready looks (Team panel)", "2 new looks", "1 for women, 1 for men, built from this week's trends. US city backdrops for the US market."],
            ["Community", "2 posts + 10 to 15 replies and likes", "Post the new looks. Reply to every member's post and question as a team profile (the TryOnU team badge shows)."],
            ["Instagram", "1 Reel + 3 Stories", "Reel: the before-and-after try-on (photo, then the look on you). Stories: a poll (Buy or skip?), a look, a link to tryonu.app."],
            ["TikTok", "1 to 2 videos", "The same before-and-after, 7 to 15 seconds, a trending song, text on screen: Would you wear this?"],
            ["Pinterest", "3 to 5 pins", "One pin per look picture, a keyword title, posted to boards by season. (Links wait until Pinterest unblocks tryonu.app.)"],
            ["Facebook", "1 post", "The day's best look. Share it in 1 or 2 fashion groups where sharing is allowed."],
            ["Direct messages", "10 to 20", "LinkedIn and Instagram: clothing shops and small brands, offering their own TryOnU store with try-on."],
          ]}
        />
      </Card>

      <Card title="Every week">
        <Bullets
          items={[
            "Monday: trend research (see Trend research), then plan the week's 14 looks.",
            "1 guide or blog post: import one /guides article to Medium, or write a new one.",
            "3 LinkedIn posts for shops and brands: a store website, the try-on API, a result.",
            "1 YouTube Short made from the best Reel of the week.",
            "Friday: check Admin, Visitors and Google Search Console. Which posts brought visitors? Make more like them.",
          ]}
        />
      </Card>

      <Card title="Search words to use (titles, captions, hashtags)">
        <Grid
          head={["Market", "Words people search", "Hashtags"]}
          rows={[
            [
              "USA",
              "winter outfit ideas, what to wear in winter, puffer jacket outfit, wool coat outfit, holiday party outfit, Thanksgiving outfit, sneakers outfit, try on clothes before buying online",
              "#winteroutfit #ootd #outfitideas #holidayoutfit #nyfashion #streetstyle",
            ],
            [
              "United Kingdom",
              "winter outfit ideas UK, Christmas party outfit ideas, wedding guest outfit winter, what to wear in London in December, avoid clothing returns",
              "#ukfashion #winterstyle #christmasoutfit #londonstyle",
            ],
            [
              "Canada",
              "what to wear in snow, Canada winter outfits, warm winter coat women, winter boots outfit",
              "#canadawinter #winterfashion #torontostyle",
            ],
            [
              "UAE",
              "modest fashion outfits, abaya, Eid outfit ideas, winter travel outfits",
              "#modestfashion #abaya #eidoutfit #dubaifashion",
            ],
            [
              "Everywhere",
              "virtual try on clothes, AI outfit try on, try on clothes on my photo, AI stylist, try eBay clothes on, try AliExpress clothes before ordering",
              "#virtualtryon #aifashion #tryonu",
            ],
          ]}
        />
      </Card>

      <Card title="Rules that keep accounts safe">
        <Bullets
          items={[
            "Post as a person, not an advert: show the try-on, ask a question, answer comments.",
            "Never buy followers or likes, and never post the same text in many groups on the same day.",
            "Team profiles always show the TryOnU team badge; don't present them as customers.",
            "Amazon: say coming soon until the Amazon connection is live.",
          ]}
        />
      </Card>
    </div>
  );
}

// ------------------------------------------------------------------ 3. project overview

export function ProjectOverviewTab() {
  return (
    <div className="space-y-5">
      <SectionHeader
        title="Project overview"
        hint="What TryOnU is and how it works, from the shopper's click to the server. Use it to explain the project to a company or a client."
      />

      <Card title="In one paragraph">
        <p>
          TryOnU (tryonu.app) is an AI virtual try-on and shopping platform. A shopper uploads one photo, picks real products, or
          describes an outfit in plain words, and sees themselves wearing the whole look in about a minute. Products come live from
          eBay, AliExpress and brand stores through affiliate networks, and every piece links to the shop that sells it. Around that
          sit an AI stylist, search by photo, ready-made looks, a community, store websites for shops, and a try-on API for other
          websites. Built and run end to end: product, AI pipeline, payments, SEO, email and hosting.
        </p>
      </Card>

      <Card title="What it does (features)">
        <Grid
          head={["For", "Features"]}
          rows={[
            ["Shoppers", "Try one product or a whole outfit on your own photo; AI Stylist from plain words (any language); Find the look from a screenshot; Ready looks; remove, add or swap pieces before generating; My looks gallery; share; credits with PayPal; first outfit free."],
            ["Community", "Posts with up to 10 photos or a video, likes, comments, replies to replies, comment likes, photos and looks in comments, @mentions, follow, People to follow, polls, weekly style challenges with prizes, Reels with music, notifications, moderation."],
            ["Shops", "Their own store website at tryonu.app/<store>: products, try-on (several products together), cart, orders by email and WhatsApp, a dashboard with customer try-ons and monthly plans."],
            ["Developers and brands", "A try-on REST API with secret and website keys, a one-line website widget, a WordPress/WooCommerce plugin, prepaid credit packs, usage reports."],
            ["Admin", "Members, shops, developers, payments, credit prices, try-on budget, product sources, email sending, community moderation, analytics, two-step sign-in, backups and alerts."],
          ]}
        />
      </Card>

      <Card title="How a try-on works (the workflow)">
        <Steps
          items={[
            <><b>Ask:</b> the shopper picks products or types a request. An AI prompt reader turns the request into items, colours, materials and who it is for.</>,
            <><b>Find:</b> each item is searched live across several product sources (marketplaces and brand-store feeds, hundreds of thousands of products). Strict matching keeps only the right item, colour, material and gender; anything missing is reported, never silently replaced.</>,
            <><b>Choose:</b> the shopper sees the selected products, removes or adds pieces, or swaps one for another option. Only the selected products are used.</>,
            <><b>Generate:</b> a background worker draws a labelled look board of the garments and sends one request to the try-on AI, which returns the shopper wearing the whole outfit.</>,
            <><b>Check:</b> an AI vision check compares the result with the products; a clearly wrong result is refunded automatically, with the reason shown.</>,
            <><b>Buy:</b> every piece has a Shop button through a tracked affiliate link to the original store, or the cart on a TryOnU store website.</>,
          ]}
        />
      </Card>

      <Card title="Technology">
        <Grid
          head={["Layer", "What is used"]}
          rows={[
            ["Website", "Next.js (App Router, server-rendered pages), React, TypeScript, Tailwind CSS, React Query; installable as a phone app (PWA) with web push"],
            ["API", "Python, FastAPI (async), SQLAlchemy, Alembic migrations, Pydantic"],
            ["Database", "PostgreSQL with pgvector (product similarity), Redis"],
            ["Background jobs", "Redis queue workers for try-ons, product feeds, emails and payment checks"],
            ["AI", "A dedicated virtual try-on model; large language models for the prompt reader, stylist and result checks; image processing"],
            ["Products", "Marketplace and affiliate product APIs and feeds, searched live; Amazon prepared"],
            ["Payments", "PayPal (live); card, Apple Pay and Google Pay checkout prepared"],
            ["Email", "SMTP with a sending queue, hourly and daily limits, one-click unsubscribe, lifecycle emails"],
            ["SEO and AI search", "Sitemap, structured data (JSON-LD), llms.txt for AI assistants, IndexNow, topic pages and guides"],
            ["Hosting", "Linux VPS, nginx, pm2, zero-downtime deploy script with automatic rollback, nightly backups, health alerts"],
            ["Quality", "About 1,040 automated API tests run on every change"],
          ]}
        />
      </Card>

      <Card title="How the business makes money">
        <Bullets
          items={[
            "Shoppers: one-time credit packs (no subscription); the first outfit is free.",
            "Affiliate commission on purchases made through the Shop links.",
            "Shops: monthly store plans for their own TryOnU store website.",
            "Developers and brands: prepaid try-on API packs.",
          ]}
        />
      </Card>

      <Card title="How to present it (2 minutes)">
        <Steps
          items={[
            "The problem: buying clothes online is guesswork, and returns are expensive for shops.",
            "The demo: upload a photo, type an outfit, see it on yourself in about a minute, buy from the store.",
            "What makes it different: whole outfits from real products in real shops, not one item on a model.",
            "The build: AI pipeline, live product search across four sources, payments, store websites, API, community, SEO, all built and hosted end to end.",
            "What I can do for you: the same for your shop or brand (a try-on button, a store website or the API), or a custom AI product built the same way.",
          ]}
        />
      </Card>
    </div>
  );
}
