/**
 * Screen 3 & 4: Brief — full brief rendering with optional tag filtering.
 * When ?tag= URL param is present, filters stories to matching tag only.
 */

import { useEffect, useState } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { AppBar } from '../components/AppBar';
import { StoryCard } from '../components/StoryCard';
import { getRun, exportBrief } from '../api/client';
import type { Run, Brief, Section } from '../types/models';

const ROMAN = ['i', 'ii', 'iii', 'iv', 'v'];

function sectionId(title: string): string {
  return 'section-' + title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

// Minimal markdown → HTML pass for content_md blocks in summary/callout/quote sections.
function renderMarkdown(md: string): string {
  return md
    .replace(/^### (.+)$/gm, '<h4 style="font-family: var(--font-display); font-size: 20px; font-weight: 500; margin: 28px 0 12px;">$1</h4>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^- (.+)$/gm, '<div style="padding: 4px 0 4px 16px;">→ $1</div>')
    .replace(/\n\n/g, '<br><br>');
}

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

  // Under a tag filter:
  //   - list sections: keep only stories whose filter_tags include activeTag.
  //     If none match, the section is hidden (and surfaced in the notice).
  //   - non-list sections (summary/callout/quote): hidden entirely under filter,
  //     since the filtered view is a focused per-tag drill-down.
  const visibleSections: Section[] = [];
  const hiddenSectionTitles: string[] = [];

  for (const section of brief.sections) {
    if (!activeTag) {
      visibleSections.push(section);
      continue;
    }
    if (section.type === 'list') {
      const filtered = section.stories.filter((s) =>
        s.filter_tags.includes(activeTag)
      );
      if (filtered.length > 0) {
        visibleSections.push({ ...section, stories: filtered });
      } else if (section.stories.length > 0) {
        hiddenSectionTitles.push(section.title);
      }
    } else {
      hiddenSectionTitles.push(section.title);
    }
  }

  const visibleStoryCount = visibleSections.reduce(
    (sum, s) => sum + (s.type === 'list' ? s.stories.length : 0),
    0
  );

  const hasStructuredContent =
    brief.sections.length > 0 ||
    brief.highlights.length > 0 ||
    brief.executive_summary.length > 0;

  const validSectionIds = new Set<string>([
    ...brief.sections.map((s) => sectionId(s.title)),
    ...(brief.action_items.length > 0 ? [sectionId('Ideas for PM Next Steps')] : []),
    ...(brief.sources.length > 0 ? [sectionId('Sources')] : []),
  ]);

  return (
    <>
      <AppBar
        actions={
          <>
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

        {/* Fallback to raw markdown only when the brief has no structured content. */}
        {!hasStructuredContent && brief.raw_markdown ? (
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


        {/* Highlights (with summary merged in) */}
        {!activeTag && (brief.executive_summary || brief.highlights.length > 0) && (
          <div className="highlights">
            {brief.executive_summary && (
              <>
                <div className="highlights-label">Summary</div>
                <p className="highlights-summary">{brief.executive_summary}</p>
              </>
            )}
            {brief.highlights.length > 0 && (
              <>
                <div className="highlights-label">Top Highlights</div>
                {brief.highlights.map((h) => (
                  <div key={h.rank} className="highlight-item">
                    <span className="highlight-num">{ROMAN[h.rank - 1] || h.rank}.</span>
                    <span className="highlight-text">
                      {h.headline} — {h.why_matters}
                      {validSectionIds.has(sectionId(h.pointer_section)) && (
                        <>
                          {' '}
                          <a className="highlight-pointer" href={`#${sectionId(h.pointer_section)}`}>
                            → {h.pointer_section}
                          </a>
                        </>
                      )}
                    </span>
                  </div>
                ))}
              </>
            )}
          </div>
        )}

        {/* Sections — type drives the rendering */}
        {visibleSections.map((section, idx) => (
          <div key={`${section.title}-${idx}`}>
            <div className="section-heading" id={sectionId(section.title)}>
              <a className="section-heading-text" href={`#${sectionId(section.title)}`}>
                {section.title}
              </a>
              <span className="section-heading-rule" />
              {section.type === 'list' && (
                <span className="section-heading-count">{section.stories.length}</span>
              )}
            </div>

            {section.content_md && (
              <div
                className={section.type === 'callout' ? 'info-notice' : 'section-prose'}
                style={
                  section.type === 'quote'
                    ? {
                        fontFamily: 'var(--font-display)',
                        fontStyle: 'italic',
                        fontSize: '20px',
                        lineHeight: 1.5,
                        padding: '0 0 0 20px',
                        margin: '16px 0 24px',
                        borderLeft: '2px solid var(--accent)',
                      }
                    : section.type === 'summary'
                    ? {
                        fontFamily: 'var(--font-display)',
                        fontStyle: 'italic',
                        fontSize: '17px',
                        lineHeight: 1.6,
                        padding: '0 0 0 20px',
                        margin: '16px 0 24px',
                        borderLeft: '2px solid var(--accent)',
                      }
                    : section.type === 'list'
                    ? { margin: '12px 0 20px', color: 'var(--ink)' }
                    : undefined
                }
                dangerouslySetInnerHTML={{ __html: renderMarkdown(section.content_md) }}
              />
            )}

            {section.type === 'list' &&
              section.stories.map((story) => (
                <StoryCard key={story.id} story={story} runId={id!} />
              ))}
          </div>
        ))}

        {/* Action items */}
        {!activeTag && brief.action_items.length > 0 && (
          <>
            <div className="section-heading" id={sectionId('Ideas for PM Next Steps')}>
              <a className="section-heading-text" href={`#${sectionId('Ideas for PM Next Steps')}`}>
                Ideas for PM Next Steps
              </a>
              <span className="section-heading-rule" />
            </div>
            {brief.action_items.map((item) => (
              <div key={item.rank} className="action-item">
                <span className="action-num">{item.rank}</span>
                <span>
                  {item.text}
                  {validSectionIds.has(sectionId(item.pointer_section)) && (
                    <>
                      {' '}
                      <a className="action-pointer" href={`#${sectionId(item.pointer_section)}`}>
                        → {item.pointer_section}
                      </a>
                    </>
                  )}
                </span>
              </div>
            ))}
          </>
        )}

        {/* Sources */}
        {!activeTag && brief.sources.length > 0 && (
          <>
            <div className="section-heading" id={sectionId('Sources')}>
              <a className="section-heading-text" href={`#${sectionId('Sources')}`}>
                Sources
              </a>
              <span className="section-heading-rule" />
              <span className="section-heading-count">{brief.sources.length}</span>
            </div>
            <ul className="sources-list">
              {[...brief.sources]
                .map((src) => ({ ...src, referenced_in: [...src.referenced_in].sort((a, b) => a.localeCompare(b)) }))
                .sort((a, b) => {
                  const sa = a.referenced_in[0] ?? '';
                  const sb = b.referenced_in[0] ?? '';
                  return sa.localeCompare(sb) || a.domain.localeCompare(b.domain);
                })
                .map((src, i) => (
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
        {activeTag && hiddenSectionTitles.length > 0 && (
          <div className="hidden-notice">
            <i className="ti ti-eye-off" />
            {hiddenSectionTitles.length} {hiddenSectionTitles.length === 1 ? 'section' : 'sections'} hidden:{' '}
            {hiddenSectionTitles.join(', ')}.{' '}
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
