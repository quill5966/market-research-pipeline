/**
 * StoryCard — renders a single story entry within a brief section.
 */

import type { Story } from '../types/models';
import { TagChip } from './TagChip';

interface StoryCardProps {
  story: Story;
  runId: string;
}

export function StoryCard({ story, runId }: StoryCardProps) {
  return (
    <article className="story">
      <h3 className="story-headline">{story.headline}</h3>

      <p className="story-line">
        <span className="story-line-label">TL;DR</span>
        {story.tldr}
      </p>

      <p className="story-line">
        <span className="story-line-label">PM angle</span>
        {story.pm_angle}
      </p>

      {story.supporting && (
        <p className="story-supporting">{story.supporting}</p>
      )}

      <div className="story-source">
        Source:{' '}
        <a href={story.source_url} target="_blank" rel="noopener noreferrer">
          {story.source_domain}
        </a>
        {story.additional_coverage.length > 0 && (
          <> · also: {story.additional_coverage.join(', ')}</>
        )}
      </div>

      <div className="story-footer">
        <div className="story-tags">
          {story.filter_tags.map((tag) => (
            <TagChip key={tag} tag={tag} runId={runId} />
          ))}
        </div>
        <a
          className="explore-btn"
          href={story.source_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          Explore further <i className="ti ti-external-link" />
        </a>
      </div>
    </article>
  );
}
