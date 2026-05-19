export const DEFAULT_INCLUDE_DOMAINS: string[] = [
  // General tech & enterprise
  'reuters.com',
  'axios.com',
  'techcrunch.com',
  'theverge.com',
  'arstechnica.com',
  'zdnet.com',
  'venturebeat.com',
  'siliconangle.com',
  'theregister.com',
  'computerworld.com',
  'infoworld.com',
  'thenextweb.com',
  // Business & markets
  'cnbc.com',
  'apnews.com',
  'fastcompany.com',
  'inc.com',
  'fortune.com',
  // Funding, M&A & competitive intel
  'crunchbase.com',
  'businesswire.com',
  'prnewswire.com',
  'globenewswire.com',
  'geekwire.com',
  'sifted.eu',
  // Community
  'news.ycombinator.com',
];

export const DEFAULT_EXCLUDE_DOMAINS: string[] = [
  // Aggregators / low-quality
  'finance.yahoo.com',
  'msn.com',
  'news.google.com',
  'smartbrief.com',
  'seekingalpha.com',
  'medium.com',
  // Paywalled sources (Tavily can't scrape usable raw_content)
  'bloomberg.com',
  'wsj.com',
  'ft.com',
  'economist.com',
  'nytimes.com',
  'theinformation.com',
  'wired.com',
  'platformer.news',
  'stratechery.com',
  'gartner.com',
  'forrester.com',
  'idc.com',
  '451research.com',
  'cbinsights.com',
  'pitchbook.com',
];

export const DEFAULT_MAX_RESULTS_PER_TERM = 10;
export const DEFAULT_MAX_ARTICLE_CHARS = 10000;
export const DEFAULT_DEDUP_TITLE_SIMILARITY = 0.6;
export const DEFAULT_DEDUP_SNIPPET_SIMILARITY = 0.8;
