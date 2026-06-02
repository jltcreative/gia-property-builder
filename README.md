# GIA Property Builder

Turns property websites into import-ready CSV for [Glamping In Africa](https://glampinginafrica.com).

## What it does

1. **Crawl** — Fetches the property's own website (home, about, rooms, rates, activities pages)
2. **Extract** — Pulls factual data points (GPS, prices, amenities, room details, check-in times)
3. **Review** — Shows everything extracted in an editable form for you to correct/fill gaps
4. **Generate** — Uses Claude to write original copy (overview, subtitle, directions, tips) from verified facts only
5. **Export** — Outputs a CSV matching the GIA WordPress importer schema exactly

## Setup

### Streamlit Community Cloud (free)
1. Fork this repo to your GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Set `app.py` as the main file
5. Deploy

### Run locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Usage

1. Enter your **Anthropic API key** in the sidebar
2. Upload a CSV with property URLs (or add manually)
3. Click **Crawl All Websites**
4. Review extracted facts, fix any gaps
5. Click **Generate Copy**
6. Review generated content
7. Click **Assemble Final CSV** → **Download CSV**
8. Upload the CSV to WordPress at **Properties > Import Properties**

## Input CSV format

| Column | Required | Description |
|--------|----------|-------------|
| official_website_url | Yes | Property's own website |
| property_name | No | Can be confirmed from page |
| booking_url | No | Booking.com affiliate link |
| tripadvisor_url | No | TripAdvisor link |
| viator_url | No | Viator link |
| gyg_url | No | GetYourGuide link |
| go2africa_url | No | Go2Africa link |
| safarinow_url | No | SafariNow link |
| travelpayouts_url | No | TravelPayouts link |
| override_notes | No | Manual notes to guide extraction |

## Anti-hallucination

- Copy is generated ONLY from verified extracted facts
- Missing data shows as `[needs review]` — never invented
- "Why We Love It" is always left blank (written personally)
- No content is copied verbatim from source websites

## Cost

- **Hosting:** Free (Streamlit Community Cloud)
- **API calls:** ~$0.01-0.03 per property with Claude Sonnet
- **Caching:** Fetch, geocode, and LLM results are cached to disk so reruns don't re-bill
