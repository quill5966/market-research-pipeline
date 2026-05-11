/**
 * Screen 3 & 4: Brief — full brief rendering with optional tag filtering.
 * When ?tag= URL param is present, filters stories to matching tag only.
 */

import { useEffect, useState } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { AppBar } from '../components/AppBar';
import { StoryCard } from '../components/StoryCard';
import { getRun, exportBrief } from '../api/client';
import type { Run, Brief, Story } from '../types/models';

const ROMAN = ['i', 'ii', 'iii', 'iv', 'v'];

const SECTION_LABELS: Record<string, string> = {
  competitor_moves: 'Competitor Moves',
  market_macro: 'Market & Macro',
  customer_buyer: 'Customer Signals',
  technology_ecosystem: 'Technology & Ecosystem',
};

export function BriefScreen() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<string | null>(null);

  const activeTag = searchParams.get('tag');

  useEffect(() => {
    if (!id) return;
    getRun(id)
      .then(setRun)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed'));
  }, [id]);

  async function handleExport() {
    if (!id) return;
    try {
      const blob = await exportBrief(id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `brief-${id.slice(0, 8)}.md`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert('Export failed');
    }
  }

  function handleRerun() {
    navigate('/');
  }

  function clearFilter() {
    navigate(`/runs/${id}/brief`);
  }

  if (error) {
    return (
      <>
        <AppBar />
        <div className="app-body">
          <div className="info-notice" style={{ borderLeft: '3px solid #b91c1c' }}>
            <i className="ti ti-alert-circle" /> {error}
          </div>
        </div>
      </>
    );
  }

  if (!run || !run.brief) {
    return (
      <>
        <AppBar />
        <div className="app-body">
          <p>Loading brief…</p>
        </div>
      </>
    );
  }

  const brief: Brief = run.brief;

  // Filter stories if tag param is present
  const filteredSections: Record<string, Story[]> = {};
  const hiddenSections: string[] = [];

  for (const [sectionKey, stories] of Object.entries(brief.sections)) {
    const filtered = activeTag
      ? stories.filter((s) => s.filter_tags.includes(activeTag))
      : stories;

    if (filtered.length > 0) {
      filteredSections[sectionKey] = filtered;
    } else if (activeTag && stories.length > 0) {
      hiddenSections.push(SECTION_LABELS[sectionKey] || sectionKey);
    }
  }

  // Count total visible stories
  const visibleStoryCount = Object.values(filteredSections).reduce(
    (sum, stories) => sum + stories.length, 0
  );

  return (
    <>
      <AppBar
        actions={
          <>
            {!activeTag && (
              <button className="btn btn-ghost" onClick={() => navigate(`/runs/${id}/brief?tag=`)}>
                <i className="ti ti-filter" /> Filter
              </button>
            )}
            <button className="btn btn-ghost" onClick={handleExport}>
              <i className="ti ti-download" /> Export
            </button>
            <button className="btn btn-ghost" onClick={handleRerun}>
              <i className="ti ti-refresh" /> Re-run
            </button>
          </>
        }
      />
      <div className="app-body">
        {/* Filter bar */}
        {activeTag && (
          <div className="filter-bar">
            <span className="filter-label">Filtered by</span>
            <span className="filter-pill">
              {activeTag}
              <button className="filter-pill-x" onClick={clearFilter}>×</button>
            </span>
            <button className="filter-clear" onClick={clearFilter}>
              Clear filter
            </button>
            <span className="filter-count">
              {visibleStoryCount} {visibleStoryCount === 1 ? 'story' : 'stories'} matching
            </span>
          </div>
        )}

        {/* Brief header */}
        <div className="brief-header">
          <div className="brief-eyebrow">PM Intelligence Brief</div>
          <h1 className="brief-title">
            {brief.title.split(' ').map((word, i) =>
              i === 0 ? <em key={i}>{word} </em> : word + ' '
            )}
          </h1>
          <div className="brief-meta">
            <span>{brief.date}</span>
            <span>{brief.story_count} stories</span>
            <span>{brief.source_count} sources</span>
            <span>{brief.search_term_count} search terms</span>
          </div>
        </div>

        {/* Check if structured data exists or if we need the raw markdown fallback */}
        {Object.keys(filteredSections).length === 0 && !activeTag && brief.raw_markdown ? (
          /* Raw markdown fallback — shown until Phase 3 adds structured JSON synthesis */
          <div
            className="brief-raw-markdown"
            style={{
              fontFamily: 'var(--font-sans)',
              fontSize: '14px',
              lineHeight: '1.7',
              whiteSpace: 'pre-wrap',
              color: 'var(--ink)',
            }}
            dangerouslySetInnerHTML={{
              __html: brief.raw_markdown
                .replace(/^# (.+)$/gm, '<h2 style="font-family: var(--font-display); font-size: 26px; font-weight: 500; letter-spacing: -0.015em; margin: 48px 0 16px;">$1</h2>')
                .replace(/^## (.+)$/gm, '<h3 style="font-family: var(--font-mono); font-size: 11px; text-transform: uppercase; letter-spacing: 0.18em; font-weight: 500; margin: 40px 0 16px; padding-bottom: 8px; border-bottom: 1px solid var(--rule);">$1</h3>')
                .replace(/^### (.+)$/gm, '<h4 style="font-family: var(--font-display); font-size: 20px; font-weight: 500; margin: 28px 0 12px;">$1</h4>')
                .replace(/^\*\*(.+?)\*\*/gm, '<strong>$1</strong>')
                .replace(/^- (.+)$/gm, '<div style="padding: 4px 0 4px 16px; position: relative;">→ $1</div>')
                .replace(/^> (.+)$/gm, '<blockquote style="font-family: var(--font-display); font-style: italic; font-size: 17px; line-height: 1.55; padding: 0 0 0 20px; margin: 16px 0; border-left: 2px solid var(--accent);">$1</blockquote>')
                .replace(/---/g, '<hr style="border: none; border-top: 1px solid var(--rule); margin: 32px 0;">')
                .replace(/\n\n/g, '<br><br>')
            }}
          />
        ) : (
          /* Structured brief rendering */
          <>


        {/* Highlights */}
        {!activeTag && brief.highlights.length > 0 && (
          <div className="highlights">
            <div className="highlights-label">Top Highlights</div>
            {brief.highlights.map((h) => (
              <div key={h.rank} className="highlight-item">
                <span className="highlight-num">{ROMAN[h.rank - 1] || h.rank}.</span>
                <span className="highlight-text">
                  <strong>{h.headline}</strong> — {h.why_matters}
                  <span className="highlight-pointer"> → {h.pointer_section}</span>
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Executive summary */}
        {!activeTag && brief.executive_summary && (
          <p className="exec-summary">{brief.executive_summary}</p>
        )}

        {/* Sections with stories */}
        {Object.entries(filteredSections).map(([sectionKey, stories]) => (
          <div key={sectionKey}>
            <div className="section-heading">
              <span className="section-heading-text">
                {SECTION_LABELS[sectionKey] || sectionKey}
              </span>
              <span className="section-heading-rule" />
              <span className="section-heading-count">{stories.length}</span>
            </div>
            {stories.map((story) => (
              <StoryCard key={story.id} story={story} runId={id!} />
            ))}
          </div>
        ))}

        {/* Watchlist */}
        {!activeTag && brief.watchlist.length > 0 && (
          <>
            <div className="section-heading">
              <span className="section-heading-text">Watchlist</span>
              <span className="section-heading-rule" />
            </div>
            {brief.watchlist.map((item, i) => (
              <div key={i} className="watchlist-item">
                <span className="watchlist-bullet">→</span>
                <span>
                  <span className="watchlist-topic">{item.topic}</span> — {item.signal}
                  <span className="watchlist-source"> ({item.source_domain})</span>
                </span>
              </div>
            ))}
          </>
        )}

        {/* Action items */}
        {!activeTag && brief.action_items.length > 0 && (
          <>
            <div className="section-heading">
              <span className="section-heading-text">PM Action Items</span>
              <span className="section-heading-rule" />
            </div>
            {brief.action_items.map((item) => (
              <div key={item.rank} className="action-item">
                <span className="action-num">{item.rank}</span>
                <span>
                  {item.text}
                  <span className="action-pointer">→ {item.pointer_section}</span>
                </span>
              </div>
            ))}
          </>
        )}

        {/* Sources */}
        {!activeTag && brief.sources.length > 0 && (
          <>
            <div className="section-heading">
              <span className="section-heading-text">Sources</span>
              <span className="section-heading-rule" />
              <span className="section-heading-count">{brief.sources.length}</span>
            </div>
            <ul className="sources-list">
              {brief.sources.map((src, i) => (
                <li key={i}>
                  <a href={src.url} target="_blank" rel="noopener noreferrer">
                    {src.domain}
                  </a>
                  {' '} — {src.referenced_in.join(', ')}
                </li>
              ))}
            </ul>
          </>
        )}

        {/* Hidden sections notice (tag filter) */}
        {activeTag && hiddenSections.length > 0 && (
          <div className="hidden-notice">
            <i className="ti ti-eye-off" />
            {hiddenSections.length} {hiddenSections.length === 1 ? 'section' : 'sections'} hidden:{' '}
            {hiddenSections.join(', ')}.{' '}
            <button className="filter-clear" onClick={clearFilter} style={{ display: 'inline' }}>
              Clear filter
            </button>{' '}
            to see all.
          </div>
        )}
          </>
        )}
      </div>
    </>
  );
}
